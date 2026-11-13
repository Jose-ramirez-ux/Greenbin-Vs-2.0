"""
GreenBin - Captura automatica con sensor

"""

from libcamera import controls
from gpiozero import DistanceSensor
from picamera2 import Picamera2
from datetime import datetime
from pathlib import Path
from time import sleep
import cv2

UMBRAL_CM = 50        # a menos de esta distancia se considera que hay un residuo
TIEMPO_ESPERA = 0.3   # segundos de espera antes de la rafaga
RAFAGA = 5            # fotos por deteccion; se guarda la mas nitida
CARPETA = Path.home() / "greenbin" / "dataset" / "sin_clasificar"
CARPETA.mkdir(parents=True, exist_ok=True)

sensor = DistanceSensor(echo=24, trigger=23, max_distance=4)
camara = Picamera2()
camara.configure(camara.create_still_configuration(main={"size": (1296, 972), "format": "RGB888"}))
camara.set_controls({"AeExposureMode": controls.AeExposureModeEnum.Short})
camara.start()
sleep(2)  # tiempo para que la camara ajuste la luz

def nitidez(img):
    gris = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    return cv2.Laplacian(gris, cv2.CV_64F).var()

contador = 0
print(f"Captura automatica iniciada. Guardando en {CARPETA}")
try:
    while True:
        if sensor.distance * 100 < UMBRAL_CM:
            sleep(TIEMPO_ESPERA)
            fotos = [camara.capture_array() for _ in range(RAFAGA)]
            mejor = max(fotos, key=nitidez)
            contador += 1
            nombre = CARPETA / f"img_{datetime.now():%Y%m%d_%H%M%S}_{contador:04d}.jpg"
            cv2.imwrite(str(nombre), mejor)
            print(f"[{contador}] Foto guardada: {nombre.name}")
            while sensor.distance * 100 < UMBRAL_CM:
                sleep(0.2)
            print("Retirado, listo para el siguiente.")
        sleep(0.2)
except KeyboardInterrupt:
    print(f"\nCaptura detenida. Total de fotos: {contador}")
finally:
    camara.stop()
