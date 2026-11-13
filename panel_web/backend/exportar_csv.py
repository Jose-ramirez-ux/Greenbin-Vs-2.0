"""
GreenBin - Exporta las clasificaciones guardadas en greenbin.db a CSV.

Funciona sin el backend encendido (lee la base SQLite directamente) y también
lo usa el backend para el botón "Exportar CSV" del panel.

Uso (desde la carpeta backend/):
    python exportar_csv.py                         -> resultados_AAAA-MM-DD.csv (para Excel)
    python exportar_csv.py --desde 2026-11-10      -> solo desde esa fecha
    python exportar_csv.py --estandar              -> separador "," y punto decimal (Python, R)

Columnas vacías al final (residuo_real, caneca_correcta, acierto, observaciones)
para completarlas a mano con la planilla de observación.
"""

import argparse
import csv
import io
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
DB = Path(os.environ.get("GREENBIN_DB", AQUI / "greenbin.db"))

CANECA = {"aprovechable": "blanca", "no_aprovechable": "negra", "organico": "verde"}
COLUMNAS = ["id", "fecha", "hora", "dispositivo", "categoria", "caneca", "confianza", "estado",
            "tiempo_s", "residuo_real", "caneca_correcta", "acierto", "observaciones"]


def filas(db=DB, desde=None, hasta=None):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    cols = {r[1] for r in con.execute("PRAGMA table_info(clasificaciones)")}
    tiempo = "tiempo_s" if "tiempo_s" in cols else "NULL AS tiempo_s"
    sql, args = f"SELECT id, dispositivo_id, momento, fecha, categoria, confianza, estado, {tiempo} FROM clasificaciones WHERE 1=1", []
    if desde:
        sql += " AND fecha >= ?"; args.append(desde)
    if hasta:
        sql += " AND fecha <= ?"; args.append(hasta)
    for r in con.execute(sql + " ORDER BY momento, id", args):
        yield {"id": r["id"], "fecha": r["fecha"], "hora": datetime.fromisoformat(r["momento"]).strftime("%H:%M:%S"),
               "dispositivo": r["dispositivo_id"], "categoria": r["categoria"],
               "caneca": CANECA.get(r["categoria"], ""), "confianza": round(r["confianza"], 4),
               "estado": r["estado"], "tiempo_s": r["tiempo_s"]}
    con.close()


def a_csv(registros, excel=True) -> str:
    """excel=True: ';' y coma decimal (Excel en español). False: ',' y punto decimal."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNAS, delimiter=";" if excel else ",", extrasaction="ignore")
    w.writeheader()
    for r in registros:
        if excel:
            r = {k: (str(v).replace(".", ",") if isinstance(v, float) else v) for k, v in r.items()}
        w.writerow({k: ("" if r.get(k) is None else r.get(k, "")) for k in COLUMNAS})
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde"), ap.add_argument("--hasta")
    ap.add_argument("--estandar", action="store_true", help="separador ',' y punto decimal")
    ap.add_argument("--salida")
    a = ap.parse_args()
    texto = a_csv(filas(desde=a.desde, hasta=a.hasta), excel=not a.estandar)
    salida = Path(a.salida or f"resultados_{date.today():%Y-%m-%d}.csv")
    salida.write_text(texto, encoding="utf-8-sig")       # con BOM: Excel respeta las tildes
    print(f"[OK] {texto.count(chr(10)) - 1} clasificaciones -> {salida.resolve()}")


if __name__ == "__main__":
    main()
