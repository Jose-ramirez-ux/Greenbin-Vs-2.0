"""
GreenBin - Entrenamiento v2 (extractor congelado + clasificador lineal)

Por qué este método: con ~150 fotos propias, ajustar toda la red sobreajusta.
Se usa ResNet18 preentrenada en ImageNet como extractor de características
(congelada) y se entrena solo la capa final con regresión logística.
En validación cruzada por objeto fue el mejor de los métodos probados.

Entrada : dataset_v1/etiquetas.csv  (archivo, clase, grupo, ...)
          dataset_v1/<clase>/<archivo>.jpg
Salida  : modelos/greenbin_resnet18_v1.pt  (mismo formato que usa demo_webcam.py)
          y un reporte de validación cruzada en pantalla.

Uso (desde la carpeta greenbin/):
    python scripts/entrenar_v2.py
    python scripts/entrenar_v2.py --pesos ruta/resnet18_imagenet.pt   # sin internet

Requisitos: torch, torchvision, pillow, numpy, scikit-learn
"""

import argparse
import csv
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms as T
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import StratifiedGroupKFold

RAIZ = Path(__file__).resolve().parent.parent          # carpeta greenbin/
CLASES = ["aprovechable", "no_aprovechable", "organico"]  # orden alfabético, igual que ImageFolder
SEMILLA = 42
AUMENTOS = 4          # copias aumentadas de cada foto para el clasificador
C_REG = 0.5           # regularización de la regresión logística

NORM = T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
# Importante: foto COMPLETA redimensionada a 224x224, sin recorte central.
# clasificar_pi.py usa exactamente el mismo preprocesamiento.
TF_EVAL = T.Compose([T.Resize((224, 224)), T.ToTensor(), NORM])
TF_AUG = T.Compose([
    T.RandomResizedCrop(224, scale=(0.6, 1.0)),
    T.RandomHorizontalFlip(),
    T.ColorJitter(0.3, 0.3, 0.3, 0.05),
    T.RandomRotation(10),
    T.ToTensor(), NORM,
])


def cargar_dataset(carpeta):
    filas = list(csv.DictReader(open(carpeta / "etiquetas.csv", encoding="utf-8-sig")))
    imgs = [Image.open(carpeta / f["clase"] / f["archivo"]).convert("RGB") for f in filas]
    y = np.array([CLASES.index(f["clase"]) for f in filas])
    grupos = np.array([int(f["grupo"]) for f in filas])
    return imgs, y, grupos


def construir_red(pesos):
    red = models.resnet18(weights=None)
    if pesos:
        red.load_state_dict(torch.load(pesos, map_location="cpu"))
    else:
        red = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
    return red


@torch.no_grad()
def caracteristicas(extractor, imgs, tf):
    out = []
    for k in range(0, len(imgs), 16):
        out.append(extractor(torch.stack([tf(i) for i in imgs[k:k + 16]])))
    return torch.cat(out).numpy()


def entrenar_clasificador(E, A, y, idx):
    X = np.vstack([E[idx]] + [a[idx] for a in A])
    Y = np.concatenate([y[idx]] * (len(A) + 1))
    return LogisticRegression(max_iter=3000, C=C_REG, class_weight="balanced").fit(X, Y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(RAIZ / "dataset_v1"))
    ap.add_argument("--pesos", default=None, help="state_dict de ResNet18 ImageNet (si no hay internet)")
    ap.add_argument("--salida", default=str(RAIZ / "modelos" / "greenbin_resnet18_v1.pt"))
    args = ap.parse_args()

    torch.manual_seed(SEMILLA)
    np.random.seed(SEMILLA)
    imgs, y, grupos = cargar_dataset(Path(args.dataset))
    print(f"[INFO] {len(y)} fotos | por clase: {dict(zip(CLASES, np.bincount(y, minlength=3)))} "
          f"| {len(set(grupos))} objetos/ráfagas")

    red = construir_red(args.pesos)
    pesos_base = {k: v for k, v in red.state_dict().items() if not k.startswith("fc.")}
    red.fc = nn.Identity()
    red.eval()
    E = caracteristicas(red, imgs, TF_EVAL)
    A = [caracteristicas(red, imgs, TF_AUG) for _ in range(AUMENTOS)]

    # Validación cruzada por grupos: un mismo objeto nunca queda en train y test a la vez
    pred = np.zeros_like(y)
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEMILLA)
    for tr, te in cv.split(E, y, grupos):
        pred[te] = entrenar_clasificador(E, A, y, tr).predict(E[te])
    print("\nMatriz de confusión (filas = real, columnas = predicho):")
    print("            " + "  ".join(c[:8] for c in CLASES))
    for c, fila in zip(CLASES, confusion_matrix(y, pred, labels=[0, 1, 2])):
        print(f"{c[:10]:10}  " + "  ".join(f"{v:8d}" for v in fila))
    print("\n" + classification_report(y, pred, target_names=CLASES, zero_division=0))

    # Modelo final con todas las fotos; la capa fc es la regresión logística
    clf = entrenar_clasificador(E, A, y, np.arange(len(y)))
    final = models.resnet18(weights=None)
    final.fc = nn.Linear(512, len(CLASES))
    final.load_state_dict({**pesos_base,
                           "fc.weight": torch.tensor(clf.coef_, dtype=torch.float32),
                           "fc.bias": torch.tensor(clf.intercept_, dtype=torch.float32)})
    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model": final.state_dict(), "classes": CLASES,
                "preprocesamiento": "foto completa RGB -> Resize((224,224)) -> Normalize ImageNet"},
               args.salida)
    print(f"[OK] Modelo guardado en {args.salida}")


if __name__ == "__main__":
    main()
