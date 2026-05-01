import pandas as pd
from typing import Final

from src.common.logging import logger

# =========================================
# Importing helper functions and constants
# =========================================
from src.transformers.helper import (
    _clean_convert_currency_column_to_numeric,
    _convert_vest_date_for_postgres_posting
)

INDMONEY_DEPOSITS_INDMONEY_STATEMENT_DF_RENAMING: Final = {
        "trade_date": "deposit_date",
        "amount":"usd_deposit",
}

COLUMNS_TO_CONVERT_NUMERIC: Final = [
    "usd_deposit",
]

COLUMNS_TO_CONVERT_DATE: Final = [
    "deposit_date",
]

INDMONEY_DEPOSITS_INDMONEY_STATEMENT_DF_COLUMNS: Final = [
    "deposit_date",
    "usd_deposit",
]

# =========================
# Main transformer
# =========================
def transform_indmoney_statement_to_get_indmoney_deposits(
        indmoney_transactions_df: pd.DataFrame,
        month_year: str,
)-> pd.DataFrame:
    """
    Transforms raw indmoney statement to determine the amount deposited in indmoney platform for investment (in USD)

    Parameters
    ----------
    indmoney_transactions_df: pd.DataFrame
        Output dataframe from indmoney transactions statement parser
    month_year: str
        output from bank statement period parser

    Returns
    -------
    pd.DataFrame
        Final transformed dataframe ready with buy amount(in USD) for persistence or analytics
    """
    logger.info(
        "Starting indmoney statement transformation to get indmoney investment exchange rate",
    )

    if indmoney_transactions_df.empty:
        logger.warning(
            "No indmoney deposit transactions found for period %s",
            month_year
        )
        return pd.DataFrame()
    
    deposit_amount_mask = indmoney_transactions_df["entry_type"]=="Journal Entry(Cash)"
    
    indmoney_transactions_filtered_df = indmoney_transactions_df[deposit_amount_mask].copy()

    filtered_rows = len(indmoney_transactions_filtered_df)

    if filtered_rows>0:
        logger.info(
            "Filterd indmoney statement to get the indmoney deposit transactions | rows remainined=%d",
                filtered_rows,
        )

        indmoney_deposits_indmoney_statement_df = indmoney_transactions_filtered_df.rename(columns=INDMONEY_DEPOSITS_INDMONEY_STATEMENT_DF_RENAMING)
        
        indmoney_deposits_indmoney_statement_df[COLUMNS_TO_CONVERT_NUMERIC] = (
            indmoney_deposits_indmoney_statement_df[COLUMNS_TO_CONVERT_NUMERIC]
            .apply(_clean_convert_currency_column_to_numeric)
        )

        indmoney_deposits_indmoney_statement_df[COLUMNS_TO_CONVERT_DATE] = (
            indmoney_deposits_indmoney_statement_df[COLUMNS_TO_CONVERT_DATE]
            .apply(_convert_vest_date_for_postgres_posting)
        )
        
        return indmoney_deposits_indmoney_statement_df[INDMONEY_DEPOSITS_INDMONEY_STATEMENT_DF_COLUMNS]
    
    else:
        logger.warning(
            "No indmoney deposit transactions found for period %s",
            month_year
        )
        return pd.DataFrame()
