# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GreenBin classifies solid waste in real time using a webcam and ResNet18. It maps each waste item to the correct bin color defined by Colombia's Resolución 2184 de 2019: **Verde** (orgánico), **Blanca** (aprovechable), **Negra** (no aprovechable).

## Environment Setup

Python 3.9+ with a `.venv` already present in the repo root.

```powershell
.venv\Scripts\activate
pip install torch torchvision opencv-python pillow numpy
```

## Running the Scripts

There are two independent usage paths — no shared entry point.

**Path A — full training:**
```powershell
python capturar_dataset.py      # collect ≥50 images per class
python entrenar.py              # trains ResNet18, saves modelos/greenbin_resnet18.pt
python demo_webcam.py           # live inference with trained model
```

**Path B — few-shot (no training needed):**
```powershell
# Place one reference image per class in ejemplos/ first
python fewshot_desde_imagenes.py
```

## Architecture

The project is four standalone scripts with no shared modules, packages, or tests.

### Shared conventions across all scripts
- **ROI**: all scripts crop the center 60% of the frame (`calcular_roi`) before processing — dataset capture, training, and inference all use the same region.
- **Normalization**: ImageNet mean/std `[0.485, 0.456, 0.406]` / `[0.229, 0.224, 0.225]` — must be consistent across capture, training, and inference.
- **BGR → RGB**: OpenCV reads frames as BGR; every script converts to RGB before passing to torchvision transforms.
- **Prediction smoothing** (`demo_webcam.py`, `fewshot_desde_imagenes.py`): a sliding window of the last 5 frames picks the modal class and averages its confidence to reduce flicker.

### Path A model lifecycle
- `capturar_dataset.py` writes 224×224 JPEGs into `dataset/{organico,aprovechable,no_aprovechable}/`.
- `entrenar.py` uses `torchvision.datasets.ImageFolder` on that directory, fine-tunes ResNet18 (only `fc` is replaced), and saves the checkpoint as `{"model": state_dict, "classes": list}` to `modelos/greenbin_resnet18.pt`. The best checkpoint by val accuracy is kept; a `ReduceLROnPlateau` scheduler fires after 3 stagnant epochs.
- `demo_webcam.py` reconstructs the exact same ResNet18 architecture, loads the checkpoint, and runs softmax inference per frame.

### Path B feature extraction
- `fewshot_desde_imagenes.py` uses ResNet18 with `fc = Identity()` to get 512-d embeddings.
- At startup it computes a **centroid** (mean of L2-normalized embeddings) for each class from the reference images in `EJEMPLOS`.
- At inference time it picks the class whose centroid has the highest **cosine similarity** to the current ROI embedding. Threshold is 0.55 (vs. 0.70 in Path A).

### Key configuration constants (per-file, at the top of each script)
| Constant | File | Default | Purpose |
|---|---|---|---|
| `N` | capturar_dataset.py | 200 | Max images per class |
| `FRAC` | capturar_dataset.py | 0.6 | ROI fraction |
| `EPOCHS` | entrenar.py | 10 | Training epochs |
| `TH` | demo_webcam.py | 0.70 | Confidence threshold |
| `SUAVIZADO` | demo_webcam.py / fewshot | 5 | Smoothing window |
| `CAM_INDEX` | demo_webcam.py / fewshot | 0 | Webcam index |

## Generated Directories (not committed)
- `dataset/` — created by `capturar_dataset.py`
- `modelos/` — created by `entrenar.py`
- `ejemplos/` — must be populated manually for few-shot mode
