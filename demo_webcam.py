"""
GreenBin - Demo en tiempo real con webcam
Carga el modelo entrenado y clasifica residuos frame a frame.
Muestra la clase predicha, la confianza y la caneca recomendada.

Uso:
    python demo_webcam.py

Controles:
    Q / ESC → salir
"""

import os
import sys
import cv2
import torch
import numpy as np
from torchvision import transforms, models
from PIL import Image

# ── Configuración ────────────────────────────────────────────────────────────
MODEL      = "modelos/greenbin_resnet18.pt"
IMG        = 224
TH         = 0.70    # umbral de confianza: verde=seguro, amarillo=dudoso
CAM_INDEX  = 0       # cambia a 1 si usas otra cámara
SUAVIZADO  = 5       # frames a promediar para estabilizar predicción

CANECA = {
    "organico":        ("VERDE (Orgánico)",              (0, 180, 0)),
    "aprovechable":    ("BLANCA (Aprovechable/Reciclable)", (220, 220, 220)),
    "no_aprovechable": ("NEGRA (No aprovechable)",       (60, 60, 60)),
}
# ─────────────────────────────────────────────────────────────────────────────

def cargar_modelo(ruta):
    """Carga el modelo guardado y reconstruye la arquitectura."""
    if not os.path.exists(ruta):
        print(f"[ERROR] No se encontró el modelo en '{ruta}'.")
        print("        Ejecuta primero entrenar.py o fewshot_desde_imagenes.py")
        sys.exit(1)

    ckpt    = torch.load(ruta, map_location="cpu")
    classes = ckpt["classes"]
    model   = models.resnet18(weights=None)
    model.fc = torch.nn.Linear(model.fc.in_features, len(classes))
    model.load_state_dict(ckpt["model"])
    model.eval()
    print(f"[OK] Modelo cargado. Clases: {classes}")
    return model, classes

def obtener_transform():
    return transforms.Compose([
        transforms.Resize((IMG, IMG)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406],
                             [0.229, 0.224, 0.225]),
    ])

def calcular_roi(h, w, frac=0.6):
    s  = int(frac * min(h, w))
    cx, cy = w // 2, h // 2
    x1, y1 = cx - s // 2, cy - s // 2
    return x1, y1, x1 + s, y1 + s

def inferir(frame, model, classes, transform):
    """Realiza la inferencia sobre el ROI central del frame."""
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = calcular_roi(h, w)
    roi = frame[y1:y2, x1:x2]

    if roi.size == 0:
        return "desconocido", "", 0.0, (x1, y1, x2, y2)

    # Convertir BGR → RGB → PIL (necesario para el transform de torchvision)
    rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    ten = transform(pil).unsqueeze(0)

    with torch.no_grad():
        probs = torch.softmax(model(ten), dim=1).numpy()[0]

    i       = int(np.argmax(probs))
    conf    = float(probs[i])
    cls     = classes[i]
    caneca, _ = CANECA.get(cls, ("Desconocida", (128, 128, 128)))
    return cls, caneca, conf, (x1, y1, x2, y2)

def texto_con_sombra(img, texto, pos, color, escala=0.8, grosor=2):
    """Dibuja texto con sombra negra para mejor legibilidad."""
    cv2.putText(img, texto, pos,
                cv2.FONT_HERSHEY_SIMPLEX, escala, (0, 0, 0), grosor + 2, cv2.LINE_AA)
    cv2.putText(img, texto, pos,
                cv2.FONT_HERSHEY_SIMPLEX, escala, color, grosor, cv2.LINE_AA)

def color_confianza(conf):
    """Verde si conf >= TH, amarillo si es dudoso."""
    return (0, 220, 0) if conf >= TH else (0, 220, 220)

def main():
    model, classes = cargar_modelo(MODEL)
    transform      = obtener_transform()

    cap = cv2.VideoCapture(CAM_INDEX)
    if not cap.isOpened():
        print(f"[ERROR] No se pudo abrir la cámara (índice {CAM_INDEX}).")
        sys.exit(1)

    print("GreenBin Demo iniciado. Coloca el residuo en el marco.")
    print("Q / ESC para salir.")

    historial = []   # para suavizar predicciones

    while True:
        ok, frame = cap.read()
        if not ok:
            print("[ERROR] No se pudo leer el frame.")
            break

        cls, caneca_texto, conf, (x1, y1, x2, y2) = inferir(
            frame, model, classes, transform
        )

        # Suavizado: guardar últimas N predicciones
        historial.append((cls, conf))
        if len(historial) > SUAVIZADO:
            historial.pop(0)

        # Clase más frecuente y confianza promedio de esa clase
        clases_hist = [h[0] for h in historial]
        cls_suav    = max(set(clases_hist), key=clases_hist.count)
        conf_suav   = np.mean([h[1] for h in historial if h[0] == cls_suav])
        caneca_suav, color_caneca = CANECA.get(cls_suav, ("Desconocida", (128,128,128)))

        # Dibujar
        color_box = color_confianza(conf_suav)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color_box, 2)

        texto_con_sombra(frame,
                         f"Clase: {cls_suav}  Conf: {conf_suav:.0%}",
                         (20, 35), color_box)
        texto_con_sombra(frame,
                         f"Caneca: {caneca_suav}",
                         (20, 70),
                         (255, 255, 255) if conf_suav >= TH else (0, 220, 220))

        estado = "SEGURO" if conf_suav >= TH else "DUDOSO"
        texto_con_sombra(frame, estado, (20, 105),
                         (0, 220, 0) if conf_suav >= TH else (0, 220, 220),
                         escala=0.65)

        cv2.imshow("GreenBin - Demo Webcam", frame)

        k = cv2.waitKey(10) & 0xFF
        if k in (27, ord("q")):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("GreenBin Demo finalizado.")

if __name__ == "__main__":
    main()
