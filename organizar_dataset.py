"""
GreenBin - Reorganizador de dataset
Copia las imágenes de TrashNet (dataset-resized) a la estructura
de 3 clases que necesita entrenar.py:

    dataset/
        aprovechable/
        no_aprovechable/
        organico/

Uso:
    1. Coloca este script en la misma carpeta donde está dataset-resized/
    2. Ejecuta: python organizar_dataset.py
    3. Mueve tus fotos propias a dataset/organico/ manualmente
"""

import shutil
import os

# ── Configuración ─────────────────────────────────────────────────────────────
SRC = "dataset-resized"   # carpeta del dataset de TrashNet
DST = "dataset"           # carpeta destino (la que usa entrenar.py)

# Mapeo: categoría TrashNet → clase GreenBin
MAPEO = {
    "cardboard": "aprovechable",
    "paper":     "aprovechable",
    "plastic":   "aprovechable",
    "glass":     "aprovechable",
    "metal":     "no_aprovechable",
    "trash":     "no_aprovechable",
}
# ──────────────────────────────────────────────────────────────────────────────

EXTENSIONES = (".jpg", ".jpeg", ".png")


def crear_estructura():
    """Crea las carpetas destino si no existen."""
    for clase in ["aprovechable", "no_aprovechable", "organico"]:
        os.makedirs(os.path.join(DST, clase), exist_ok=True)
    print(f"[OK] Estructura creada en '{DST}/'")


def copiar_imagenes():
    """Copia las imágenes de cada categoría TrashNet a su clase GreenBin."""
    conteo = {"aprovechable": 0, "no_aprovechable": 0, "organico": 0}

    for origen, destino in MAPEO.items():
        origen_path = os.path.join(SRC, origen)

        if not os.path.exists(origen_path):
            print(f"[AVISO] No se encontró la carpeta: {origen_path}")
            continue

        imagenes = [f for f in os.listdir(origen_path)
                    if f.lower().endswith(EXTENSIONES)]

        for img in imagenes:
            src_file = os.path.join(origen_path, img)
            # Prefijo para evitar nombres duplicados entre categorías
            dst_file = os.path.join(DST, destino, f"{origen}_{img}")
            if not os.path.exists(dst_file):
                shutil.copy2(src_file, dst_file)
                conteo[destino] += 1

        print(f"[OK] {origen:12} → {destino:16} ({len(imagenes)} imágenes)")

    return conteo


def resumen(conteo):
    """Muestra el resumen final y advertencias."""
    print("\n─── Resumen del dataset ───────────────────────────────")
    total = sum(conteo.values())
    for clase, n in conteo.items():
        pct = (n / total * 100) if total > 0 else 0
        barra = "█" * int(pct / 2)
        print(f"  {clase:20} {n:>5} imgs  {pct:4.1f}%  {barra}")
    print(f"  {'TOTAL':20} {total:>5} imgs")

    print("\n─── Advertencias ──────────────────────────────────────")
    if conteo["organico"] == 0:
        print("  ⚠  organico/ está vacío.")
        print("     Mueve tus fotos propias a dataset/organico/ manualmente.")
    elif conteo["organico"] < 50:
        print(f"  ⚠  Solo {conteo['organico']} imágenes en organico/.")
        print("     Recomendado: mínimo 50-100 para un buen entrenamiento.")

    if conteo["aprovechable"] > conteo["no_aprovechable"] * 3:
        print("  ⚠  Dataset desbalanceado: aprovechable tiene muchas más")
        print("     imágenes que no_aprovechable. Considera usar")
        print("     WeightedRandomSampler en entrenar.py.")

    print("\n[LISTO] Ahora puedes ejecutar: python entrenar.py")


def main():
    print("GreenBin - Reorganizador de dataset")
    print(f"Origen : {SRC}/")
    print(f"Destino: {DST}/\n")

    if not os.path.exists(SRC):
        print(f"[ERROR] No se encontró '{SRC}/'.")
        print("        Asegúrate de ejecutar este script desde la carpeta")
        print("        donde está la carpeta dataset-resized/")
        return

    crear_estructura()
    conteo = copiar_imagenes()
    resumen(conteo)


if __name__ == "__main__":
    main()  