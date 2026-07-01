"""
Runner reanudable y por lotes para el entrenamiento IMDC.
Procesa combinaciones (unidad x test) con presupuesto de tiempo y 2 workers.
Escribe un archivo parcial por combo en outputs/predictions/parts/ y se salta
los ya hechos, de modo que se puede invocar repetidamente hasta completar.

Uso:
  python scripts/run_batch.py --level uf --max-seconds 40
  python scripts/run_batch.py --level cities --max-seconds 40
Al terminar todos, consolida en dengue_{level}_validation.csv
"""
import argparse, os, sys, time, glob
# limitar hilos BLAS para evitar sobre-suscripcion con 2 workers en 2 cores
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
import numpy as np, pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import train_imdc as T

PARTS = os.path.join(HERE, "..", "outputs", "predictions", "parts")
OUTDIR = os.path.join(HERE, "..", "outputs", "predictions")


def part_path(level, uid, tname):
    return os.path.join(PARTS, f"{level}__{uid}__{tname}.csv")


def run_one(args):
    level, uid, meta, s, tname, y = args
    cut = T.cutoff_date(y)
    tgt = T.season_dates(y)
    train = s[s.index <= cut].dropna()
    try:
        if len(train) < 60 or train.sum() < 10:
            df, method = T.climatological_forecast(train, tgt)
        else:
            df, method = T.arima_forecast(train, cut, tgt)
            if not np.isfinite(df[T.QCOLS].values).all():
                df, method = T.climatological_forecast(train, tgt)
    except Exception:
        df, method = T.climatological_forecast(train, tgt)
        method += "_fallback"
    df = T.enforce_rules(df)
    df.insert(0, "validation_test", tname)
    for k, v in meta.items():
        df[k] = v
    df["method"] = method
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df.to_csv(part_path(level, uid, tname), index=False)
    return f"{uid} {tname} -> {method}"


def consolidate(level):
    files = sorted(glob.glob(os.path.join(PARTS, f"{level}__*.csv")))
    out = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    cols = ["level", "unit_id", "unit_name", "uf", "validation_test", "date",
            "pred", "lower_50", "upper_50", "lower_80", "upper_80",
            "lower_90", "upper_90", "lower_95", "upper_95", "method"]
    cols = [c for c in cols if c in out.columns] + [c for c in out.columns if c not in cols]
    fn = os.path.join(OUTDIR, f"dengue_{level}_validation.csv")
    out[cols].to_csv(fn, index=False)
    return fn, len(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", choices=["uf", "cities"], default="uf")
    ap.add_argument("--max-seconds", type=int, default=40)
    ap.add_argument("--max-combos", type=int, default=0, help="procesar N combos y salir (0=usar tiempo)")
    args = ap.parse_args()
    os.makedirs(PARTS, exist_ok=True)

    units = T.load_series(args.level)
    combos = [(uid, meta, s, tname, y)
              for uid, (meta, s) in units.items()
              for tname, y in T.TESTS]
    pending = [c for c in combos
               if not os.path.exists(part_path(args.level, c[0], c[3]))]
    total = len(combos)
    done0 = total - len(pending)
    print(f"[{args.level}] total {total} | hechos {done0} | pendientes {len(pending)}", flush=True)

    if not pending:
        fn, n = consolidate(args.level)
        print(f"COMPLETO -> {fn} ({n} filas)", flush=True)
        return

    t0 = time.time()
    processed = 0
    if args.max_combos > 0:
        pending = pending[:args.max_combos]
    tasks = [(args.level, uid, meta, s, tname, y) for (uid, meta, s, tname, y) in pending]
    with ProcessPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(run_one, tk): tk for tk in tasks}
        for fut in as_completed(futs):
            try:
                msg = fut.result()
                processed += 1
                print(f"  [{done0+processed}/{total}] {msg}", flush=True)
            except Exception as e:
                print(f"  ERROR: {e}", flush=True)
            if args.max_combos == 0 and time.time() - t0 > args.max_seconds:
                for f in futs:
                    f.cancel()
                break
    # recomputar pendientes globales (no solo del lote)
    global_pending = [c for c in combos
                      if not os.path.exists(part_path(args.level, c[0], c[3]))]
    print(f"lote: procesados {processed} en {time.time()-t0:.0f}s | pendientes globales {len(global_pending)}", flush=True)
    if not global_pending:
        fn, n = consolidate(args.level)
        print(f"COMPLETO -> {fn} ({n} filas)", flush=True)


if __name__ == "__main__":
    main()
