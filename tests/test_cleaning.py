import pandas as pd
import pytest

from cleaning import apply_outlier_rule, clean_dataframe

@pytest.mark.parametrize("column", ["Quantity", "Total Spent"])
def test_flag_sinaliza_outlier_sem_alterar_valor(column):
    # Criando um DataFrame de teste
    data = {
        "Transaction ID": [f"TXN-{i}" for i in range(8)],
        column: [10, 20, 30, 1000, 50, 60, 70, 80],  # 1000 é um outlier
    }
    df = pd.DataFrame(data)
    original = df[column].tolist()
    report = {}

    # Definindo a regra de outlier para flag
    apply_outlier_rule(
        df,
        {
            "method": "iqr",
            "column": column,
            "factor": 1.5,
            "action": "flag",
            "id_column": "Transaction ID"
        },
        report,
    )

    # Verificando se o valor do outlier não foi alterado
    assert df[column].tolist() == original

    # Verificando se o relatório de outliers contém a informação correta
    assert report[column]["found"] == 1
    assert report[column]["changed"] == 0
    assert report[column]["flagged_rows"][0]["transaction_id"] == "TXN-3"
    assert report[column]["flagged_rows"][0]["value"] == 1000.0

    # Verificando os limites calculados para o outlier
    assert report[column]["lower_bound"] == pytest.approx(-40.0)
    assert report[column]["upper_bound"] == pytest.approx(140.0)

    # Verificando se a lista de linhas sinalizadas no relatório corresponde ao outlier identificado
    assert report[column]["flagged_rows"] == [
        {"transaction_id": "TXN-3", "value": 1000.0}
    ]

def test_apenas_colunas_clip_sao_alteradas():
    values = [10, 20, 30, 40, 50, 60, 70, 1000]
    original = pd.DataFrame({
        "Transaction ID": [f"TXN-{i}" for i in range(8)],
        "Quantity": values,
        "Total Spent": values,
    })
    df = original.copy(deep=True)
    report = {}

    config = {
        "columns": [],
        "outliers": [
            {
                "column": "Quantity",
                "method": "iqr",
                "factor": 1.5,
                "action": "clip",
            },
            {
                "column": "Total Spent",
                "method": "iqr",
                "factor": 1.5,
                "action": "flag",
                "id_column": "Transaction ID"
            },
        ]
    }

    cleaned = clean_dataframe(df, config, outlier_report=report)

    changed_columns = [
        column for column in original.columns if not cleaned[column].equals(original[column])
    ]

    # Verificando se apenas a coluna "Quantity" foi alterada
    assert changed_columns == ["Quantity"]
    
    # Verificando se o valor do outlier na coluna "Quantity" foi alterado para o limite superior
    assert cleaned.loc[7, "Quantity"] == report["Quantity"]["upper_bound"]
    
    # Verificando se o valor do outlier na coluna "Total Spent" não foi alterado
    assert report["Quantity"]["changed"] == 1
    assert report["Total Spent"]["found"] == 1
    assert report["Total Spent"]["changed"] == 0