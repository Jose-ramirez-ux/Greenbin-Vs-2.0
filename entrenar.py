"""
GreenBin - Entrenamiento del clasificador
Entrena un modelo ResNet18 con transfer learning sobre el dataset capturado.
Guarda el mejor modelo según la exactitud de validación.

Uso:
    python entrenar.py
"""

import os
import torch
from torchvision import datasets, transforms, models
from torch.utils.data import DataLoader, random_split
from torch import nn, optim

# ── Configuración ────────────────────────────────────────────────────────────
DATA   = "dataset"
OUT    = "modelos"
BATCH  = 32
EPOCHS = 10       # aumentado de 6 a 10 para mejor convergencia
LR     = 1e-3
IMG    = 224
SEED   = 42       # para reproducibilidad del split
# ─────────────────────────────────────────────────────────────────────────────

def obtener_transforms():
    """Devuelve los transforms de entrenamiento y validación."""
    tf_train = transforms.Compose([
        transforms.Resize((IMG, IMG)),
        transforms.ColorJitter(0.2, 0.2, 0.2, 0.1),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),        # nueva: rotación leve
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406],
                             [0.229, 0.224, 0.225]),
    ])
    tf_val = transforms.Compose([
        transforms.Resize((IMG, IMG)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406],
                             [0.229, 0.224, 0.225]),
    ])
    return tf_train, tf_val

def cargar_datos(tf_train, tf_val):
    """Carga el dataset y hace el split train/val."""
    full = datasets.ImageFolder(DATA, transform=tf_train)
    if len(full) == 0:
        raise SystemExit("[ERROR] Dataset vacío. Ejecuta primero capturar_dataset.py")

    n       = len(full)
    n_val   = max(1, int(0.15 * n))
    n_tr    = n - n_val

    generator = torch.Generator().manual_seed(SEED)
    tr, va  = random_split(full, [n_tr, n_val], generator=generator)
    va.dataset.transform = tf_val   # validación sin augmentación

    print(f"[INFO] Dataset: {n} imágenes | "
          f"Train: {n_tr} | Val: {n_val} | "
          f"Clases: {full.classes}")
    return tr, va, full.classes

def construir_modelo(n_clases, device):
    """Crea un ResNet18 preentrenado con la capa final adaptada."""
    model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
    model.fc = nn.Linear(model.fc.in_features, n_clases)
    return model.to(device)

def entrenar_epoch(model, loader, crit, opt, device):
    """Ejecuta una época de entrenamiento y devuelve la pérdida promedio."""
    model.train()
    loss_sum = 0.0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        opt.zero_grad()
        out  = model(x)
        loss = crit(out, y)
        loss.backward()
        opt.step()
        loss_sum += loss.item() * x.size(0)
    return loss_sum / max(1, len(loader.dataset))

def evaluar(model, loader, device):
    """Evalúa el modelo en el loader dado y devuelve la exactitud."""
    model.eval()
    cor = tot = 0
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            pred  = model(x).argmax(1)
            cor  += (pred == y).sum().item()
            tot  += y.size(0)
    return cor / max(1, tot)

def guardar_modelo(model, classes, ruta):
    """Guarda el state_dict del modelo y la lista de clases."""
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    torch.save({"model": model.state_dict(), "classes": classes}, ruta)

def main():
    os.makedirs(OUT, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[INFO] Dispositivo: {device}")

    tf_train, tf_val         = obtener_transforms()
    tr, va, classes          = cargar_datos(tf_train, tf_val)
    n_clases                 = len(classes)

    tr_loader = DataLoader(tr, batch_size=BATCH, shuffle=True,  num_workers=0)
    va_loader = DataLoader(va, batch_size=BATCH, shuffle=False, num_workers=0)

    model = construir_modelo(n_clases, device)
    crit  = nn.CrossEntropyLoss()
    opt   = optim.Adam(model.parameters(), lr=LR)

    # Scheduler: reduce LR si la val_acc no mejora en 3 épocas
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        opt, mode="max", patience=3, factor=0.5
    )

    ruta_modelo = os.path.join(OUT, "greenbin_resnet18.pt")
    mejor_acc   = 0.0

    print(f"\n{'Época':>6}  {'Loss':>8}  {'Val Acc':>8}  {'Estado':}")
    print("-" * 45)

    for ep in range(1, EPOCHS + 1):
        loss    = entrenar_epoch(model, tr_loader, crit, opt, device)
        val_acc = evaluar(model, va_loader, device)
        scheduler.step(val_acc)

        estado = ""
        if val_acc >= mejor_acc:
            mejor_acc = val_acc
            guardar_modelo(model, classes, ruta_modelo)
            estado = "✓ guardado"

        print(f"{ep:>6}  {loss:>8.4f}  {val_acc:>8.3f}  {estado}")

    print(f"\n[OK] Entrenamiento finalizado. Mejor val_acc: {mejor_acc:.3f}")
    print(f"[OK] Modelo guardado en: {ruta_modelo}")

if __name__ == "__main__":
    main()
