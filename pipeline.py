import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pandas as pd
import yaml

from cleaning import clean_dataframe, validate_dataframe

Path("logs").mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler("logs/pipeline.log", encoding="utf-8", maxBytes=5*1024*1024, backupCount=3),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

logger.info("Iniciando o pipeline de limpeza de dados.")

try:
    df = pd.read_csv("retail_store_sales.csv")
    logger.info(f"Arquivo CSV lido com sucesso. Número de linhas: {len(df)}")
except Exception:
    logger.exception("Erro ao ler o arquivo CSV.")
    raise

missing_before = df.isna().sum()
logger.info(f"Valores ausentes antes da limpeza:\n{missing_before}")

try:
    with open("config/config.yml", "r") as f:
        config = yaml.safe_load(f)
        logger.info("Arquivo de configuração lido com sucesso.")
except Exception:
    logger.exception("Erro ao ler o arquivo de configuração.")
    raise

validation_report = validate_dataframe(
    df,
    config.get("validations", []),
    id_column="Transaction ID",
)
logger.info("Validações concluídas: %d ocorrências encontradas.", validation_report["issues_found"])

outlier_report = {}

try:
    df_clean = clean_dataframe(df, config, outlier_report=outlier_report)
    logger.info("Limpeza de dados concluída com sucesso.")
except Exception:
    logger.exception("Erro ao aplicar a limpeza de dados.")
    raise

missing_after = df_clean.isna().sum()
logger.info(f"Valores ausentes após a limpeza:\n{missing_after}")

try:
    df_clean.to_csv("retail_store_sales_clean.csv", index=False)
    logger.info("Arquivo CSV limpo salvo com sucesso.")
except Exception:
    logger.exception("Erro ao salvar o arquivo CSV limpo.")
    raise

report = {
    "rows_before": len(df),
    "rows_after": len(df_clean),
    "missing_by_column": {
        column: {
            "before": int(missing_before[column]),
            "after": int(missing_after[column])
        } for column in missing_before.index
    },
    "outliers_by_column": outlier_report,
    "validation": validation_report,
}

for column, metrics in outlier_report.items():
    logger.info(
        "Outliers em %s: %d encontrados", column, metrics["found"]
    )

try:
    with open("cleaning_report.json", "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info("Relatório de limpeza salvo com sucesso.")
except Exception:
    logger.exception("Erro ao salvar o relatório de limpeza.")
    raise

logger.info("Pipeline de limpeza de dados concluído com sucesso.")