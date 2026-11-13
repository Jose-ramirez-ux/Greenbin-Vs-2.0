"""
GreenBin - Clasificación few-shot desde imágenes de referencia
No requiere entrenamiento. Clasifica residuos comparando características
visuales del frame contra imágenes de ejemplo por categoría.

Uso:
    python fewshot_desde_imagenes.py

Controles:
    Q / ESC → salir
"""

import os
import sys
import cv2
import numpy as np
import torch
from torchvision import models, transforms
from PIL import Image

# ── Configuración ────────────────────────────────────────────────────────────
IMG       = 224
TH        = 0.55      # umbral de similitud coseno (0–1)
CAM_INDEX = 0
SUAVIZADO = 5         # frames para suavizar predicción

# Imágenes de referencia por clase (puedes agregar más rutas por lista)
EJEMPLOS = {
    "organico":        [r"C:\Users\USUARIO\Documentos\GreenBin_mejorado\dataset\organico\1779470871.jpg"],
    "aprovechable":    [r"C:\Users\USUARIO\Documentos\GreenBin_mejorado\dataset\aprovechable\1779473546.jpg"],
    "no_aprovechable": [r"C:\Users\USUARIO\Documentos\GreenBin_mejorado\dataset\no_aprovechable\20.jpeg"]
}

CANECA = {
    "organico":        ("VERDE (Organico)",               (0, 180, 0)),
    "aprovechable":    ("BLANCA (Aprovechable/Reciclable)", (220, 220, 220)),
    "no_aprovechable": ("NEGRA (No aprovechable)",         (60, 60, 60)),
}
# ─────────────────────────────────────────────────────────────────────────────

def construir_extractor():
    """ResNet18 sin la capa final → extrae un vector de 512 características."""
    device = "cpu"
    base   = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
    base.fc = torch.nn.Identity()
    base.eval().to(device)
    return base, device

def obtener_transform():
    return transforms.Compose([
        transforms.Resize((IMG, IMG)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406],
                             [0.229, 0.224, 0.225]),
    ])

def embed_bgr(bgr, model, transform, device):
    """Convierte un frame BGR a su vector de características normalizado."""
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    ten = transform(pil).unsqueeze(0).to(device)
    with torch.no_grad():
        v = model(ten).cpu().numpy()[0]
    norma = np.linalg.norm(v)
    return v / (norma + 1e-9)

def cargar_centroides(model, transform, device):
    """Calcula el centroide de embeddings por cada clase."""
    centroides = {}
    for clase, rutas in EJEMPLOS.items():
        vecs = []
        for ruta in rutas:
            if not os.path.exists(ruta):
                print(f"[AVISO] No se encontró: {ruta}")
                continue
            bgr = cv2.imread(ruta)
            if bgr is None:
                print(f"[AVISO] No se pudo leer: {ruta}")
                continue
            vecs.append(embed_bgr(bgr, model, transform, device))

        if not vecs:
            print(f"[ERROR] Sin imágenes válidas para la clase '{clase}'.")
            sys.exit(1)

        M = np.vstack(vecs)
        m = M.mean(axis=0)
        centroides[clase] = m / (np.linalg.norm(m) + 1e-9)
        print(f"[OK] Centroide '{clase}' calculado con {len(vecs)} imagen(es).")

    return centroides

def predecir(emb, centroides):
    """Similitud coseno del embedding contra cada centroide."""
    mejor_clase = "desconocido"
    mejor_sim   = -1.0
    for clase, m in centroides.items():
        sim = float(np.dot(emb, m))
        if sim > mejor_sim:
            mejor_sim, mejor_clase = sim, clase
    return mejor_clase, mejor_sim

def calcular_roi(h, w, frac=0.6):
    s  = int(frac * min(h, w))
    cx, cy = w // 2, h // 2
    x1, y1 = cx - s // 2, cy - s // 2
    return x1, y1, x1 + s, y1 + s

def texto_con_sombra(img, texto, pos, color, escala=0.85, grosor=2):
    cv2.putText(img, texto, pos,
                cv2.FONT_HERSHEY_SIMPLEX, escala, (0, 0, 0), grosor + 2, cv2.LINE_AA)
    cv2.putText(img, texto, pos,
                cv2.FONT_HERSHEY_SIMPLEX, escala, color, grosor, cv2.LINE_AA)

def main():
    model, device  = construir_extractor()
    transform      = obtener_transform()
    centroides     = cargar_centroides(model, transform, device)

    cap = cv2.VideoCapture(CAM_INDEX)
    if not cap.isOpened():
        print(f"[ERROR] No se pudo abrir la cámara (índice {CAM_INDEX}).")
        sys.exit(1)

    print("\nGreenBin Few-Shot iniciado. Coloca el residuo en el marco.")
    print("Q / ESC para salir.")

    historial = []

    while True:
        ok, frame = cap.read()
        if not ok:
            print("[ERROR] No se pudo leer el frame.")
            break

        h, w = frame.shape[:2]
        x1, y1, x2, y2 = calcular_roi(h, w)
        roi = frame[y1:y2, x1:x2]

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 220), 2)

        if roi.size:
            emb = embed_bgr(roi, model, transform, device)
            cls, sim = predecir(emb, centroides)

            historial.append((cls, sim))
            if len(historial) > SUAVIZADO:
                historial.pop(0)

            clases_hist = [h[0] for h in historial]
            cls_suav    = max(set(clases_hist), key=clases_hist.count)
            sim_suav    = np.mean([h[1] for h in historial if h[0] == cls_suav])
            caneca_suav, color_caneca = CANECA.get(cls_suav, ("Desconocida", (128,128,128)))

            color_box = (0, 220, 0) if sim_suav >= TH else (0, 220, 220)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color_box, 2)

            texto_con_sombra(frame,
                             f"Clase: {cls_suav}  Sim: {sim_suav:.2f}",
                             (20, 35), color_box)
            texto_con_sombra(frame,
                             f"Caneca: {caneca_suav}",
                             (20, 70),
                             (255, 255, 255) if sim_suav >= TH else (0, 220, 220))

            estado = "SEGURO" if sim_suav >= TH else "DUDOSO"
            texto_con_sombra(frame, estado, (20, 105),
                             (0, 220, 0) if sim_suav >= TH else (0, 220, 220),
                             escala=0.65)
        else:
            texto_con_sombra(frame, "Mueve el objeto al marco",
                             (20, 35), (0, 220, 220))

        cv2.imshow("GreenBin - Few-Shot", frame)
        k = cv2.waitKey(10) & 0xFF
        if k in (27, ord("q")):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("GreenBin Few-Shot finalizado.")

if __name__ == "__main__":
    main()
