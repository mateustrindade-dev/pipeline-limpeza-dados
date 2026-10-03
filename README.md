# Pipeline de Limpeza de Dados

Pipeline em Python para validar e limpar dados de vendas de uma loja de varejo. As regras ficam em YAML, e os resultados são exportados para CSV e JSON.

## Funcionalidades

- Conversão de colunas para tipos string, numérico, inteiro, booleano e data.
- Tratamento de valores ausentes por valor padrão, cálculo a partir de colunas relacionadas ou mediana por categoria.
- Detecção de outliers pelo método do intervalo interquartil (IQR). Os valores originais são preservados e cada coluna analisada recebe uma coluna booleana `<coluna>_is_outlier` no CSV limpo.
- Validação de valores não negativos, valores permitidos, booleanos e datas.
- Registro da execução no log do pipeline.

## Estrutura

```text
.
├── cleaning.py                       # Regras de limpeza e validação
├── pipeline.py                       # Execução do pipeline
├── config/
│   └── config.yml                    # Regras por coluna
├── tests/
│   └── test_cleaning.py              # Testes automatizados
├── retail_store_sales.csv            # Dados de entrada
├── retail_store_sales_clean.csv      # CSV limpo (gerado)
├── cleaning_report.json              # Relatório (gerado)
└── logs/
    └── pipeline.log                 # Log da execução (gerado)
```

## Requisitos

- Python 3
- pandas
- PyYAML
- pytest (para executar os testes)

## Instalação

Na raiz do projeto, crie e ative um ambiente virtual. No Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install pandas PyYAML pytest
```

No macOS ou Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install pandas PyYAML pytest
```

## Executar

Execute a partir da raiz do projeto, pois os caminhos dos arquivos são relativos a ela. O pipeline cria a pasta `logs` automaticamente.

Windows PowerShell:

```powershell
py pipeline.py
```

macOS ou Linux:

```bash
python pipeline.py
```

A execução lê `retail_store_sales.csv` e as regras de `config/config.yml`. Quando concluída, grava `retail_store_sales_clean.csv`, `cleaning_report.json` e `logs/pipeline.log`. O CSV contém uma coluna booleana `<coluna>_is_outlier` para cada variável configurada para detecção; o JSON mantém os limites e as ocorrências detalhadas. Esses arquivos gerados são ignorados pelo Git.

## Configuração

Edite `config/config.yml` para ajustar:

- `columns`: tipo e estratégia de preenchimento de cada coluna;
- `outliers`: coluna, método, fator IQR e identificador usado nas ocorrências sinalizadas;
- `validations`: regras aplicadas a cada coluna, incluindo formatos e listas de valores permitidos.

As regras de outliers atuais usam `factor: 1.5` e apenas sinalizam ocorrências; os dados originais dessas ocorrências não são limitados aos valores de corte. Para datas futuras, a validação marca os valores inválidos como ausentes. A configuração mantém datas ausentes como nulas; ao exportar para CSV, o pandas representa esses valores como campos vazios.

## Testes

Com o ambiente virtual ativado, execute:

```bash
python -m pytest -q
```

No Windows, também é possível usar `py -m pytest -q`.

## Licença

Este projeto está sob a licença MIT. Consulte [LICENSE](LICENSE).

