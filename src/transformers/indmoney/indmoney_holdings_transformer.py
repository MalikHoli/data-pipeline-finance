import pandas as pd

from src.common.logging import logger
from src.transformers.helper import _clean_convert_currency_column_to_numeric, _derive_month_end_date_for_postgres_posting

RENAME_COLUMNS = {
    "Symbol": "symbol",
    "Quantity": "quantity",
    "Cost Price": "unit_cost",
    "TD Cost Basis": "total_cost",
    "Market Price": "market_price",
    "Market Value": "market_value",
    "Unrealized": "gain",
}

NUMERIC_COLUMNS = ["quantity", "unit_cost", "total_cost", "market_price", "market_value", "gain"]


def transform_indmoney_holdings(summary_df: pd.DataFrame, month_year: str) -> pd.DataFrame:
    if summary_df.empty:
        logger.error("No holdings parsed from indmoney statement")
        raise ValueError("holdings cannot be empty for indmoney statement")

    insert_df = summary_df[list(RENAME_COLUMNS.keys())].copy()
    insert_df.rename(columns=RENAME_COLUMNS, inplace=True)

    insert_df[NUMERIC_COLUMNS] = insert_df[NUMERIC_COLUMNS].apply(_clean_convert_currency_column_to_numeric)

    insert_df["date"] = _derive_month_end_date_for_postgres_posting(month_year)

    logger.info("Transformed indmoney holdings | rows=%d", len(insert_df))
    return insert_df
