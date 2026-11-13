"""
test_picamera_opencv.py
Captura un frame con Picamera2 (librería oficial para cámaras CSI en Raspberry Pi)
y lo pasa a OpenCV para guardarlo como imagen.
"""
from picamera2 import Picamera2
import cv2

print("Inicializando cámara con Picamera2...")
picam2 = Picamera2()

config = picam2.create_preview_configuration(main={"size": (1296, 972), "format": "RGB888"})
picam2.configure(config)
picam2.start()

print("Capturando frame...")
frame = picam2.capture_array()   # devuelve un array numpy, formato RGB

# OpenCV trabaja en BGR, así que convertimos antes de guardar/mostrar
frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

h, w = frame_bgr.shape[:2]
print(f"[OK] Frame capturado. Resolución: {w}x{h}")

cv2.imwrite("capturada.jpg", frame_bgr)
print("[OK] Imagen guardada como capturada.jpg")

picam2.stop()
