# Triage de reclamos

Caso de estudio del curso **Product Development** (Maestría en Data Science, Universidad Galileo).

Un servicio que recibe el texto de un reclamo financiero y lo asigna al equipo responsable.
Datos: narrativas públicas de reclamos del CFPB.

```bash
pip install -r requirements.txt
make data    # construye data/processed/
make train   # entrena el baseline y escribe metrics.json
make test    # ejecuta las pruebas
```

`make data` combina los CSV de `data/raw/` con los archivos `*.parquet` de
`data/landing/`, incluidas sus subcarpetas (configurable con `data.landing_dir`
en `params.yaml`). Puede
trabajar con una sola de las fuentes si la otra está vacía o no existe.
Los Parquet pueden usar las columnas originales del CFPB o los nombres internos
del proyecto. La limpieza, deduplicación y separación temporal se aplican al
conjunto combinado; `data/golden/` se reserva para evaluación.
