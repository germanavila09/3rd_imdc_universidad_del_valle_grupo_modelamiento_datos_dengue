"""
Subida de predicciones a la plataforma Mosqlimate (IMDC 2026) via mosqlient.

Envia, por cada unidad geografica y cada test de validacion, el dataframe de
prediccion (date, pred, lower/upper_50/80/90/95) usando `upload_prediction`.

Credenciales y metadatos se leen de un archivo .env en la raiz del proyecto:
  API_KEY=xxxxxxxx
  REPOSITORY=tu_usuario/3rd_imdc_univalle_nombre
  COMMIT=<hash_de_commit_git>

Uso:
  python scripts/submit_mosqlient.py --level uf --dry-run     # valida sin subir
  python scripts/submit_mosqlient.py --level uf               # sube de verdad
  python scripts/submit_mosqlient.py --level cities

Notas:
  - disease 'A90' = dengue (CID-10). case_definition = 'probable' (requerido por el IMDC).
  - Estado (UF): adm_level=1, adm_1=uf_code.
  - Ciudad:      adm_level=2, adm_1=uf_code (2 primeros digitos del geocode), adm_2=geocode.
  - Se sube un dataframe por (unidad, test). Ajusta 'description' segun tu criterio.
"""
import os, sys, argparse, time
import pandas as pd

PREDCOLS = ["date", "pred", "lower_50", "upper_50", "lower_80", "upper_80",
            "lower_90", "upper_90", "lower_95", "upper_95"]
OUT = os.path.join(os.path.dirname(__file__), "..", "outputs", "predictions")
ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_env():
    env = {}
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", choices=["uf", "cities"], default="uf")
    ap.add_argument("--dry-run", action="store_true", help="valida y muestra sin subir")
    ap.add_argument("--description", default="Ensamble XGBoost+climatologico+AutoARIMA con tope (IMDC 2026, UniValle)")
    args = ap.parse_args()

    env = load_env()
    api_key = env.get("API_KEY"); repository = env.get("REPOSITORY"); commit = env.get("COMMIT")

    df = pd.read_csv(os.path.join(OUT, f"FINAL_dengue_{args.level}.csv"))
    groups = list(df.groupby(["unit_id", "validation_test"]))
    print(f"[{args.level}] {len(groups)} envios (unidad x test) | dry_run={args.dry_run}")

    if not args.dry_run:
        if not all([api_key, repository, commit]):
            sys.exit("ERROR: faltan API_KEY / REPOSITORY / COMMIT en .env")
        from mosqlient import upload_prediction

    ok = 0
    for (uid, test), g in groups:
        g = g.sort_values("date")
        pred = g[PREDCOLS].reset_index(drop=True)
        # validaciones minimas antes de enviar
        assert (pd.to_datetime(pred.date).dt.weekday == 6).all(), f"{uid} {test}: fechas no-domingo"
        assert (pred[PREDCOLS[1:]] >= 0).all().all(), f"{uid} {test}: valores negativos"
        if args.level == "uf":
            adm_level, adm_1, adm_2 = 1, int(g["uf_code"].iloc[0]), None
        else:
            gc = int(g["geocode"].iloc[0]); adm_level, adm_1, adm_2 = 2, int(str(gc)[:2]), gc
        if args.dry_run:
            if ok < 3:
                print(f"  [DRY] {uid} {test} adm_level={adm_level} adm_1={adm_1} adm_2={adm_2} filas={len(pred)}")
            ok += 1
            continue
        res = upload_prediction(
            api_key=api_key, repository=repository, description=f"{args.description} | {test}",
            commit=commit, disease="A90", case_definition="probable",
            adm_level=adm_level, adm_1=adm_1, adm_2=adm_2, published=True, prediction=pred)
        print(f"  {uid} {test}: {res}")
        ok += 1
        time.sleep(0.5)
    print(f"{'validados' if args.dry_run else 'subidos'}: {ok}/{len(groups)}")


if __name__ == "__main__":
    main()
