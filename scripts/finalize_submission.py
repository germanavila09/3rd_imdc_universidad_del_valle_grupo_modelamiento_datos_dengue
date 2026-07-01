"""
Genera la submission final IMDC combinando (ensamble) el modelo AutoARIMA
con el baseline climatologico estacional. El ensamble es mas robusto y
mejor calibrado que cualquiera de los dos por separado (evita la
sobre-extrapolacion del ARIMA tras epidemias extremas).

pred_final = w*ARIMA + (1-w)*climatologico   (por cuantil)
Por defecto w=0.30 (30% ARIMA / 70% climatologico).

Salida: outputs/predictions/FINAL_dengue_{level}.csv
"""
import argparse, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import train_imdc as T

QC = ["pred", "lower_50", "upper_50", "lower_80", "upper_80",
      "lower_90", "upper_90", "lower_95", "upper_95"]
OUT = os.path.join(os.path.dirname(__file__), "..", "outputs", "predictions")


def climatological_all(level):
    units = T.load_series(level)
    rows = []
    for uid, (meta, s) in units.items():
        for tn, yy in T.TESTS:
            cut = T.cutoff_date(yy); tgt = T.season_dates(yy)
            tr = s[s.index <= cut].dropna()
            df, _ = T.climatological_forecast(tr, tgt)
            df = T.enforce_rules(df)
            df["validation_test"] = tn
            for k, v in meta.items():
                df[k] = v
            rows.append(df)
    c = pd.concat(rows, ignore_index=True)
    c["date"] = pd.to_datetime(c["date"]).dt.strftime("%Y-%m-%d")
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", choices=["uf", "cities"], default="uf")
    ap.add_argument("--w", type=float, default=0.30, help="peso del ARIMA en el ensamble")
    args = ap.parse_args()

    ar = pd.read_csv(os.path.join(OUT, f"dengue_{args.level}_validation.csv"))
    cl = climatological_all(args.level)
    key = ["unit_id", "validation_test", "date"]
    merged = ar[key + QC + ["unit_name", "uf"]].merge(
        cl[key + QC], on=key, suffixes=("_a", "_c"))
    for c in QC:
        merged[c] = args.w * merged[c + "_a"] + (1 - args.w) * merged[c + "_c"]
    # reforzar reglas tras el promedio
    merged = T.enforce_rules(merged)
    cols = ["unit_id", "unit_name", "uf", "validation_test", "date"] + QC
    out = merged[cols].sort_values(["unit_id", "validation_test", "date"])
    fn = os.path.join(OUT, f"FINAL_dengue_{args.level}.csv")
    out.to_csv(fn, index=False)
    print(f"OK -> {fn} | filas {len(out)} | w_arima={args.w}")


if __name__ == "__main__":
    main()
