import pandas as pd

# Conversão de tipos
def cast_column(df, column, dtype):
    if dtype == "string":
        df[column] = df[column].astype("string")
    elif dtype == "float":
        df[column] = pd.to_numeric(df[column], errors="coerce")
    elif dtype == "integer":
        df[column] = (pd.to_numeric(df[column], errors="coerce").round().astype("Int64"))
    elif dtype == "boolean":
        boolean_values = df[column].astype("string").str.casefold()
        df[column] = boolean_values.map({"true": True, "false": False}).astype("boolean")
    elif dtype == "datetime":
        df[column] = pd.to_datetime(df[column], errors="coerce")
        
    return df

# Trata valores ausentes
def fill_value(df, column, value):
    df[column] = df[column].fillna(value)
    
    return df

# Preenche valores ausentes com base em colunas relacionadas
def derive_column(df, target, sources):

    if target == "Price Per Unit":
        total_col, qty_col = sources
        
        mask = (
            df[target].isna()
            & df[total_col].notna()
            & df[qty_col].notna()
            & (df[qty_col] != 0)
        )
        
        df.loc[mask, target] = (df.loc[mask, total_col] / df.loc[mask, qty_col])
        
    elif target == "Quantity":
        total_col, price_col = sources
        
        mask = (
            df[target].isna()
            & df[total_col].notna()
            & df[price_col].notna()
            & (df[price_col] != 0)
        )
        
        df.loc[mask, target] = (df.loc[mask, total_col] / df.loc[mask, price_col]).round()
        
    elif target == "Total Spent":
        price_col, qty_col = sources
        
        mask = (
            df[target].isna()
            & df[price_col].notna()
            & df[qty_col].notna()
        )
        
        df.loc[mask, target] = (df.loc[mask, price_col] * df.loc[mask, qty_col])
        
    return df

# Caso não seja possível derivar o valor, preenche com a mediana da categoria
def median_by_category(df, target_col, category_col):

    medians = (df.groupby(category_col)[target_col].median())

    mask = df[target_col].isna()

    df.loc[mask, target_col] = (df.loc[mask, category_col].map(medians))

    return df

# Identifica outliers usando o método do IQR e retorna os limites inferior e superior
def _iqr_bounds(df, column, factor):
    q1 = df[column].quantile(0.25)
    q3 = df[column].quantile(0.75)
    iqr = q3 - q1
    return q1 - factor * iqr, q3 + factor * iqr

# Trata os valores ausentes de acordo com as regras definidas no config.yml
def apply_missing_rule(df, column, rule):
    strategy = rule["strategy"]
    
    if strategy == "fill_value":
        return fill_value(df, column, rule["value"])
    
    elif strategy == "derive":
        df = derive_column(df, column, rule["derive_from"])
        fallback = rule.get("fallback")
        
        if fallback:
            if fallback["strategy"] == "median_by_category":
                df = median_by_category(df, column, fallback["group_col"])
    
    return df

# Aplica a regra de outlier ao DataFrame e atualiza o relatório de outliers
def apply_outlier_rule(df, rule, outlier_report=None):
    if rule["method"] != "iqr":
        return df

    column = rule["column"]
    factor = rule.get("factor", 1.5)
    lower, upper = _iqr_bounds(df, column, factor)
    outlier_mask = (
        (df[column] < lower) | (df[column] > upper)
    ).fillna(False)
    outlier_count = int(outlier_mask.sum())
    flag_column = rule.get("flag_column", f"{column}_is_outlier")
    df[flag_column] = outlier_mask

    if outlier_report is not None:
        column_report = {
            "found": outlier_count,
            "lower_bound": float(lower),
            "upper_bound": float(upper),
            "flag_column": flag_column,
        }

        id_column = rule.get("id_column")
        if id_column:
            column_report["flagged_rows"] = [
                {
                    "transaction_id": str(transaction_id),
                    "value": float(value),
                }
                for transaction_id, value in zip(
                    df.loc[outlier_mask, id_column],
                    df.loc[outlier_mask, column],
                )
            ]
        else:
            column_report["flagged_rows"] = [
                {"row_index": str(index), "value": float(value)}
                for index, value in df.loc[outlier_mask, column].items()
            ]

        outlier_report[column] = column_report

    return df

# Verifica se os valores do DataFrame atendem às regras de validação e retorna um relatório detalhado
def validate_dataframe(df, rules, id_column=None):
    validation_results = []

    for rule in rules:
        column = rule["column"]
        rule_type = rule["type"]

        if rule_type == "non_negative":
            values = df[column]
            numeric_values = pd.to_numeric(values, errors="coerce")
            not_numeric = values.notna() & numeric_values.isna()
            negative = numeric_values < 0
            invalid_mask = not_numeric | negative
        
        elif rule_type == "allowed_values":
            invalid_mask = df[column].notna() & ~df[column].isin(rule["values"])
        
        elif rule_type == "boolean_values":
            boolean_values = df[column].astype("string").str.casefold()
            invalid_mask = df[column].notna() & ~boolean_values.isin(["true", "false"])
        
        elif rule_type == "date_format":
            date_format = rule["format"]
            parsed_dates = pd.to_datetime(df[column], format=date_format, errors="coerce")
            formatted_dates = parsed_dates.dt.strftime(date_format)
            format_matches = df[column].astype("string").eq(formatted_dates).fillna(False)
            invalid_mask = df[column].notna() & (parsed_dates.isna() | ~format_matches)
        
        elif rule_type == "not_future":
            parsed_dates = pd.to_datetime(df[column], errors="coerce")
            today = pd.Timestamp.now().normalize()
            invalid_mask = parsed_dates.notna() & (parsed_dates.dt.normalize() > today)
        
        else:
            raise ValueError(f"Tipo de validação não suportado: {rule_type}")

        # Sinaliza as linhas com valores inválidos sem altera-los
        flagged_rows = []
        for index in df.index[invalid_mask]:
            value = df.at[index, column]
            if hasattr(value, "item"):
                value = value.item()

            if rule_type == "non_negative":
                reason = "not_numeric" if not_numeric.loc[index] else "negative"
            elif rule_type == "boolean_values":
                reason = "not_boolean"
            elif rule_type == "date_format":
                reason = "invalid_format"
            elif rule_type == "not_future":
                reason = "future_date"
            else:
                reason = "not_allowed"

            row = {
                "row_index": str(index),
                "value": value,
                "reason": reason,
            }
            if id_column and id_column in df.columns:
                row["transaction_id"] = str(df.at[index, id_column])
            flagged_rows.append(row)

        if rule_type == "not_future":
            df.loc[invalid_mask, column] = pd.NaT
        
        validation_results.append({
            "column": column,
            "rule": rule_type,
            "found": len(flagged_rows),
            "flagged_rows": flagged_rows,
        })

    return {
        "issues_found": sum(result["found"] for result in validation_results),
        "rules": validation_results,
    }

# Orquestra o processo de limpeza de dados
def clean_dataframe(df, config, outlier_report=None):
    # Conversão de tipos
    for col_cfg in config["columns"]:
        df = cast_column(df, col_cfg["name"], col_cfg["type"])
    
    # Valores ausentes
    for col_cfg in config["columns"]:
        df = apply_missing_rule(df, col_cfg["name"], col_cfg["missing"])
        
    # Tratamento de outliers
    for rule in config.get("outliers", []):
        df = apply_outlier_rule(df, rule, outlier_report)
    
    return df