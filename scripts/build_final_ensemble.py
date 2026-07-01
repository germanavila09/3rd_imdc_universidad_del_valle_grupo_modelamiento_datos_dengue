"""
Construye la submission final combinando 3 modelos (ensamble ganador por WIS):
  0.4 * XGBoost cuantilico  +  0.4 * climatologico estacional  +  0.2 * AutoARIMA
y aplica un TOPE por unidad a los limites superiores (cap = MULT x maximo semanal
historico hasta el corte) para evitar que la cola log del ARIMA explote en
horizontes largos. El tope reduce el WIS y mantiene la calibracion.

Resultados de validacion (WIS medio UF):
  AutoARIMA 3191 | Climatologico 1368 | XGBoost 1462
  Ensamble 0.4/0.4/0.2 sin tope 1356 -> con tope 3x = 1214  (IC50=59%, IC95=94%)
  Ciudades: ensamble con tope ~ WIS 120

Uso: python scripts/build_final_ensemble.py --level uf     (o cities)
Salida: outputs/predictions/FINAL_dengue_{level}.csv
"""
import os, sys, argparse
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import train_imdc as T

QC = ["pred", "lower_50", "upper_50", "lower_80", "upper_80",
      "lower_90", "upper_90", "lower_95", "upper_95"]
UP = ["upper_50", "upper_80", "upper_90", "upper_95"]
KEY = ["unit_id", "validation_test", "date"]
OUT = os.path.join(os.path.dirname(__file__), "..", "outputs", "predictions")
W_XGB, W_CLIM, W_ARIMA = 0.4, 0.4, 0.2
CAP_MULT = 3.0


def climatological(level):
    units = T.load_series(level)
    rows = []
    for uid, (meta, s) in units.items():
        for tn, yy in T.TESTS:
            cut = T.cutoff_date(yy); tgt = T.season_dates(yy)
            df, _ = T.climatological_forecast(s[s.index <= cut].dropna(), tgt)
            df = T.enforce_rules(df)
            df["unit_id"] = uid if level == "uf" else int(uid)
            df["validation_test"] = tn
            rows.append(df)
    c = pd.concat(rows); c["date"] = pd.to_datetime(c["date"])
    return c, units


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", choices=["uf", "cities"], default="uf")
    args = ap.parse_args(); lvl = args.level

    ar = pd.read_csv(os.path.join(OUT, f"dengue_{lvl}_validation.csv")); ar["date"] = pd.to_datetime(ar["date"])
    xg = pd.read_csv(os.path.join(OUT, f"dengue_{lvl}_validation_xgb.csv")); xg["date"] = pd.to_datetime(xg["date"])
    if "uf" in xg.columns and "unit_id" not in xg.columns:
        xg = xg.rename(columns={"uf": "unit_id"})
    cl, units = climatological(lvl)
    # normalizar tipos de unit_id
    for df in (ar, xg, cl):
        df["unit_id"] = df["unit_id"].astype(str)

    idx = ar.set_index(KEY).index
    A = ar.set_index(KEY)[QC].reindex(idx)
    C = cl.set_index(KEY)[QC].reindex(idx)
    X = xg.set_index(KEY)[QC].reindex(idx).fillna(C)
    E = pd.DataFrame(index=idx)
    for c in QC:
        E[c] = W_XGB * X[c].values + W_CLIM * C[c].values + W_ARIMA * A[c].values
    E = E.reset_index()

    # tope por (unidad, test): CAP_MULT x maximo semanal historico hasta el corte
    capmap = {}
    for uid, (meta, s) in units.items():
        u = uid if lvl == "uf" else str(uid)
        for tn, yy in T.TESTS:
            capmap[(u, tn)] = float(s[s.index <= T.cutoff_date(yy)].max()) * CAP_MULT
    caps = E.apply(lambda r: capmap.get((str(r["unit_id"]), r["validation_test"]), np.inf), axis=1).values
    for c in UP:
        E[c] = np.minimum(E[c].values, np.maximum(caps, E["pred"].values))
    E = T.enforce_rules(E)

    # metadatos de salida
    if lvl == "uf":
        E["level"] = "state"; E["unit_name"] = E["unit_id"]; E["uf"] = E["unit_id"]
        E = E.merge(ar[["unit_id", "uf_code"]].drop_duplicates(), on="unit_id", how="left")
        cols = ["level", "unit_id", "unit_name", "uf", "uf_code", "validation_test", "date"] + QC
    else:
        E["unit_name"] = E["unit_id"].astype(int).map(T.CITIES)
        E = E.merge(ar[["unit_id", "uf"]].drop_duplicates(), on="unit_id", how="left")
        E["geocode"] = E["unit_id"]
        cols = ["unit_id", "unit_name", "uf", "geocode", "validation_test", "date"] + QC
    E["date"] = pd.to_datetime(E["date"]).dt.strftime("%Y-%m-%d")
    E = E[cols].sort_values(["unit_id", "validation_test", "date"])
    fn = os.path.join(OUT, f"FINAL_dengue_{lvl}.csv")
    E.to_csv(fn, index=False)
    print(f"OK -> {fn} | filas {len(E)} | pesos {W_XGB}/{W_CLIM}/{W_ARIMA} | tope x{CAP_MULT}")


if __name__ == "__main__":
    main()
