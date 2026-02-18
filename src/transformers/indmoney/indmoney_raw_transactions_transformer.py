import pandas as pd

from src.common.logging import logger
from src.transformers.helper import _clean_convert_currency_column_to_numeric

RENAME_COLUMNS = {
    "Trade Date": "trade_date",
    "Entry Type": "entry_type",
    "Side": "activity",
    "Symbol": "symbol",
    "Description": "description",
    "Quantity": "quantity",
    "Price": "price",
    "Amount": "amount",
    "Commission": "commission",
}

NUMERIC_COLUMNS = ["quantity", "price", "amount", "commission"]


def transform_indmoney_raw_transactions(indmoney_transactions_df: pd.DataFrame) -> pd.DataFrame:
    if indmoney_transactions_df.empty:
        logger.warning("No indmoney transactions parsed")
        return pd.DataFrame()

    transformed_df = indmoney_transactions_df[list(RENAME_COLUMNS.keys())].copy()
    transformed_df.rename(columns=RENAME_COLUMNS, inplace=True)

    transformed_df["trade_date"] = pd.to_datetime(
        transformed_df["trade_date"], format="%m/%d/%Y", errors="coerce"
    ).dt.normalize()

    transformed_df[NUMERIC_COLUMNS] = transformed_df[NUMERIC_COLUMNS].apply(_clean_convert_currency_column_to_numeric)

    transformed_df["activity"] = transformed_df["activity"].astype(str).str.lower().str.strip()
    transformed_df["entry_type"] = transformed_df["entry_type"].astype(str).str.strip()

    if (
        len(transformed_df) == 1
        and pd.isna(transformed_df.loc[transformed_df.index[0], "trade_date"])
        and str(indmoney_transactions_df.loc[indmoney_transactions_df.index[0], "Trade Date"]).strip() == "No record found."
    ):
        logger.warning("No trade records found in indmoney statement")
        return pd.DataFrame()

    logger.info("Transformed indmoney raw transactions | rows=%d", len(transformed_df))
    return transformed_df
