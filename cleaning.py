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
        df[column] = df[column].astype("boolean")
    elif dtype == "datetime":
        df[column] = pd.to_datetime(df[column], errors="coerce")
        
    return df

# Valores ausentes
def fill_value(df, column, value):
    df[column] = df[column].fillna(value)
    
    return df

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

def median_by_category(df, target_col, category_col):

    medians = (df.groupby(category_col)[target_col].median())

    mask = df[target_col].isna()

    df.loc[mask, target_col] = (df.loc[mask, category_col].map(medians))

    return df

# Tratando outliers
def _iqr_bounds(df, column, factor):
    q1 = df[column].quantile(0.25)
    q3 = df[column].quantile(0.75)
    iqr = q3 - q1
    return q1 - factor * iqr, q3 + factor * iqr


def clip_outliers_iqr(df, column, factor=1.5):
    lower, upper = _iqr_bounds(df, column, factor)
    df[column] = df[column].clip(lower=lower, upper=upper)
    return df

# Pipeline de limpeza
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

def apply_outlier_rule(df, rule, outlier_report=None):
    if rule["method"] != "iqr" or rule["action"] not in {"clip", "flag"}:
        return df

    column = rule["column"]
    factor = rule.get("factor", 1.5)
    lower, upper = _iqr_bounds(df, column, factor)
    outlier_mask = (
        (df[column] < lower) | (df[column] > upper)
    ).fillna(False)
    outlier_count = int(outlier_mask.sum())

    if outlier_report is not None:
        column_report = {
            "found": outlier_count,
            "changed": outlier_count if rule["action"] == "clip" else 0,
            "lower_bound": float(lower),
            "upper_bound": float(upper),
        }

        if rule["action"] == "flag":
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

    if rule["action"] == "clip":
        df[column] = df[column].clip(lower=lower, upper=upper)

    return df

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