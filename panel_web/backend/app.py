"""
GreenBin - Backend local del panel web (FastAPI + SQLite)

Recibe de la Raspberry Pi solo el RESULTADO de cada clasificación (categoría,
confianza, estado y hora). Nunca recibe imágenes (RNF-05).
Guarda los eventos en SQLite, los reenvía en vivo al panel por WebSocket y sirve
la versión compilada del panel Angular.

Ejecutar (desde la carpeta backend/):
    pip install -r requirements.txt
    set GREENBIN_TOKEN=una-clave-larga        (Windows; en Linux: export ...)
    uvicorn app:app --host 0.0.0.0 --port 8000

Rutas:
    POST /api/clasificaciones          (Pi, con cabecera X-GreenBin-Token)
    POST /api/clasificaciones/lote     (Pi, envía las pendientes cuando no hubo red)
    POST /api/latido                   (Pi, cada 30 s: dispositivo en línea)
    GET  /api/clasificaciones?limite=20
    GET  /api/metricas
    GET  /api/historial?dias=7
    GET  /api/dispositivos
    GET  /api/exportar.csv?desde=AAAA-MM-DD&hasta=...&formato=excel|estandar
    GET  /api/salud
    WS   /ws/eventos                   (panel: clasificaciones y estado en vivo)
"""

import asyncio
import json
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from exportar_csv import a_csv, filas

AQUI = Path(__file__).resolve().parent
DB = Path(os.environ.get("GREENBIN_DB", AQUI / "greenbin.db"))
TOKEN = os.environ.get("GREENBIN_TOKEN", "")
PANEL = Path(os.environ.get("GREENBIN_PANEL_DIR", AQUI.parent / "dist" / "greenbin-panel" / "browser"))
EN_LINEA_S = 90              # sin latido en este tiempo, el dispositivo pasa a "sin conexión"
DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

Categoria = Literal["organico", "aprovechable", "no_aprovechable"]


# ───────────────────────────── Base de datos ─────────────────────────────
def conectar():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def crear_tablas():
    with closing(conectar()) as con, con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS clasificaciones (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            dispositivo_id TEXT NOT NULL,
            momento        TEXT NOT NULL,          -- ISO 8601, hora local de la Pi
            fecha          TEXT NOT NULL,          -- AAAA-MM-DD
            categoria      TEXT NOT NULL,
            confianza      REAL NOT NULL,
            estado         TEXT NOT NULL,          -- seguro | dudoso
            UNIQUE (dispositivo_id, momento)       -- evita duplicados al reenviar pendientes
        );
        CREATE INDEX IF NOT EXISTS ix_clas_fecha ON clasificaciones (fecha);
        CREATE TABLE IF NOT EXISTS dispositivos (
            id            TEXT PRIMARY KEY,
            nombre        TEXT NOT NULL,
            ubicacion     TEXT NOT NULL,
            modelo        TEXT NOT NULL,
            umbral        REAL NOT NULL,
            ultimo_latido TEXT
        );
        """)
        # Bases creadas antes de guardar el tiempo de respuesta: se agrega la columna
        if "tiempo_s" not in {r[1] for r in con.execute("PRAGMA table_info(clasificaciones)")}:
            con.execute("ALTER TABLE clasificaciones ADD COLUMN tiempo_s REAL")


# ───────────────────────────── Modelos ─────────────────────────────
class EventoClasificacion(BaseModel):
    dispositivo_id: str = Field(min_length=1, max_length=40)
    momento: datetime
    categoria: Categoria
    confianza: float = Field(ge=0, le=1)
    estado: Literal["seguro", "dudoso"]
    tiempo_s: Optional[float] = Field(None, ge=0, le=120)   # tiempo de clasificación en la Pi (PR-08)


class Latido(BaseModel):
    dispositivo_id: str = Field(min_length=1, max_length=40)
    nombre: str = Field(max_length=60)
    ubicacion: str = Field(max_length=80)
    modelo: str = Field(max_length=80)
    umbral: float = Field(ge=0, le=1)


def verificar_token(token: Optional[str]):
    if TOKEN and token != TOKEN:
        raise HTTPException(status_code=401, detail="token inválido")


# ───────────────────────────── WebSocket ─────────────────────────────
class Difusor:
    def __init__(self):
        self.clientes: set[WebSocket] = set()

    async def conectar(self, ws: WebSocket):
        await ws.accept()
        self.clientes.add(ws)

    def desconectar(self, ws: WebSocket):
        self.clientes.discard(ws)

    async def enviar(self, mensaje: dict):
        texto = json.dumps(mensaje, ensure_ascii=False)
        for ws in list(self.clientes):
            try:
                await ws.send_text(texto)
            except Exception:
                self.desconectar(ws)


difusor = Difusor()
app = FastAPI(title="GreenBin API", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:4200"],
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def inicio():
    crear_tablas()
    asyncio.create_task(vigilar_dispositivos())


def fila_a_json(f: sqlite3.Row, nombres: dict) -> dict:
    return {"id": f["id"], "timestamp": f["momento"], "dispositivoId": f["dispositivo_id"],
            "dispositivoNombre": nombres.get(f["dispositivo_id"], f["dispositivo_id"]),
            "categoria": f["categoria"], "confianza": f["confianza"], "estado": f["estado"],
            "tiempoS": f["tiempo_s"]}


def nombres_dispositivos(con) -> dict:
    return {r["id"]: r["nombre"] for r in con.execute("SELECT id, nombre FROM dispositivos")}


def guardar(con, e: EventoClasificacion) -> Optional[int]:
    m = e.momento.astimezone() if e.momento.tzinfo else e.momento     # a la hora local de este PC
    momento = m.isoformat(timespec="seconds")
    cur = con.execute(
        "INSERT OR IGNORE INTO clasificaciones (dispositivo_id, momento, fecha, categoria, confianza, estado, tiempo_s) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (e.dispositivo_id, momento, m.date().isoformat(), e.categoria, round(e.confianza, 4), e.estado,
         None if e.tiempo_s is None else round(e.tiempo_s, 3)))
    return cur.lastrowid if cur.rowcount else None


# ───────────────────────────── Rutas de la Pi ─────────────────────────────
@app.post("/api/clasificaciones", status_code=201)
async def recibir(e: EventoClasificacion, x_greenbin_token: Optional[str] = Header(None)):
    verificar_token(x_greenbin_token)
    with closing(conectar()) as con, con:
        nuevo = guardar(con, e)
        if nuevo:
            f = con.execute("SELECT * FROM clasificaciones WHERE id = ?", (nuevo,)).fetchone()
            await difusor.enviar({"tipo": "clasificacion", "datos": fila_a_json(f, nombres_dispositivos(con))})
    return {"ok": True, "duplicado": nuevo is None}


@app.post("/api/clasificaciones/lote")
async def recibir_lote(eventos: list[EventoClasificacion], x_greenbin_token: Optional[str] = Header(None)):
    verificar_token(x_greenbin_token)
    with closing(conectar()) as con, con:
        nuevos = sum(1 for e in eventos[:5000] if guardar(con, e))
    if nuevos:
        await difusor.enviar({"tipo": "actualizar"})
    return {"ok": True, "nuevos": nuevos}


@app.post("/api/latido")
async def latido(l: Latido, x_greenbin_token: Optional[str] = Header(None)):
    verificar_token(x_greenbin_token)
    with closing(conectar()) as con, con:
        antes = con.execute("SELECT ultimo_latido FROM dispositivos WHERE id = ?", (l.dispositivo_id,)).fetchone()
        con.execute(
            "INSERT INTO dispositivos (id, nombre, ubicacion, modelo, umbral, ultimo_latido) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET nombre=excluded.nombre, ubicacion=excluded.ubicacion, "
            "modelo=excluded.modelo, umbral=excluded.umbral, ultimo_latido=excluded.ultimo_latido",
            (l.dispositivo_id, l.nombre, l.ubicacion, l.modelo, l.umbral, datetime.now().isoformat(timespec="seconds")))
    if antes is None or not en_linea(antes["ultimo_latido"]):
        await difusor.enviar({"tipo": "dispositivo"})       # pasó a "en línea"
    return {"ok": True}


def en_linea(ultimo: Optional[str]) -> bool:
    return bool(ultimo) and (datetime.now() - datetime.fromisoformat(ultimo)).total_seconds() < EN_LINEA_S


async def vigilar_dispositivos():
    """Avisa al panel cuando un dispositivo deja de enviar latidos."""
    estados: dict = {}
    while True:
        await asyncio.sleep(15)
        with closing(conectar()) as con:
            actual = {r["id"]: en_linea(r["ultimo_latido"]) for r in con.execute("SELECT * FROM dispositivos")}
        if any(estados.get(k) != v for k, v in actual.items()):
            await difusor.enviar({"tipo": "dispositivo"})
        estados = actual


# ───────────────────────────── Rutas del panel ─────────────────────────────
@app.get("/api/salud")
def salud():
    return {"ok": True, "hora": datetime.now().isoformat(timespec="seconds")}


@app.get("/api/clasificaciones")
def ultimas(limite: int = Query(20, ge=1, le=500)):
    with closing(conectar()) as con:
        n = nombres_dispositivos(con)
        filas = con.execute("SELECT * FROM clasificaciones ORDER BY momento DESC, id DESC LIMIT ?", (limite,))
        return [fila_a_json(f, n) for f in filas]


def resumen_dia(con, dia: str) -> dict:
    f = con.execute("""SELECT COUNT(*) total, AVG(confianza) conf,
                       SUM(estado = 'dudoso') dudosas,
                       SUM(categoria = 'organico') organico,
                       SUM(categoria = 'aprovechable') aprovechable,
                       SUM(categoria = 'no_aprovechable') no_aprovechable
                       FROM clasificaciones WHERE fecha = ?""", (dia,)).fetchone()
    return {k: (f[k] or 0) for k in f.keys()}


@app.get("/api/metricas")
def metricas():
    hoy, ayer = date.today(), date.today() - timedelta(days=1)
    with closing(conectar()) as con:
        h, a = resumen_dia(con, hoy.isoformat()), resumen_dia(con, ayer.isoformat())
        disp = con.execute("SELECT ultimo_latido FROM dispositivos").fetchall()
        total = con.execute("SELECT COUNT(*) FROM clasificaciones").fetchone()[0]
    t = h["total"]
    return {
        "clasificacionesHoy": t,
        "clasificacionesAyer": a["total"],
        "variacionVsAyer": round((t - a["total"]) / a["total"] * 100) if a["total"] else None,
        "confianzaPromedio": h["conf"],
        "dispositivosActivos": sum(en_linea(d["ultimo_latido"]) for d in disp),
        "dispositivosTotal": len(disp),
        "prediccionesDudosas": h["dudosas"],
        "pctDudosas": round(h["dudosas"] / t * 100) if t else 0,
        "distribucion": {c: (round(h[c] / t * 100, 1) if t else 0)
                         for c in ("organico", "aprovechable", "no_aprovechable")},
        "totalHistorico": total,
    }


@app.get("/api/historial")
def historial(dias: int = Query(7, ge=1, le=60)):
    hoy = date.today()
    with closing(conectar()) as con:
        salida = []
        for k in range(dias - 1, -1, -1):
            d = hoy - timedelta(days=k)
            r = resumen_dia(con, d.isoformat())
            salida.append({"fecha": DIAS_SEMANA[d.weekday()], "dia": d.isoformat(), "total": r["total"],
                           "organico": r["organico"], "aprovechable": r["aprovechable"],
                           "noAprovechable": r["no_aprovechable"]})
    return salida


@app.get("/api/dispositivos")
def dispositivos():
    hoy = date.today().isoformat()
    with closing(conectar()) as con:
        salida = []
        for d in con.execute("SELECT * FROM dispositivos ORDER BY id"):
            s = con.execute("SELECT COUNT(*) n, AVG(confianza) c FROM clasificaciones "
                            "WHERE dispositivo_id = ? AND fecha = ?", (d["id"], hoy)).fetchone()
            ultima = con.execute("SELECT MAX(momento) FROM clasificaciones WHERE dispositivo_id = ?",
                                 (d["id"],)).fetchone()[0]
            salida.append({"id": d["id"], "nombre": d["nombre"], "ubicacion": d["ubicacion"],
                           "estado": "online" if en_linea(d["ultimo_latido"]) else "offline",
                           "clasificacionesHoy": s["n"], "confianzaPromedio": s["c"] or 0,
                           "modelo": d["modelo"], "umbral": d["umbral"],
                           "ultimoLatido": d["ultimo_latido"], "ultimaClasificacion": ultima})
        return salida


@app.get("/api/exportar.csv")
def exportar(desde: Optional[str] = None, hasta: Optional[str] = None,
             formato: Literal["excel", "estandar"] = "excel"):
    texto = a_csv(filas(DB, desde, hasta), excel=formato == "excel")
    nombre = f"greenbin_resultados_{date.today():%Y-%m-%d}.csv"
    return Response("\ufeff" + texto, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@app.websocket("/ws/eventos")
async def ws_eventos(ws: WebSocket):
    await difusor.conectar(ws)
    try:
        while True:
            await ws.receive_text()          # el panel no envía nada; solo mantiene la conexión
    except WebSocketDisconnect:
        difusor.desconectar(ws)


# ───────────────────────────── Panel compilado ─────────────────────────────
if PANEL.exists():
    app.mount("/assets", StaticFiles(directory=PANEL / "assets", check_dir=False), name="assets")

    @app.get("/{ruta:path}", include_in_schema=False)
    def panel(ruta: str):
        archivo = (PANEL / ruta).resolve()
        if ruta and archivo.is_file() and PANEL.resolve() in archivo.parents:
            return FileResponse(archivo)
        return FileResponse(PANEL / "index.html")       # rutas de Angular (/dashboard, /info...)
