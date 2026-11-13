"""
GreenBin - Clasificación en la Raspberry Pi

Flujo (casos de uso CU-01 a CU-05 de la tesis):
  1. El HC-SR04 detecta un residuo (con histéresis para no dispararse dos veces).
  2. (Opcional) enciende el LED, toma una ráfaga y elige la foto más nítida.
  3. Clasifica la foto completa con modelos/greenbin_resnet18_v1.pt.
  4. Muestra la caneca y reproduce el audio de la caneca (CU-04).
     Si la confianza es < 70 % la marca como DUDOSA y reproduce desconocido.mp3.
  5. Registra fecha, hora, clase y confianza en registros/clasificaciones.csv (RF-07).
  6. Solo si la predicción es DUDOSA guarda la foto en registros/dudosas/ para
     revisarla y reetiquetarla después. Antes de guardarla difumina los rostros
     detectados (RNF-05). Las fotos seguras no se guardan nunca.
  7. (Opcional) Envía el RESULTADO al panel web local (nunca la foto). Si el panel
     no responde, lo guarda en registros/pendientes.jsonl y lo reenvía después.

Uso en la Raspberry (desde greenbin/):
    python3 -u scripts/clasificar_pi.py
Prueba en el PC con una foto, sin cámara ni sensor:
    python scripts/clasificar_pi.py --imagen ruta/foto.jpg
Sin guardar las fotos dudosas:
    python3 -u scripts/clasificar_pi.py --sin-dudosas
Con panel web (portátil en la misma red, backend en el puerto 8000):
    python3 -u scripts/clasificar_pi.py --panel http://IP-DEL-PORTATIL:8000 --token LA-CLAVE
  o, para no escribirlo cada vez, crear greenbin/panel.env (no se sube a Git) con:
    GREENBIN_PANEL=http://IP-DEL-PORTATIL:8000
    GREENBIN_TOKEN=LA-CLAVE
"""

import argparse
import csv
import json
import os
import queue
import threading
import urllib.request
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from time import sleep, time

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms as T

RAIZ = Path(__file__).resolve().parent.parent
MODELO = RAIZ / "modelos" / "greenbin_resnet18_v1.pt"
REGISTRO = RAIZ / "registros" / "clasificaciones.csv"
AUDIOS = RAIZ / "audios"               # organico.mp3, aprovechable.mp3, no_aprovechable.mp3, desconocido.mp3
DUDOSAS = RAIZ / "registros" / "dudosas"
MAX_DUDOSAS = 500                      # tope de fotos guardadas (~220 KB c/u, ~110 MB en total); al llenarse deja de guardar

UMBRAL_CONF = 0.70                     # RF-06
DISPARO_CM, LIBERA_CM = 40, 55         # histéresis del sensor
LECTURAS = 3                           # lecturas seguidas bajo el umbral para disparar
ESPERA_S, RAFAGA = 0.3, 5
BRILLO_MIN = 25                        # por debajo, la foto está oscura y no se clasifica
PIN_LED = None                         # p. ej. 17 si conectan un LED por transistor
PENDIENTES = RAIZ / "registros" / "pendientes.jsonl"
DISPOSITIVO = {"dispositivo_id": "gb-01", "nombre": "GreenBin-01", "ubicacion": "Cafetería FET",
               "modelo": "ResNet18 v1 · extractor congelado + regresión logística", "umbral": UMBRAL_CONF}
LATIDO_S = 30                          # cada cuánto avisa al panel que está en línea

CANECA = {
    "aprovechable": "BLANCA (aprovechable)",
    "no_aprovechable": "NEGRA (no aprovechable)",
    "organico": "VERDE (orgánico)",
}
TF = T.Compose([T.Resize((224, 224)), T.ToTensor(),
                T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])


def cargar_modelo(ruta=MODELO):
    ck = torch.load(ruta, map_location="cpu")
    red = models.resnet18(weights=None)
    red.fc = nn.Linear(512, len(ck["classes"]))
    red.load_state_dict(ck["model"])
    red.eval()
    return red, ck["classes"]


@torch.no_grad()
def clasificar(red, clases, rgb):
    """rgb: arreglo numpy HxWx3 en orden RGB (foto completa, sin recortar)."""
    probs = torch.softmax(red(TF(Image.fromarray(rgb)).unsqueeze(0)), dim=1)[0].numpy()
    i = int(np.argmax(probs))
    return clases[i], float(probs[i]), probs


_audio_actual = None


def reproducir(nombre):
    """Reproduce audios/<nombre>.mp3 sin bloquear el programa (requiere: sudo apt install mpg123).
    Si había un mensaje sonando, lo corta para no encimar voces."""
    global _audio_actual
    archivo = AUDIOS / f"{nombre}.mp3"
    reproductor = shutil.which("mpg123")
    if not archivo.exists() or reproductor is None:
        print(f"   [audio] no se pudo reproducir {archivo.name} "
              f"({'falta el archivo' if not archivo.exists() else 'instale mpg123'})", flush=True)
        return
    if _audio_actual is not None and _audio_actual.poll() is None:
        _audio_actual.terminate()
    _audio_actual = subprocess.Popen([reproductor, "-q", str(archivo)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def anunciar(clase, conf):
    seguro = conf >= UMBRAL_CONF
    estado = "SEGURO" if seguro else "DUDOSO, verifique"
    print(f"[{datetime.now():%H:%M:%S}] Caneca {CANECA[clase]}  confianza {conf:.0%}  ({estado})", flush=True)
    reproducir(clase if seguro else "desconocido")


COLUMNAS_REGISTRO = ["fecha", "hora", "clase", "confianza", "dudoso", "imagen", "tiempo_s"]


def registrar(clase, conf, imagen="", tiempo_s=None):
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    if REGISTRO.exists():                      # archivo de una versión anterior, con otras columnas
        with open(REGISTRO, encoding="utf-8") as f:
            if f.readline().strip().split(",") != COLUMNAS_REGISTRO:
                REGISTRO.rename(REGISTRO.with_name(f"clasificaciones_anterior_{datetime.now():%Y%m%d_%H%M%S}.csv"))
    nuevo = not REGISTRO.exists()
    with open(REGISTRO, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(COLUMNAS_REGISTRO)
        ahora = datetime.now()
        w.writerow([f"{ahora:%Y-%m-%d}", f"{ahora:%H:%M:%S}", clase, f"{conf:.3f}",
                    conf < UMBRAL_CONF, imagen, "" if tiempo_s is None else f"{tiempo_s:.3f}"])


# ---------- Fotos dudosas con rostros difuminados (RNF-05) ----------
DETECTOR_ROSTROS = RAIZ / "modelos" / "face_detection_yunet_2023mar.onnx"   # YuNet (OpenCV Zoo), 230 KB
_detector = None


def _cargar_detector():
    """Detector de rostros YuNet de OpenCV (requiere OpenCV >= 4.8). None si no está disponible."""
    if not DETECTOR_ROSTROS.exists() or not hasattr(cv2, "FaceDetectorYN"):
        return None
    try:
        return cv2.FaceDetectorYN.create(str(DETECTOR_ROSTROS), "", (320, 320), 0.4, 0.3, 5000)
    except cv2.error:
        return None


def difuminar_rostros(bgr):
    """Devuelve (copia con los rostros pixelados, n.º de rostros), o (None, 0) si no hay
    detector: en ese caso la foto NO se guarda.
    Acepta un rostro con puntaje >= 0,80, o >= 0,40 si está cortado por el borde
    superior o lateral (cabezas a medio entrar en el cuadro). Lo que toca el borde
    inferior suele ser la mano con el residuo, así que ahí se exige 0,80."""
    global _detector
    if _detector is None:
        _detector = _cargar_detector()
        if _detector is None:
            return None, 0
    alto, ancho = bgr.shape[:2]
    _detector.setInputSize((ancho, alto))
    _, caras = _detector.detect(bgr)
    out, n = bgr.copy(), 0
    for c in (caras if caras is not None else []):
        x, y, w, h, s = int(c[0]), int(c[1]), int(c[2]), int(c[3]), float(c[-1])
        borde = (x <= 2 or y <= 2 or x + w >= ancho - 2) and y + h < alto - 2
        if not (s >= 0.80 or (borde and s >= 0.40)):
            continue
        m = int(0.25 * max(w, h))                                       # margen: pelo, orejas
        x0, y0 = max(0, x - m), max(0, y - m)
        x1, y1 = min(ancho, x + w + m), min(alto, y + h + m)
        peq = cv2.resize(out[y0:y1, x0:x1], (6, 6), interpolation=cv2.INTER_AREA)
        out[y0:y1, x0:x1] = cv2.resize(peq, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
        n += 1
    return out, n


def guardar_dudosa(bgr, clase, conf):
    """Guarda la foto dudosa (rostros difuminados) y devuelve el nombre, o "" si no se guardó."""
    DUDOSAS.mkdir(parents=True, exist_ok=True)
    if len(list(DUDOSAS.glob("*.jpg"))) >= MAX_DUDOSAS:
        print(f"   [dudosas] carpeta llena ({MAX_DUDOSAS}); revise y vacíe registros/dudosas/", flush=True)
        return ""
    anon, n = difuminar_rostros(bgr)
    if anon is None:
        print("   [dudosas] sin detector de rostros (falta modelos/face_detection_yunet_2023mar.onnx "
              "u OpenCV < 4.8): la foto no se guarda (RNF-05)", flush=True)
        return ""
    ahora = datetime.now()
    nombre = f"{ahora:%Y%m%d_%H%M%S}_{ahora.microsecond // 1000:03d}_{clase}_{round(conf * 100):02d}.jpg"
    cv2.imwrite(str(DUDOSAS / nombre), anon, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f"   [dudosas] guardada {nombre} ({n} rostro(s) difuminado(s))", flush=True)
    return nombre


# ---------- Envío al panel web (solo resultados, nunca imágenes) ----------
class Panel:
    """Envía cada clasificación al backend del panel en un hilo aparte, para no
    retrasar el audio. Si no hay conexión guarda el evento en pendientes.jsonl y
    lo reenvía con el siguiente latido. Solo este hilo toca ese archivo."""

    def __init__(self, url, token):
        self.url, self.token = url.rstrip("/"), token
        self.cola = queue.Queue()
        self.conectado = None
        threading.Thread(target=self._trabajar, daemon=True).start()

    def enviar(self, clase, conf, tiempo_s=None):
        self.cola.put({"dispositivo_id": DISPOSITIVO["dispositivo_id"],
                       "momento": datetime.now().astimezone().isoformat(timespec="seconds"),
                       "categoria": clase, "confianza": round(conf, 4),
                       "estado": "seguro" if conf >= UMBRAL_CONF else "dudoso",
                       "tiempo_s": None if tiempo_s is None else round(tiempo_s, 3)})

    def esperar(self, segundos=5):
        """Para el modo --imagen: deja terminar los envíos antes de salir."""
        fin = time() + segundos
        while self.cola.unfinished_tasks and time() < fin:
            sleep(0.1)

    def _post(self, ruta, datos):
        req = urllib.request.Request(self.url + ruta, data=json.dumps(datos).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-GreenBin-Token": self.token})
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status < 300

    def _estado(self, ok, error=None):
        if ok != self.conectado:
            if ok:
                print(f"   [panel] conectado a {self.url}", flush=True)
            elif getattr(error, "code", None) == 401:
                print("   [panel] el panel rechazó el token (--token); los resultados quedan en pendientes.jsonl", flush=True)
            else:
                print(f"   [panel] sin conexión con {self.url}; los resultados quedan en pendientes.jsonl", flush=True)
        self.conectado = ok

    def _trabajar(self):
        proximo_latido = 0
        while True:
            if time() >= proximo_latido:          # primero el latido: registra el dispositivo
                proximo_latido = time() + LATIDO_S
                try:
                    self._estado(self._post("/api/latido", DISPOSITIVO))
                    self._reenviar_pendientes()
                except Exception as e:
                    self._estado(False, e)
            try:
                evento = self.cola.get(timeout=1)
            except queue.Empty:
                continue
            try:
                self._estado(self._post("/api/clasificaciones", evento))
            except Exception as e:
                self._estado(False, e)
                PENDIENTES.parent.mkdir(parents=True, exist_ok=True)
                with open(PENDIENTES, "a", encoding="utf-8") as f:
                    f.write(json.dumps(evento) + "\n")
            self.cola.task_done()

    def _reenviar_pendientes(self):
        if not PENDIENTES.exists():
            return
        lote = [json.loads(l) for l in PENDIENTES.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lote and self._post("/api/clasificaciones/lote", lote):
            PENDIENTES.unlink()
            print(f"   [panel] reenviadas {len(lote)} clasificaciones pendientes", flush=True)


def nitidez(bgr):
    return cv2.Laplacian(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()


def bucle_raspberry(red, clases, guardar_dudosas=True, panel=None):
    from gpiozero import DistanceSensor, LED
    from libcamera import controls
    from picamera2 import Picamera2

    sensor = DistanceSensor(echo=24, trigger=23, max_distance=4)   # ECHO con divisor de voltaje
    led = LED(PIN_LED) if PIN_LED is not None else None
    cam = Picamera2()
    cam.configure(cam.create_still_configuration(main={"size": (1296, 972), "format": "RGB888"}))
    cam.set_controls({"AeExposureMode": controls.AeExposureModeEnum.Short})
    cam.start()
    sleep(2)

    def cerca(umbral):
        for _ in range(LECTURAS):
            if sensor.distance * 100 >= umbral:
                return False
            sleep(0.05)
        return True

    print("GreenBin listo. Acerque un residuo.", flush=True)
    try:
        while True:
            if cerca(DISPARO_CM):
                t_det = time()                         # PR-08: desde la detección hasta el audio
                if led:
                    led.on()
                sleep(ESPERA_S)
                # "RGB888" de Picamera2 entrega los píxeles en orden B,G,R (el de OpenCV)
                fotos = [cam.capture_array() for _ in range(RAFAGA)]
                if led:
                    led.off()
                bgr = max(fotos, key=nitidez)
                if cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).mean() < BRILLO_MIN:
                    print("Foto demasiado oscura: revise la iluminación.", flush=True)
                    reproducir("desconocido")
                else:
                    t0 = time()
                    clase, conf, _ = clasificar(red, clases, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
                    t_clas = time() - t0
                    anunciar(clase, conf)              # el audio arranca antes de guardar
                    t_resp = time() - t_det
                    imagen = ""
                    if guardar_dudosas and conf < UMBRAL_CONF:
                        imagen = guardar_dudosa(bgr, clase, conf)
                    registrar(clase, conf, imagen, t_resp)
                    if panel:
                        panel.enviar(clase, conf, t_resp)
                    print(f"   tiempo de clasificación: {t_clas:.2f} s | respuesta total (detección → audio): {t_resp:.2f} s",
                          flush=True)
                while sensor.distance * 100 < LIBERA_CM:
                    sleep(0.2)
            sleep(0.1)
    except KeyboardInterrupt:
        print("\nDetenido.")
    finally:
        cam.stop()


def cargar_panel_env(ruta=RAIZ / "panel.env"):
    """Lee GREENBIN_PANEL y GREENBIN_TOKEN de greenbin/panel.env si existe
    (las variables de entorno ya definidas tienen prioridad)."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"'))


def main():
    cargar_panel_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--imagen", help="clasifica una foto y termina (prueba sin hardware)")
    ap.add_argument("--modelo", default=str(MODELO))
    ap.add_argument("--sin-dudosas", action="store_true", help="no guardar las fotos dudosas")
    ap.add_argument("--panel", default=os.environ.get("GREENBIN_PANEL"),
                    help="URL del backend del panel, p. ej. http://192.168.1.20:8000")
    ap.add_argument("--token", default=os.environ.get("GREENBIN_TOKEN", ""))
    args = ap.parse_args()
    red, clases = cargar_modelo(args.modelo)
    panel = Panel(args.panel, args.token) if args.panel else None
    if args.imagen:
        rgb = np.array(Image.open(args.imagen).convert("RGB"))
        clase, conf, probs = clasificar(red, clases, rgb)
        anunciar(clase, conf)
        print("   " + "  ".join(f"{c}: {p:.0%}" for c, p in zip(clases, probs)))
        if conf < UMBRAL_CONF and not args.sin_dudosas:
            guardar_dudosa(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), clase, conf)
        if panel:
            panel.enviar(clase, conf)
            panel.esperar()
        if _audio_actual is not None:
            _audio_actual.wait()           # deja terminar el mensaje antes de salir
    else:
        bucle_raspberry(red, clases, guardar_dudosas=not args.sin_dudosas, panel=panel)


if __name__ == "__main__":
    main()
