"""
Modelo alternativo: XGBoost de regresion cuantilica (reg:quantileerror).
Pronostico de dengue nivel UF para los 4 tests de validacion IMDC.

Enfoque: modelo GLOBAL (todos los estados) que aprende la forma estacional y
la escala segun el nivel epidemico reciente + covariables climaticas y
oscilaciones oceanicas. Cada ejemplo es (origen=EW25 del anio de temporada,
semana objetivo). Solo se usan features conocidas en el origen -> sin leakage.

Features:
  - ew_sin/cos (3 armonicos)         estacionalidad
  - weeks_ahead                       horizonte
  - clim_med_log                      mediana historica de casos por (uf,ew), solo temporadas previas
  - level_log                         nivel reciente (EW18-25 del anio origen)
  - growth_yoy                        crecimiento interanual del nivel
  - prev_season_total_log             tamanio de la temporada anterior
  - enso,iod,pdo                      oscilaciones oceanicas en el origen
  - c_temp,c_precip,c_humid           clima climatologico UF-ew (esperado)
  - pop_log                           poblacion
  - uf                                estado (categorico)
Target: log1p(casos).

Salida: outputs/predictions/dengue_uf_validation_xgb.csv (formato Mosqlimate)
"""
import os, sys
import numpy as np, pandas as pd
import xgboost as xgb
from epiweeks import Week

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "..", "outputs", "predictions")
sys.path.insert(0, HERE)
import train_imdc as T

QUANTILES = np.array([0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975])
QNAME = {0.025: "lower_95", 0.05: "lower_90", 0.10: "lower_80", 0.25: "lower_50",
         0.50: "pred", 0.75: "upper_50", 0.90: "upper_80", 0.95: "upper_90",
         0.975: "upper_95"}
FEATS = ["ew_sin1", "ew_cos1", "ew_sin2", "ew_cos2", "ew_sin3", "ew_cos3",
         "weeks_ahead", "clim_med_log", "level_log", "growth_yoy",
         "prev_season_total_log", "enso", "iod", "pdo",
         "c_temp", "c_precip", "c_humid", "pop_log", "uf"]


def build_base():
    d = pd.read_csv(os.path.join(DATA, "dengue.csv.gz"),
                    usecols=["date", "casos", "uf", "uf_code", "epiweek"])
    d = d[d.uf != "ES"].copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.groupby(["uf", "uf_code", "date", "epiweek"], as_index=False)["casos"].sum()
    d["ew"] = d.epiweek % 100
    d["ey"] = d.epiweek // 100
    # anio de temporada (origen): si ew>=41 -> ey, si no -> ey-1
    d["oy"] = np.where(d.ew >= 41, d.ey, d.ey - 1)
    # cutoff EW25 del anio origen
    cut = {y: pd.Timestamp(Week(int(y), 25, system="cdc").startdate())
           for y in d.oy.unique() if y >= 2009}
    d["cutoff"] = d.oy.map(cut)
    d["weeks_ahead"] = ((d.date - d.cutoff).dt.days / 7).round().astype("Int64")
    return d


def add_features(d):
    # ---- oscilaciones en el origen (EW25 oy) ----
    osc = pd.read_csv(os.path.join(DATA, "ocean_climate_oscillations.csv.gz"))
    osc["date"] = pd.to_datetime(osc["date"])
    osc["ew"] = osc.epiweek % 100
    osc["ey"] = osc.epiweek // 100
    osc25 = osc[osc.ew == 25].groupby("ey")[["enso", "iod", "pdo"]].mean()
    d = d.merge(osc25, left_on="oy", right_index=True, how="left")
    # ---- poblacion ----
    pop = pd.read_csv(os.path.join(DATA, "datasus_population_2001_2025.csv.gz"))
    gm = pd.read_csv(os.path.join(DATA, "dengue.csv.gz"), usecols=["geocode", "uf"]).drop_duplicates()
    pop = pop.merge(gm, on="geocode").groupby(["uf", "year"], as_index=False)["population"].sum()
    pop2 = pop.copy()
    d = d.merge(pop.rename(columns={"year": "oy", "population": "pop"}), on=["uf", "oy"], how="left")
    d["pop"] = d.groupby("uf")["pop"].ffill().bfill()
    d["pop_log"] = np.log1p(d["pop"])
    # ---- clima climatologico UF-ew ----
    clim = pd.read_csv(os.path.join(OUT, "uf_climate_climatology.csv"))
    d = d.merge(clim, on=["uf", "ew"], how="left")
    # ---- nivel reciente por (uf, oy): media log casos EW18-25 del anio oy ----
    lvl = d[(d.ey == d.oy) & (d.ew.between(18, 25))].groupby(["uf", "oy"])["casos"].mean()
    lvl = np.log1p(lvl).rename("level_log").reset_index()
    d = d.merge(lvl, on=["uf", "oy"], how="left")
    lvl_prev = lvl.rename(columns={"oy": "oy_j", "level_log": "level_prev"})
    d = d.merge(lvl_prev.assign(oy=lambda x: x.oy_j + 1)[["uf", "oy", "level_prev"]],
                on=["uf", "oy"], how="left")
    d["level_log"] = d["level_log"].fillna(0)
    d["level_prev"] = d["level_prev"].fillna(d["level_log"])
    d["growth_yoy"] = d["level_log"] - d["level_prev"]
    # ---- total temporada anterior ----
    seas = d.groupby(["uf", "oy"])["casos"].sum().rename("season_total").reset_index()
    seas["prev_season_total_log"] = np.log1p(seas["season_total"])
    d = d.merge(seas.assign(oy=lambda x: x.oy + 1)[["uf", "oy", "prev_season_total_log"]],
                on=["uf", "oy"], how="left")
    d["prev_season_total_log"] = d["prev_season_total_log"].fillna(0)
    # ---- armonicos estacionales ----
    for k in (1, 2, 3):
        d[f"ew_sin{k}"] = np.sin(2 * np.pi * k * d.ew / 52)
        d[f"ew_cos{k}"] = np.cos(2 * np.pi * k * d.ew / 52)
    return d


def clim_med_expanding(d):
    """mediana de casos por (uf,ew) usando solo temporadas de origen < origen del ejemplo."""
    piv = d.groupby(["uf", "ew", "oy"])["casos"].mean().reset_index()
    out = []
    for (uf, ew), g in piv.groupby(["uf", "ew"]):
        g = g.sort_values("oy")
        med = g["casos"].expanding().median().shift(1)  # excluye el propio origen
        out.append(pd.DataFrame({"uf": uf, "ew": ew, "oy": g.oy.values,
                                 "clim_med": med.values}))
    cm = pd.concat(out, ignore_index=True)
    cm["clim_med_log"] = np.log1p(cm["clim_med"].fillna(cm["clim_med"].median()))
    return cm


FEATCACHE = os.path.join(OUT, "xgb_features.parquet")


def build_feature_table():
    import time
    t = time.time()
    d = build_base(); print(f"  base {time.time()-t:.0f}s", flush=True); t = time.time()
    d = add_features(d); print(f"  feats {time.time()-t:.0f}s", flush=True); t = time.time()
    cm = clim_med_expanding(d); print(f"  climmed {time.time()-t:.0f}s", flush=True)
    d = d.merge(cm[["uf", "ew", "oy", "clim_med_log"]], on=["uf", "ew", "oy"], how="left")
    d["clim_med_log"] = d["clim_med_log"].fillna(np.log1p(d["casos"].median()))
    d["y"] = np.log1p(d["casos"])
    keep = ["uf", "uf_code", "date", "ew", "ey", "oy", "casos", "y"] + FEATS
    d = d[list(dict.fromkeys(keep))]
    d.to_parquet(FEATCACHE)
    print(f"  cache -> {FEATCACHE} ({len(d)} filas)", flush=True)
    return d


def main():
    if os.path.exists(FEATCACHE):
        d = pd.read_parquet(FEATCACHE)
    else:
        d = build_feature_table()
    d["date"] = pd.to_datetime(d["date"])
    d["uf"] = d["uf"].astype("category")

    results = []
    for tname, Y in T.TESTS:
        train = d[(d.oy < Y) & d.weeks_ahead.notna()].dropna(subset=FEATS + ["y"])
        # filas objetivo: la temporada de origen Y, semanas EW41 Y -> EW40 Y+1
        tgt_dates = T.season_dates(Y)
        pred = d[(d.oy == Y) & (d.date.isin(tgt_dates))].copy()
        Xtr = train[FEATS].copy(); Xpr = pred[FEATS].copy()
        model = xgb.XGBRegressor(
            objective="reg:quantileerror", quantile_alpha=QUANTILES,
            n_estimators=400, max_depth=5, learning_rate=0.04,
            subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
            enable_categorical=True, tree_method="hist", n_jobs=2)
        model.fit(Xtr, train["y"].values)
        q = model.predict(Xpr)                     # (n, 9) en log
        q = np.expm1(q)
        q = np.clip(q, 0, None)
        q = np.sort(q, axis=1)                     # monotonia de cuantiles
        res = pred[["uf", "uf_code", "date"]].copy()
        for j, ql in enumerate(QUANTILES):
            res[QNAME[ql]] = q[:, j]
        res["validation_test"] = tname
        res["level"] = "state"; res["unit_id"] = res["uf"]; res["unit_name"] = res["uf"]
        results.append(res)
        print(f"{tname}: train {len(Xtr)} filas, pred {len(res)} filas", flush=True)

    out = pd.concat(results, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    cols = ["level", "unit_id", "unit_name", "uf", "uf_code", "validation_test", "date",
            "pred", "lower_50", "upper_50", "lower_80", "upper_80",
            "lower_90", "upper_90", "lower_95", "upper_95"]
    out = out[cols].sort_values(["uf", "validation_test", "date"])
    fn = os.path.join(OUT, "dengue_uf_validation_xgb.csv")
    out.to_csv(fn, index=False)
    print(f"OK -> {fn} | filas {len(out)}", flush=True)


if __name__ == "__main__":
    main()
