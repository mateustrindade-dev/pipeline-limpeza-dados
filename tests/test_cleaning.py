import pandas as pd
import pytest

from cleaning import apply_outlier_rule, clean_dataframe, validate_dataframe

def test_validate_dataframe_registra_discount_applied_invalido():
    df = pd.DataFrame({
        "Transaction ID": ["TXN-1", "TXN-2", "TXN-3", "TXN-4", "TXN-5"],
        "Discount Applied": [True, False, "yes", None, "true"],
    })
    original = df.copy(deep=True)

    report = validate_dataframe(
        df,
        [{"column": "Discount Applied", "type": "boolean_values"}],
        id_column="Transaction ID",
    )

    assert report["issues_found"] == 1
    assert report["rules"][0]["flagged_rows"] == [
        {
            "row_index": "2",
            "value": "yes",
            "reason": "not_boolean",
            "transaction_id": "TXN-3",
        }
    ]
    pd.testing.assert_frame_equal(df, original)

    cleaned = clean_dataframe(
        df,
        {
            "columns": [{
                "name": "Discount Applied",
                "type": "boolean",
                "missing": {"strategy": "fill_value", "value": False},
            }]
        },
    )

    assert cleaned["Discount Applied"].tolist() == [True, False, False, False, True]

def test_validate_dataframe_registra_formato_de_data_invalido():
    df = pd.DataFrame({
        "Transaction ID": ["TXN-1", "TXN-2", "TXN-3", "TXN-4"],
        "Transaction Date": ["2024-01-15", "2024/01/16", "2024-02-30", None],
    })

    report = validate_dataframe(
        df,
        [{"column": "Transaction Date", "type": "date_format", "format": "%Y-%m-%d"}],
        id_column="Transaction ID",
    )

    assert report["issues_found"] == 2
    assert report["rules"][0]["flagged_rows"] == [
        {
            "row_index": "1",
            "value": "2024/01/16",
            "reason": "invalid_format",
            "transaction_id": "TXN-2",
        },
        {
            "row_index": "2",
            "value": "2024-02-30",
            "reason": "invalid_format",
            "transaction_id": "TXN-3",
        },
    ]

def test_validate_dataframe_anula_data_futura():
    df = pd.DataFrame({
        "Transaction ID": ["TXN-1", "TXN-2"],
        "Transaction Date": ["2024-01-01", "2999-12-31"],
    })

    report = validate_dataframe(
        df,
        [{"column": "Transaction Date", "type": "not_future"}],
        id_column="Transaction ID",
    )

    assert report["issues_found"] == 1
    assert report["rules"][0]["flagged_rows"] == [
        {
            "row_index": "1",
            "value": "2999-12-31",
            "reason": "future_date",
            "transaction_id": "TXN-2",
        }
    ]
    assert df.loc[0, "Transaction Date"] == "2024-01-01"
    assert pd.isna(df.loc[1, "Transaction Date"])

def test_validate_dataframe_registra_anomalias_sem_alterar_dados():
    df = pd.DataFrame({
        "Transaction ID": ["TXN-1", "TXN-2", "TXN-3", "TXN-4"],
        "Price Per Unit": [-2.5, "not-a-number", 10.0, 12.0],
        "Payment Method": ["Cash", "Credit Card", "Credit Crad", "Digital Wallet"],
        "Category": ["Food", "Beverages", "Foood", "Furniture"],
        "Location": ["Online", "In-store", "in-store", "Online"],
    })
    original = df.copy(deep=True)

    report = validate_dataframe(
        df,
        [
            {"column": "Price Per Unit", "type": "non_negative"},
            {
                "column": "Payment Method",
                "type": "allowed_values",
                "values": ["Cash", "Credit Card", "Digital Wallet"],
            },
            {
                "column": "Category",
                "type": "allowed_values",
                "values": [
                    "Beverages",
                    "Butchers",
                    "Computers and electric accessories",
                    "Electric household essentials",
                    "Food",
                    "Furniture",
                    "Milk Products",
                    "Patisserie",
                ],
            },
            {
                "column": "Location",
                "type": "allowed_values",
                "values": ["In-store", "Online"],
            },
        ],
        id_column="Transaction ID",
    )

    assert report["issues_found"] == 5
    assert report["rules"][0]["flagged_rows"] == [
        {"row_index": "0", "value": -2.5, "reason": "negative", "transaction_id": "TXN-1"},
        {"row_index": "1", "value": "not-a-number", "reason": "not_numeric", "transaction_id": "TXN-2"},
    ]
    assert report["rules"][1]["flagged_rows"] == [
        {"row_index": "2", "value": "Credit Crad", "reason": "not_allowed", "transaction_id": "TXN-3"},
    ]
    assert report["rules"][2]["flagged_rows"] == [
        {"row_index": "2", "value": "Foood", "reason": "not_allowed", "transaction_id": "TXN-3"},
    ]
    assert report["rules"][3]["flagged_rows"] == [
        {"row_index": "2", "value": "in-store", "reason": "not_allowed", "transaction_id": "TXN-3"},
    ]
    pd.testing.assert_frame_equal(df, original)

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
    assert df[f"{column}_is_outlier"].tolist() == [False, False, False, True, False, False, False, False]

    # Verificando se o relatório de outliers contém a informação correta
    assert report[column]["found"] == 1
    assert report[column]["flag_column"] == f"{column}_is_outlier"
    assert report[column]["flagged_rows"][0]["transaction_id"] == "TXN-3"
    assert report[column]["flagged_rows"][0]["value"] == 1000.0

    # Verificando os limites calculados para o outlier
    assert report[column]["lower_bound"] == pytest.approx(-40.0)
    assert report[column]["upper_bound"] == pytest.approx(140.0)

    # Verificando se a lista de linhas sinalizadas no relatório corresponde ao outlier identificado
    assert report[column]["flagged_rows"] == [
        {"transaction_id": "TXN-3", "value": 1000.0}
    ]

def test_regras_de_outlier_sinalizam_sem_alterar_valores():
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

    assert changed_columns == []
    assert cleaned.loc[7, "Quantity"] == 1000
    assert cleaned["Quantity_is_outlier"].tolist() == [False, False, False, False, False, False, False, True]
    assert cleaned["Total Spent_is_outlier"].tolist() == [False, False, False, False, False, False, False, True]
    assert report["Total Spent"]["found"] == 1