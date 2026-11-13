# GreenBin — Panel web local

Panel de gestión del prototipo GreenBin (FET Neiva). Muestra en tiempo real cada
clasificación que hace la Raspberry Pi, el historial de la semana y el estado del
dispositivo. Funciona **en la red local**, sin servicios en la nube.

```
Raspberry Pi (clasificar_pi.py)                 Portátil (este repositorio)
  sensor → cámara → modelo → audio              ┌──────────────────────────────┐
        │                                       │ backend/ (FastAPI + SQLite)  │
        └── POST /api/clasificaciones ────────► │   guarda y reenvía por WS    │
            POST /api/latido (cada 30 s)        │ dist/ (panel Angular)        │──► navegador
            solo resultados, nunca imágenes     └──────────────────────────────┘
```

- La Pi envía **solo el resultado** (categoría, confianza, seguro/dudoso, hora). Ninguna imagen sale de la Pi (RNF-05).
- Si el portátil no responde, la Pi guarda los resultados en `registros/pendientes.jsonl` y los reenvía al reconectarse. El audio nunca espera al panel.

## Estructura

```
backend/
  app.py              API REST + WebSocket + sirve el panel compilado
  requirements.txt
  iniciar_panel.bat   arranque en Windows
src/app/
  core/               modelos y servicio (HTTP + WebSocket con reconexión)
  features/           dashboard, dispositivos, en vivo (clasificador), info
  shared/             navbar, metric-card
proxy.conf.json       reenvía /api y /ws a localhost:8000 durante `ng serve`
```

## Puesta en marcha (portátil con Windows)

1. **Compilar el panel** (solo cuando cambie el código Angular; requiere Node 18+):
   ```
   npm install
   npm run build
   ```
2. **Iniciar el backend**: doble clic en `backend\iniciar_panel.bat`, o:
   ```
   cd backend
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   set GREENBIN_TOKEN=una-clave-larga
   .venv\Scripts\uvicorn app:app --host 0.0.0.0 --port 8000
   ```
   La primera vez Windows pregunta por el firewall: permita las **redes privadas**.
3. Abrir **http://localhost:8000**.
4. Averiguar la IP del portátil (`ipconfig`, o la IP 100.x de Tailscale si la red del campus no deja que los equipos se vean entre sí).

## En la Raspberry Pi

```
python3 -u scripts/clasificar_pi.py --panel http://IP-DEL-PORTATIL:8000 --token una-clave-larga
```
También se pueden usar las variables de entorno `GREENBIN_PANEL` y `GREENBIN_TOKEN`.
Si se omite `--panel`, el clasificador funciona igual, sin enviar nada.

## Desarrollo

```
cd backend && uvicorn app:app --reload --port 8000     # terminal 1
npm start                                              # terminal 2 → http://localhost:4200
```

## API

| Método | Ruta | Uso |
|---|---|---|
| POST | `/api/clasificaciones` | La Pi envía una clasificación (cabecera `X-GreenBin-Token`) |
| POST | `/api/clasificaciones/lote` | La Pi reenvía las pendientes |
| POST | `/api/latido` | La Pi avisa que está en línea (cada 30 s) |
| GET | `/api/clasificaciones?limite=20` | Últimas clasificaciones |
| GET | `/api/metricas` | Totales de hoy, confianza, dudosas, distribución |
| GET | `/api/historial?dias=7` | Conteo por día y categoría |
| GET | `/api/dispositivos` | Estado de cada Pi (en línea si hubo latido en 90 s) |
| GET | `/api/exportar.csv?desde=&hasta=&formato=excel\|estandar` | Descarga las clasificaciones en CSV |
| WS | `/ws/eventos` | `{"tipo": "clasificacion", "datos": {...}}`, `{"tipo": "dispositivo"}` |

Los datos quedan en `backend/greenbin.db` (SQLite). Ese archivo no se sube a Git.

## Exportar resultados a CSV

- **Desde el panel:** botón **Exportar CSV** en el Dashboard (formato Excel: `;` y coma decimal). El enlace *formato estándar* usa `,` y punto decimal, para Python, R o Google Sheets.
- **Sin el backend encendido:** `cd backend` y `.venv\Scripts\python exportar_csv.py` (opciones `--desde AAAA-MM-DD`, `--hasta`, `--estandar`).

Columnas: `id, fecha, hora, dispositivo, categoria, caneca, confianza, estado, tiempo_s`, más cuatro columnas vacías para completar a mano con la planilla de observación: `residuo_real, caneca_correcta, acierto, observaciones`. `tiempo_s` es el tiempo desde que el sensor detecta el residuo hasta que suena el audio (PR-08); solo existe en las clasificaciones hechas con la versión del 10 de noviembre de `clasificar_pi.py` o posterior.

## Equipo

Juan Felipe Bahamon Castillo · José Eduar Ramírez Cardona · Santiago Tovar Vargas
Tutora: Viviana Muñoz Álvarez — Ingeniería de Software, FET Neiva
