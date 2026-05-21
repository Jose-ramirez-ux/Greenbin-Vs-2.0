# GreenBin — Sistema Inteligente de Gestión de Residuos

Proyecto del semillero **FetSociety** — Fundación Escuela Tecnológica de Neiva  
Programa: Ingeniería de Software

---

## ¿Qué hace GreenBin?

GreenBin clasifica residuos sólidos en tiempo real mediante la cámara del computador
y muestra en pantalla la caneca correcta según el código de colores de la
Resolución 2184 de 2019 (Colombia):

| Categoría        | Caneca  |
|------------------|---------|
| Orgánico         | Verde   |
| Aprovechable     | Blanca  |
| No aprovechable  | Negra   |

---

## Requisitos

```bash
pip install torch torchvision opencv-python pillow numpy
```

> Se recomienda Python 3.9 o superior.

---

## Estructura del proyecto

```
GreenBin/
├── capturar_dataset.py       # Captura imágenes para entrenar
├── entrenar.py               # Entrena el modelo ResNet18
├── demo_webcam.py            # Demo con modelo entrenado
├── fewshot_desde_imagenes.py # Demo sin entrenamiento (few-shot)
├── dataset/                  # Se crea al correr capturar_dataset.py
│   ├── organico/
│   ├── aprovechable/
│   └── no_aprovechable/
├── modelos/                  # Se crea al entrenar
│   └── greenbin_resnet18.pt
└── ejemplos/                 # Imágenes de referencia para few-shot
    ├── organico_tomate.jpg
    ├── aprovechable_botella.jpg
    └── no_aprovechable_papel.jpg
```

---

## Flujo de uso — opción A: con entrenamiento

### Paso 1 — Capturar imágenes
```bash
python capturar_dataset.py
```
- Presiona **ESPACIO** para guardar una imagen de la clase actual.
- Presiona **Q** para cambiar de clase.
- Presiona **ESC** para terminar.
- Se recomienda al menos 50 imágenes por clase.

### Paso 2 — Entrenar
```bash
python entrenar.py
```
El modelo se guarda automáticamente en `modelos/greenbin_resnet18.pt`.

### Paso 3 — Demo en tiempo real
```bash
python demo_webcam.py
```

---

## Flujo de uso — opción B: few-shot (sin entrenamiento)

Solo necesitas una imagen de referencia por clase en la carpeta `ejemplos/`.

```bash
python fewshot_desde_imagenes.py
```

Esta opción es más rápida de configurar pero puede ser menos precisa
que la opción con entrenamiento.

---

## Controles comunes

| Tecla     | Acción              |
|-----------|---------------------|
| Q / ESC   | Salir               |
| ESPACIO   | Guardar imagen (solo en capturar_dataset.py) |
| Q         | Cambiar clase (solo en capturar_dataset.py)  |

---

## Autores

- Juan Felipe Bahamon Castillo
- José Eduar Ramírez Cardona
- Santiago Tovar Vargas

Tutora: Viviana Muñoz Álvarez  
Semillero FetSociety — FET Neiva, 2026
