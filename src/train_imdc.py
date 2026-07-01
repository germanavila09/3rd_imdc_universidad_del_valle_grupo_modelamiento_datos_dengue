"""
Entrenamiento IMDC 2026 - Pronostico de dengue.

Modelo: log1p(casos) -> Fourier (m=52, K armonicos) + AutoARIMA (errores ARIMA)
Enfoque estandar y rapido para estacionalidad anual semanal (evita el SARIMA m=52 lento).

Reto obligatorio  : dengue nivel estado (UF), todos menos Espirito Santo (ES).
Reto opcional 1   : dengue 15 ciudades objetivo.

Para cada unidad geografica y cada test de validacion:
  - entrena con datos EW01 2010 -> EW25 del anio Y (corte)
  - pronostica la temporada EW41 Y -> EW40 Y+1 (fechas domingo continuas)
  - genera mediana (q0.5) e intervalos 50/80/90/95%
Salida en formato Mosqlimate (date, pred, lower_x, upper_x) por unidad y test.

Uso:
  python src/train_imdc.py --level uf     --out outputs/predictions
  python src/train_imdc.py --level cities  --out outputs/predictions
"""
import argparse, os, sys, time, warnings, traceback
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

from epiweeks import Week
from pmdarima.pipeline import Pipeline
from pmdarima.preprocessing import FourierFeaturizer
from pmdarima.arima import AutoARIMA

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "dengue.csv.gz")

# 15 ciudades objetivo (reto opcional 1)
CITIES = {
    2931350: "Teixeira de Freitas (BA)", 2933307: "Vitoria da Conquista (BA)",
    2302503: "Brejo Santo (CE)", 3119401: "Coronel Fabriciano (MG)",
    3549805: "Sao Jose do Rio Preto (SP)", 3541406: "Presidente Prudente (SP)",
    1200401: "Rio Branco (AC)", 1200203: "Cruzeiro do Sul (AC)",
    1716109: "Paraiso do Tocantins (TO)", 4113700: "Londrina (PR)",
    4103701: "Cambe (PR)", 4104808: "Cascavel (PR)",
    5201405: "Aparecida de Goiania (GO)", 5102637: "Campo Novo do Parecis (MT)",
    5215231: "Novo Gama (GO)",
}

# 4 tests de validacion: (nombre, anio de corte Y). Corte = EW25 Y ; temporada = EW41 Y -> EW40 Y+1
TESTS = [("validation_1", 2022), ("validation_2", 2023),
         ("validation_3", 2024), ("validation_4", 2025)]

# niveles de intervalo -> alpha
INTERVALS = {50: 0.50, 80: 0.20, 90: 0.10, 95: 0.05}
QCOLS = ["lower_95", "lower_90", "lower_80", "lower_50", "pred",
         "upper_50", "upper_80", "upper_90", "upper_95"]


def ew_sunday(year, week):
    """Domingo de inicio de la semana epidemiologica CDC (EW empieza en domingo)."""
    return pd.Timestamp(Week(year, week, system="cdc").startdate())


def season_dates(y):
    """Lista continua de domingos EW41 de Y hasta EW40 de Y+1 (inclusive)."""
    start = ew_sunday(y, 41)
    # EW40 del anio siguiente
    end = ew_sunday(y + 1, 40)
    dates = pd.date_range(start=start, end=end, freq="7D")
    return dates


def cutoff_date(y):
    return ew_sunday(y, 25)


def load_series(level):
    """Devuelve dict {unit_id: (meta_dict, serie pd.Series indexada por fecha semanal)}."""
    if level == "uf":
        d = pd.read_csv(DATA, usecols=["date", "casos", "uf", "uf_code"])
        d["date"] = pd.to_datetime(d["date"])
        units = {}
        for (uf, code), g in d.groupby(["uf", "uf_code"]):
            if uf == "ES":
                continue  # excluido del reto
            s = g.groupby("date")["casos"].sum().sort_index().asfreq("7D").fillna(0)
            units[uf] = ({"level": "state", "uf": uf, "uf_code": int(code),
                          "unit_id": uf, "unit_name": uf}, s)
        return units
    else:  # cities
        d = pd.read_csv(DATA, usecols=["date", "casos", "geocode", "uf"])
        d = d[d.geocode.isin(CITIES)].copy()
        d["date"] = pd.to_datetime(d["date"])
        units = {}
        for (gc, uf), g in d.groupby(["geocode", "uf"]):
            s = g.groupby("date")["casos"].sum().sort_index().asfreq("7D").fillna(0)
            units[str(gc)] = ({"level": "city", "geocode": int(gc), "uf": uf,
                               "unit_id": int(gc), "unit_name": CITIES[gc]}, s)
        return units


def climatological_forecast(train, target_dates):
    """Fallback: cuantiles empiricos por semana epidemiologica (robusto, nunca falla)."""
    df = pd.DataFrame({"casos": train.values}, index=train.index)
    df["ew"] = [Week.fromdate(d.date(), system="cdc").week for d in df.index]
    out = {}
    for lvl, a in list(INTERVALS.items()):
        lo, hi = a / 2, 1 - a / 2
        out[f"lower_{lvl}"] = []
        out[f"upper_{lvl}"] = []
    med = []
    for d in target_dates:
        ew = Week.fromdate(d.date(), system="cdc").week
        vals = df.loc[df.ew == ew, "casos"].values
        if len(vals) == 0:
            vals = df["casos"].values
        med.append(np.quantile(vals, 0.5))
        for lvl, a in INTERVALS.items():
            out[f"lower_{lvl}"].append(np.quantile(vals, a / 2))
            out[f"upper_{lvl}"].append(np.quantile(vals, 1 - a / 2))
    res = pd.DataFrame({"date": target_dates, "pred": med})
    for k, v in out.items():
        res[k] = v
    return res, "climatological"


def arima_forecast(train, cutoff, target_dates):
    """log1p + Fourier(m=52) + AutoARIMA. Devuelve df formato Mosqlimate."""
    y = np.log1p(train.values.astype(float))
    n = len(y)
    k = 4 if n > 120 else 2
    pipe = Pipeline([
        ("fourier", FourierFeaturizer(m=52, k=k)),
        ("arima", AutoARIMA(seasonal=False, stepwise=True, suppress_warnings=True,
                            error_action="ignore", max_p=2, max_q=2, max_d=1,
                            max_order=5, trace=False)),
    ])
    pipe.fit(y)
    # horizonte: desde el domingo siguiente al corte hasta la ultima fecha objetivo
    first_future = cutoff + pd.Timedelta(days=7)
    horizon = int((target_dates[-1] - first_future).days / 7) + 1
    idx = [(int((d - first_future).days / 7)) for d in target_dates]  # posicion 0-based
    res = {"date": target_dates}
    # mediana
    fc = np.asarray(pipe.predict(n_periods=horizon))
    res["pred"] = np.expm1(fc)[idx]
    for lvl, a in INTERVALS.items():
        _, ci = pipe.predict(n_periods=horizon, return_conf_int=True, alpha=a)
        ci = np.asarray(ci)
        res[f"lower_{lvl}"] = np.expm1(ci[idx, 0])
        res[f"upper_{lvl}"] = np.expm1(ci[idx, 1])
    df = pd.DataFrame(res)
    order = pipe.named_steps["arima"].model_.order
    return df, f"arima{order}_fourierK{k}"


def enforce_rules(df):
    """No negativos + intervalos anidados: l95<=l90<=l80<=l50<=pred<=u50<=u80<=u90<=u95."""
    for c in QCOLS:
        df[c] = np.clip(df[c].astype(float), 0, None)
    # ordena limites inferiores ascendente hasta pred y superiores descendente desde pred
    lowers = ["lower_95", "lower_90", "lower_80", "lower_50"]
    uppers = ["upper_50", "upper_80", "upper_90", "upper_95"]
    L = df[lowers].values
    L = np.maximum.accumulate(L, axis=1)            # no decreciente
    L = np.minimum(L, df["pred"].values[:, None])   # <= pred
    df[lowers] = L
    U = df[uppers].values
    U = np.maximum.accumulate(U, axis=1)            # no decreciente (u50<=u80<=..)
    U = np.maximum(U, df["pred"].values[:, None])   # >= pred
    df[uppers] = U
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", choices=["uf", "cities"], default="uf")
    ap.add_argument("--out", default="outputs/predictions")
    args = ap.parse_args()
    outdir = os.path.join(os.path.dirname(__file__), "..", args.out)
    os.makedirs(outdir, exist_ok=True)

    units = load_series(args.level)
    print(f"[{args.level}] unidades: {len(units)} | tests: {len(TESTS)} | total corridas: {len(units)*len(TESTS)}", flush=True)

    all_rows = []
    t0 = time.time()
    done = 0
    total = len(units) * len(TESTS)
    for uid, (meta, s) in units.items():
        for tname, y in TESTS:
            cut = cutoff_date(y)
            tgt = season_dates(y)
            train = s[s.index <= cut].dropna()
            train = train[train > -1]  # todo
            method = ""
            try:
                if len(train) < 60 or train.sum() < 10:
                    df, method = climatological_forecast(train, tgt)
                else:
                    df, method = arima_forecast(train, cut, tgt)
                    # si el ARIMA colapsa a algo degenerado, respaldo
                    if not np.isfinite(df[QCOLS].values).all():
                        df, method = climatological_forecast(train, tgt)
            except Exception as e:
                df, method = climatological_forecast(train, tgt)
                method += "_fallback"
            df = enforce_rules(df)
            df.insert(0, "validation_test", tname)
            for k, v in meta.items():
                df[k] = v
            df["method"] = method
            all_rows.append(df)
            done += 1
            el = time.time() - t0
            eta = el / done * (total - done)
            print(f"  [{done}/{total}] {uid} {tname} -> {method} | {el:.0f}s ETA {eta:.0f}s", flush=True)

    out = pd.concat(all_rows, ignore_index=True)
    cols = ["level", "unit_id", "unit_name", "uf", "validation_test", "date",
            "pred", "lower_50", "upper_50", "lower_80", "upper_80",
            "lower_90", "upper_90", "lower_95", "upper_95", "method"]
    cols = [c for c in cols if c in out.columns] + [c for c in out.columns if c not in cols]
    out = out[cols]
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    fn = os.path.join(outdir, f"dengue_{args.level}_validation.csv")
    out.to_csv(fn, index=False)
    print(f"OK -> {fn} | filas {len(out)} | tiempo {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
