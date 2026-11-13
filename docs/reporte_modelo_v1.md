# GreenBin — Modelo v1: datos, método y resultados

Fecha: 22 de octubre de 2026 · Archivo: `modelos/greenbin_resnet18_v1.pt`

## 1. Datos
- Origen: fotos propias tomadas con la cámara Arducam OV5647 y el disparo por sensor HC-SR04, en la zona de cafetería de la FET, los días 7 y 13 de octubre de 2026.
- De 251 capturas se descartaron 104: 35 vacías, 31 oscuras, 22 de prueba (celulares, cinta, marcadores), 7 primeros planos o borrosas y 9 con el residuo ambiguo, con dos residuos o con interferencia.
- Dataset final (`dataset_v1/`): **147 fotos**, de unos 44 objetos o ráfagas distintos.

| Caneca | Fotos | Objetos o ráfagas |
|---|---|---|
| Blanca · aprovechable | 42 | 11 |
| Negra · no aprovechable | 93 | 28 |
| Verde · orgánico | 12 | 5 |

- Criterio de etiquetado: Resolución 2184 de 2019 y el criterio de la caracterización de la tesis. Los empaques metalizados, los pitillos y los vasos desechables usados van a la negra.
- `etiquetas.csv` incluye el **grupo** de cada foto: las tomas seguidas del mismo objeto comparten grupo.

## 2. Método
- Extractor: ResNet18 preentrenada en ImageNet, congelada (vector de 512 características).
- Clasificador: regresión logística con pesos balanceados por clase (C = 0,5), entrenada con la foto original y 4 versiones aumentadas: recorte aleatorio, volteo, color y rotación de ±10°.
- Entrada: **la foto completa** redimensionada a 224×224, sin recorte central.
- El clasificador se guardó como la capa `fc` de la ResNet18, en el formato `{"model", "classes"}` que usa `demo_webcam.py`.

## 3. Evaluación
Validación cruzada de 5 particiones **agrupada por objeto**: un mismo objeto nunca aparece a la vez en entrenamiento y en prueba.

| Método | Exactitud | F1-macro |
|---|---|---|
| Modelo de mayo (TrashNet), sin reentrenar | 29 % | 0,16 |
| Few-shot por centroides (sin entrenamiento) | 68 % | 0,59 |
| Ajuste fino de la última etapa (layer4 + fc) | 71 % | 0,65 |
| **Extractor congelado + clasificador lineal (elegido)** | **73–77 %** | **0,65–0,72** |
| Línea base: decir siempre "negra" | 63 % | 0,26 |

El rango del modelo elegido corresponde a distintas semillas de los aumentos aleatorios.

Matriz de confusión del modelo elegido (corrida con 76,9 %; filas = real, columnas = predicho):

| | Blanca | Negra | Verde |
|---|---|---|---|
| **Blanca** (42) | 27 | 15 | 0 |
| **Negra** (93) | 12 | 79 | 2 |
| **Verde** (12) | 1 | 4 | 7 |

Por clase: blanca, precisión 0,68 y sensibilidad 0,64 · negra, 0,81 y 0,85 · verde, 0,78 y 0,58.

Umbral de confianza (RF-06): con 70 %, el 88 % de las predicciones salen "seguras" y aciertan el 77,5 %. El umbral casi no separa aciertos de errores; el modelo está sobreconfiado.

## 4. Limitaciones
- Pocos datos, sobre todo en orgánico: 12 fotos de 5 objetos, así que sus métricas tienen mucha incertidumbre.
- El error más común es confundir blanca con negra: botellas y latas frente a empaques plásticos.
- Las fotos son de residuos sostenidos con la mano frente a la cafetería, con personas al fondo. El uso real (residuo depositado dentro de la caneca, con luz propia) es otro escenario y requiere recapturar ahí.
- 39 de las 147 fotos muestran rostros; hay que difuminarlos antes de publicar el dataset (RNF-05, Ley 1581 de 2012).

## 5. Reproducir
```
python scripts/entrenar_v2.py            # descarga los pesos ImageNet de torchvision
python scripts/clasificar_pi.py --imagen foto.jpg
python3 -u scripts/clasificar_pi.py      # en la Raspberry, con sensor y cámara
```
Requisitos: torch, torchvision, pillow, numpy, scikit-learn (opencv, gpiozero y picamera2 en la Pi).

## 6. Pruebas del sistema en la Raspberry Pi

Las pruebas se reportan por etapa y no se mezclan entre sí. Las revisiones manuales de canecas del 3 y 5 de noviembre **no son pruebas del modelo** (se hicieron sin la Raspberry Pi) y se documentan en la tesis, en *Resultados › Caracterización de residuos*.

| Fecha | Tipo de prueba | Clasif. | Con residuo real | Aciertos | Dudosas |
|---|---|---|---|---|---|
| 29 oct (mañana) | Por componente, una imagen de referencia por caneca (`--imagen`) | 3 | 3 | 3 | 0 |
| 29 oct, 20:35–21:04 | **Funcionamiento en la FET con estudiantes y docentes** | 44 | 41 (3 sin residuo) | **38 (92,7 %)** | 13 (29,5 %) |
| 31 oct | Pruebas funcionales con botellas plásticas | 3 | 3 | 3 (100 %) | 0 |
| 2 y 4 nov | Imagen de referencia verde enviada al panel | 3 | 3 | 3 | 0 |
| 10 nov | Cámara y residuos reales (1 botella, 2 latas, 5 envoltorios) | 8 | 8 | **5 (62,5 %)** | 0 |
| **Total con cámara y residuos reales** | 29 oct + 31 oct + 10 nov | 55 | 52 | **46 (88,5 %)** | 13 |

Las pruebas con imagen de referencia no entran en el total, porque la imagen pertenece al entrenamiento.

Matriz de confusión en campo (52 residuos; filas = caneca correcta, columnas = predicha):

| | Blanca | Negra | Verde |
|---|---|---|---|
| **Blanca** (20) | 15 | 5 | 0 |
| **Negra** (31) | 1 | 30 | 0 |
| **Verde** (1) | 0 | 0 | 1 |

Hallazgos:
- 29 oct: las 31 predicciones seguras fueron correctas; los 3 errores fueron dudosos. El umbral del 70 % funcionó.
- 10 nov: la botella y las 2 latas fueron a la negra con confianza alta (91,9–100 %). El error no se marcó como dudoso. Probable cambio de condiciones de captura (posición de la cámara en el soporte, fondo, luz): conviene recapturar y reentrenar.
- Las dudosas en uso real (29,5 %) superan las de la validación (12 %). El sensor se activa con personas (3 casos). El pixelado falló en 1 imagen.
- La clase orgánica tiene un solo residuo probado en campo: no es evaluable todavía.
- Primera medición del tiempo de respuesta (10 nov, 22:22): **1,44 s** de la detección al audio.

Pendiente para PR-08: pruebas con residuos de las tres canecas, anotando el residuo real de cada una. Desde el 10 de noviembre, `clasificar_pi.py` guarda el tiempo de respuesta (`tiempo_s`, desde la detección del sensor hasta el audio), y el panel lo exporta con el botón **Exportar CSV**.

Datos: `resultados/pruebas_sistema_consolidado.csv` (todas las etapas, desde el registro de la Pi y el panel) y `resultados/resultados_pruebas_2026-11-10.csv` (exportado del panel y anotado).
