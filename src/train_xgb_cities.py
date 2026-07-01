"""
XGBoost cuantilico para las 15 ciudades objetivo (reto opcional 1).
Mismo enfoque que train_xgb.py pero a nivel municipio (geocode).
El clima climatologico se toma del UF de cada ciudad.

Salida: outputs/predictions/dengue_cities_validation_xgb.csv
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
from train_xgb import QUANTILES, QNAME, FEATS


def build_cities():
    gcs = list(T.CITIES.keys())
    d = pd.read_csv(os.path.join(DATA, "dengue.csv.gz"),
                    usecols=["date", "casos", "geocode", "uf", "uf_code", "epiweek"])
    d = d[d.geocode.isin(gcs)].copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.groupby(["geocode", "uf", "uf_code", "date", "epiweek"], as_index=False)["casos"].sum()
    d["ew"] = d.epiweek % 100
    d["ey"] = d.epiweek // 100
    d["oy"] = np.where(d.ew >= 41, d.ey, d.ey - 1)
    cut = {y: pd.Timestamp(Week(int(y), 25, system="cdc").startdate())
           for y in d.oy.unique() if y >= 2009}
    d["cutoff"] = d.oy.map(cut)
    d["weeks_ahead"] = ((d.date - d.cutoff).dt.days / 7).round().astype("Int64")

    # oscilaciones en el origen
    osc = pd.read_csv(os.path.join(DATA, "ocean_climate_oscillations.csv.gz"))
    osc["ew"] = osc.epiweek % 100; osc["ey"] = osc.epiweek // 100
    osc25 = osc[osc.ew == 25].groupby("ey")[["enso", "iod", "pdo"]].mean()
    d = d.merge(osc25, left_on="oy", right_index=True, how="left")

    # poblacion por geocode-anio
    pop = pd.read_csv(os.path.join(DATA, "datasus_population_2001_2025.csv.gz"))
    d = d.merge(pop.rename(columns={"year": "oy", "population": "pop"}),
                on=["geocode", "oy"], how="left")
    d["pop"] = d.groupby("geocode")["pop"].ffill().bfill()
    d["pop_log"] = np.log1p(d["pop"])

    # clima climatologico del UF de la ciudad
    clim = pd.read_csv(os.path.join(OUT, "uf_climate_climatology.csv"))
    d = d.merge(clim, on=["uf", "ew"], how="left")

    # nivel reciente EW18-25 del anio origen
    lvl = d[(d.ey == d.oy) & (d.ew.between(18, 25))].groupby(["geocode", "oy"])["casos"].mean()
    lvl = np.log1p(lvl).rename("level_log").reset_index()
    d = d.merge(lvl, on=["geocode", "oy"], how="left")
    lp = lvl.rename(columns={"level_log": "level_prev"}).assign(oy=lambda x: x.oy + 1)
    d = d.merge(lp[["geocode", "oy", "level_prev"]], on=["geocode", "oy"], how="left")
    d["level_log"] = d["level_log"].fillna(0)
    d["level_prev"] = d["level_prev"].fillna(d["level_log"])
    d["growth_yoy"] = d["level_log"] - d["level_prev"]

    seas = d.groupby(["geocode", "oy"])["casos"].sum().rename("st").reset_index()
    seas["prev_season_total_log"] = np.log1p(seas["st"])
    d = d.merge(seas.assign(oy=lambda x: x.oy + 1)[["geocode", "oy", "prev_season_total_log"]],
                on=["geocode", "oy"], how="left")
    d["prev_season_total_log"] = d["prev_season_total_log"].fillna(0)

    for k in (1, 2, 3):
        d[f"ew_sin{k}"] = np.sin(2 * np.pi * k * d.ew / 52)
        d[f"ew_cos{k}"] = np.cos(2 * np.pi * k * d.ew / 52)

    # clim_med expanding por (geocode, ew)
    piv = d.groupby(["geocode", "ew", "oy"])["casos"].mean().reset_index()
    parts = []
    for (g, ew), gg in piv.groupby(["geocode", "ew"]):
        gg = gg.sort_values("oy")
        med = gg["casos"].expanding().median().shift(1)
        parts.append(pd.DataFrame({"geocode": g, "ew": ew, "oy": gg.oy.values, "clim_med": med.values}))
    cm = pd.concat(parts, ignore_index=True)
    cm["clim_med_log"] = np.log1p(cm["clim_med"].fillna(cm["clim_med"].median()))
    d = d.merge(cm[["geocode", "ew", "oy", "clim_med_log"]], on=["geocode", "ew", "oy"], how="left")
    d["clim_med_log"] = d["clim_med_log"].fillna(np.log1p(d["casos"].median()))
    d["uf"] = d["uf"].astype("category")
    d["y"] = np.log1p(d["casos"])
    return d


def main():
    d = build_cities()
    res = []
    for tname, Y in T.TESTS:
        tr = d[d.oy < Y].dropna(subset=FEATS + ["y"])
        pr = d[(d.oy == Y) & (d.date.isin(T.season_dates(Y)))].copy()
        m = xgb.XGBRegressor(objective="reg:quantileerror", quantile_alpha=QUANTILES,
                             n_estimators=300, max_depth=4, learning_rate=0.05,
                             subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
                             enable_categorical=True, tree_method="hist", n_jobs=2)
        m.fit(tr[FEATS], tr["y"].values)
        q = np.sort(np.clip(np.expm1(m.predict(pr[FEATS])), 0, None), axis=1)
        r = pr[["geocode", "uf", "uf_code", "date"]].copy()
        for j, ql in enumerate(QUANTILES):
            r[QNAME[ql]] = q[:, j]
        r["validation_test"] = tname
        res.append(r)
        print(f"{tname}: train {len(tr)} pred {len(r)}", flush=True)
    out = pd.concat(res, ignore_index=True)
    out["unit_id"] = out["geocode"]; out["unit_name"] = out["geocode"].map(T.CITIES)
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    cols = ["unit_id", "unit_name", "uf", "geocode", "validation_test", "date",
            "pred", "lower_50", "upper_50", "lower_80", "upper_80",
            "lower_90", "upper_90", "lower_95", "upper_95"]
    out[cols].sort_values(["unit_id", "validation_test", "date"]).to_csv(
        os.path.join(OUT, "dengue_cities_validation_xgb.csv"), index=False)
    print("OK cities xgb", len(out), flush=True)


if __name__ == "__main__":
    main()
