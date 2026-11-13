# GreenBin — Sistema Inteligente de Gestión de Residuos

Proyecto del semillero **FetSociety** — Fundación Escuela Tecnológica de Neiva (FET)
Programa: Ingeniería de Software

GreenBin reconoce un residuo con una cámara y le indica por voz a la persona en qué caneca
depositarlo, según el código de colores de la Resolución 2184 de 2019:

| Categoría        | Caneca  |
|------------------|---------|
| Aprovechable     | Blanca  |
| No aprovechable  | Negra   |
| Orgánico         | Verde   |

---

## Versión 2 (noviembre de 2026): Raspberry Pi + panel web

```
Raspberry Pi 4 (raspberry/)                        Portátil (panel_web/)
sensor HC-SR04 → cámara OV5647 → ResNet18 → 🔊     backend FastAPI + SQLite → panel Angular
                         └── envía solo el resultado (sin imágenes) ──┘
```

```
raspberry/
├── scripts/
│   ├── clasificar_pi.py       # Programa principal en la Raspberry Pi
│   ├── entrenar_v2.py         # Entrena el modelo v1 (extractor congelado + regresión logística)
│   ├── captura_automatica.py  # Captura fotos para el dataset con el sensor
│   └── capturar_dataset.py
├── pruebas/                   # Pruebas de cámara y sensor
├── modelos/
│   ├── greenbin_resnet18_v1.pt            # Modelo v1 (73–77 % en validación cruzada)
│   └── face_detection_yunet_2023mar.onnx  # Pixelado de rostros en fotos dudosas
├── audios/                    # Mensajes de voz (edge-tts, es-CO) y su generador
└── dataset_v1/etiquetas.csv   # Etiquetas del dataset (las fotos no se suben)
panel_web/                     # Panel Angular 17 + backend FastAPI (ver su README)
docs/reporte_modelo_v1.md      # Datos, método, evaluación y pruebas del modelo
herramientas/encuesta_greenbin_forms.gs  # Genera la encuesta en Google Forms
```

### Ejecutar en la Raspberry Pi
```bash
cd raspberry
python3 -m venv --system-site-packages .venv && source .venv/bin/activate
pip install torch torchvision pillow "opencv-python-headless==4.10.0.84"
sudo apt install -y mpg123
python -u scripts/clasificar_pi.py                    # sin panel
python -u scripts/clasificar_pi.py --panel http://IP-DEL-PORTATIL:8000 --token LA-CLAVE
```

### Ejecutar el panel
Ver `panel_web/README.md` (en Windows: doble clic en `panel_web/backend/iniciar_panel.bat`).

### Privacidad
- El dataset de fotos **no está en el repositorio**: 39 de las 147 fotos muestran rostros (RNF-05, Ley 1581 de 2012).
- La Raspberry Pi no envía imágenes; solo guarda localmente las fotos dudosas, con los rostros pixelados.

---

## Versión 1 (mayo de 2026): prototipo en el portátil

Los archivos de la raíz (`capturar_dataset.py`, `entrenar.py`, `demo_webcam.py`,
`fewshot_desde_imagenes.py`, `modelos/greenbin_resnet18.pt`) son el prototipo de mayo,
que clasificaba con la cámara del computador y mostraba el resultado en pantalla.
Se conservan como referencia.

```bash
pip install torch torchvision opencv-python pillow numpy
python demo_webcam.py
```

---

## Autores

- Juan Felipe Bahamon Castillo
- José Eduar Ramírez Cardona
- Santiago Tovar Vargas

Tutora: Viviana Muñoz Álvarez
Semillero FetSociety — FET Neiva, 2026
