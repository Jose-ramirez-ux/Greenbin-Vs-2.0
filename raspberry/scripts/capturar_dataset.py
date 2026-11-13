"""
GreenBin - Captura de dataset
Guarda imágenes recortadas del centro de la cámara para cada categoría.

Controles:
  ESPACIO → guardar imagen de la clase actual
  Q       → cambiar a la siguiente clase
  ESC     → salir
"""

import cv2
import os
import time
from picamera2 import Picamera2

# ── Configuración ────────────────────────────────────────────────────────────
CLASES = ["organico", "aprovechable", "no_aprovechable"]
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dataset")
BASE = os.path.normpath(BASE)
N      = 200      # máximo de imágenes por clase
SIZE   = 224      # tamaño al que se guarda cada imagen (px)
FRAC   = 0.6      # fracción del frame que se recorta al centro
COLORES = {
    "organico": (0, 200, 0),          # verde
    "aprovechable": (255, 255, 255),  # blanco
    "no_aprovechable": (40, 40, 40),  # negro/gris oscuro (negro puro no se ve en video)
}
# ─────────────────────────────────────────────────────────────────────────────

def crear_directorios():
    """Crea la carpeta del dataset y una subcarpeta por clase."""
    os.makedirs(BASE, exist_ok=True)
    for c in CLASES:
        os.makedirs(os.path.join(BASE, c), exist_ok=True)

def contar_existentes():
    """Cuenta las imágenes ya guardadas en cada carpeta de clase."""
    return {c: len(os.listdir(os.path.join(BASE, c))) for c in CLASES}

def calcular_roi(h, w, frac=FRAC):
    """Devuelve las coordenadas (x1,y1,x2,y2) del recorte central."""
    s  = int(frac * min(h, w))
    cx, cy = w // 2, h // 2
    x1, y1 = cx - s // 2, cy - s // 2
    x2, y2 = x1 + s,      y1 + s
    return x1, y1, x2, y2

def dibujar_hud(frame, clase_actual, conteo):
    """Dibuja el rectángulo guía y la información en pantalla."""
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = calcular_roi(h, w)

    # Rectángulo de captura
    color = COLORES[clase_actual]
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    # Información de clase y conteo
    texto = f"Clase: {clase_actual}  [{conteo[clase_actual]}/{N}]"
    cv2.putText(frame, texto, (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(frame, texto, (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)

    # Instrucciones
    instrucciones = "ESPACIO=guardar | Q=cambiar clase | ESC=salir"
    cv2.putText(frame, instrucciones, (20, frame.shape[0] - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)

    return x1, y1, x2, y2

def guardar_imagen(frame, roi_coords, clase, conteo):
    """Recorta, redimensiona y guarda una imagen si no se alcanzó el límite."""
    x1, y1, x2, y2 = roi_coords
    if conteo[clase] >= N:
        print(f"[AVISO] Ya se alcanzaron {N} imágenes para '{clase}'.")
        return

    roi = frame[y1:y2, x1:x2]
    if roi.size == 0:
        print("[AVISO] ROI vacío, no se guardó la imagen.")
        return

    img = cv2.resize(roi, (SIZE, SIZE))
    nombre = f"{time.time():.0f}.jpg"
    ruta = os.path.join(BASE, clase, nombre)
    cv2.imwrite(ruta, img)
    conteo[clase] += 1
    print(f"[OK] Guardada: {ruta}  ({conteo[clase]}/{N})")

def main():
    crear_directorios()
    conteo = contar_existentes()

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"format": "RGB888", "size": (640, 480)})
    picam2.configure(config)
    picam2.start()
    time.sleep(1)  # deja que la cámara ajuste exposición/balance de blancos

    idx = 0  # índice de la clase activa

    print("GreenBin - Captura de dataset iniciada.")
    print(f"Clases: {CLASES}")

    while True:
        frame = picam2.capture_array()

        clase_actual = CLASES[idx]
        roi_coords   = dibujar_hud(frame, clase_actual, conteo)

        cv2.imshow("GreenBin - Captura dataset", frame)

        k = cv2.waitKey(10) & 0xFF
        if k == 27:                        # ESC → salir
            break
        elif k == ord("q"):                # Q → siguiente clase
            idx = (idx + 1) % len(CLASES)
            print(f"[INFO] Clase activa: {CLASES[idx]}")
        elif k == 32:                      # ESPACIO → guardar
            guardar_imagen(frame, roi_coords, clase_actual, conteo)

    picam2.stop()
    cv2.destroyAllWindows()
    print("\nResumen final:")
    for c, n in conteo.items():
        print(f"  {c}: {n} imágenes")

if __name__ == "__main__":
    main()
