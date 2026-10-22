import pandas as pd
import pytest
import yaml

from triage.data.build_dataset import COLUMNAS, asignar_clase, construir, leer_crudos, limpiar, muestrear

LABEL_MAP = {
    "clases": {"tarjetas": ["Credit card"], "cobranza": ["Debt collection"]},
    "clase_por_defecto": "otros",
    "por_subproducto": {},
}


def datos(**columnas) -> pd.DataFrame:
    base = {"complaint_id": ["3", "1", "2"], "fecha": ["2023-01-03", "2023-01-01", "2023-01-02"],
            "producto": ["Credit card", "Debt collection", "Mortgage"],
            "subproducto": [None, None, None], "texto": ["a", "b", "c"]}
    base.update(columnas)
    return pd.DataFrame(base)


def test_limpiar_quita_vacios_y_ordena():
    df = limpiar(datos(texto=["hola", "  ", "adios"]))
    assert list(df["complaint_id"]) == [2, 3]


def test_limpiar_quita_textos_duplicados():
    df = limpiar(datos(texto=["Mismo  texto", "mismo texto", "otro"]))
    assert len(df) == 2
    assert 1 in set(df["complaint_id"])  # se conserva el más antiguo


def test_asignar_clase_usa_mapa_y_clase_por_defecto():
    clases = asignar_clase(datos(), LABEL_MAP)
    assert list(clases) == ["tarjetas", "cobranza", "otros"]


def test_subproducto_tiene_prioridad():
    label_map = {**LABEL_MAP, "por_subproducto": {"Gift card": "prepago"}}
    df = datos(subproducto=["Gift card", None, None])
    assert asignar_clase(df, label_map).iloc[0] == "prepago"


def test_muestrear_respeta_tope_y_es_determinista():
    df = pd.DataFrame({"complaint_id": range(100), "clase": ["a"] * 80 + ["b"] * 20})
    m1 = muestrear(df, max_por_clase=10, seed=42)
    m2 = muestrear(df, max_por_clase=10, seed=42)
    assert m1["clase"].value_counts().max() == 10
    assert m1.equals(m2)


@pytest.mark.parametrize("usar_csv,usar_parquet", [(True, True), (True, False), (False, True)])
@pytest.mark.parametrize("columnas_originales", [True, False])
def test_leer_crudos_combina_csv_y_parquet(tmp_path, usar_csv, usar_parquet, columnas_originales):
    raw = tmp_path / "raw"
    landing = tmp_path / "landing"
    original = datos().rename(columns={v: k for k, v in COLUMNAS.items()})
    if usar_csv:
        raw.mkdir()
        original.iloc[:1].to_csv(raw / "reclamos.csv", index=False)
    if usar_parquet:
        landing.mkdir()
        parquet = original if columnas_originales else datos()
        # Dos archivos para comprobar que se incorporan todos y en orden.
        parquet.iloc[1:2].to_parquet(landing / "a.parquet", index=False)
        parquet.iloc[2:].to_parquet(landing / "b.parquet", index=False)

    resultado = leer_crudos(str(raw), str(landing))

    ids = ([3] if usar_csv else []) + ([1, 2] if usar_parquet else [])
    assert resultado["complaint_id"].astype(int).tolist() == ids
    assert resultado.columns.tolist() == list(COLUMNAS.values())
    assert resultado["texto"].tolist() == (["a"] if usar_csv else []) + (["b", "c"] if usar_parquet else [])


def test_leer_crudos_sin_archivos_informa_ambas_fuentes(tmp_path):
    with pytest.raises(FileNotFoundError, match=r"\.csv.*\.parquet"):
        leer_crudos(str(tmp_path / "raw"), str(tmp_path / "landing"))


def test_construir_integra_landing_con_deduplicacion_y_split_temporal(tmp_path):
    raw = tmp_path / "raw"
    landing = tmp_path / "landing"
    raw.mkdir()
    landing.mkdir()
    df = datos(fecha=["2023-01-03", "2023-11-01", "2023-12-02"])
    df.iloc[:1].rename(columns={v: k for k, v in COLUMNAS.items()}).to_csv(
        raw / "reclamos.csv", index=False
    )
    particion = landing / "fecha=2023-11-01"
    particion.mkdir()
    df.to_parquet(particion / "reclamos.parquet", index=False)
    mapa = tmp_path / "label_map.yaml"
    mapa.write_text(yaml.safe_dump(LABEL_MAP), encoding="utf-8")
    params = {
        "data": {"raw_dir": str(raw), "landing_dir": str(landing), "label_map": str(mapa)},
        "seed": 42,
        "sample": {"max_por_clase_train": 10, "max_por_clase_val": 10},
        "split": {"val_start": "2023-11-01"},
    }

    train, val = construir(params)

    assert train["complaint_id"].tolist() == [3]  # Duplicado CSV/Parquet eliminado.
    assert val["complaint_id"].tolist() == [1, 2]
    assert train["clase"].tolist() == ["tarjetas"]
    assert val["clase"].tolist() == ["cobranza", "otros"]
    assert (train["fecha"] < pd.Timestamp("2023-11-01")).all()
    assert (val["fecha"] >= pd.Timestamp("2023-11-01")).all()
