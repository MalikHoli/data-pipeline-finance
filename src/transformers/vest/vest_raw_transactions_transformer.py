import pandas as pd

from src.common.logging import logger

# =========================================
# Importing helper functions and constants
# =========================================
from src.transformers.helper import (
    _clean_convert_currency_column_to_numeric,
    _convert_vest_date_for_postgres_posting,
    VEST_RAW_TRANSACTIONS_REQUIRED_COLUMNS_LIST,
    VEST_STATEMENT_TRANSACTIONS_CONVERT_TO_NUMERIC,
    VEST_STATEMENT_TRANSACTIONS_CONVERT_TO_POSTGRES_DATE,
)

# =========================
# Main transformer
# =========================
def transform_vest_raw_transactions(
        vest_raw_transactions_parsed_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transform raw vest transactions into schema that is compatible to upload into postgres 
    
    Parameters
    ----------
    vest_transactions_extract_df: pd.DataFrame,
        Output dataframe from vest_transactions_parser
    month_year : str
        The period for which this vest statement generated
    
    Returns
    -------
    pd.DataFrame
        Final vest raw transactions transformed dataframe ready for persistance or analytics
    """
    if vest_raw_transactions_parsed_df.empty:
        logger.error(
            "No transactions parsed from vest statement"
        )
        raise ValueError("vest statement raw transaction parsed df can't be empty")
    
    logger.info(
        "Starting vest raw transaction transformer which cleans and format columns as per postgres schema"
    )
    # Selecting required columns to write
    vest_raw_transaction_df = vest_raw_transactions_parsed_df[VEST_RAW_TRANSACTIONS_REQUIRED_COLUMNS_LIST].copy()

    vest_raw_transaction_df[VEST_STATEMENT_TRANSACTIONS_CONVERT_TO_NUMERIC] = (
        vest_raw_transaction_df[VEST_STATEMENT_TRANSACTIONS_CONVERT_TO_NUMERIC]
        .apply(_clean_convert_currency_column_to_numeric)
        .fillna(0)
    )

    vest_raw_transaction_df[VEST_STATEMENT_TRANSACTIONS_CONVERT_TO_POSTGRES_DATE] = (
        vest_raw_transaction_df[VEST_STATEMENT_TRANSACTIONS_CONVERT_TO_POSTGRES_DATE]
        .apply(_convert_vest_date_for_postgres_posting)
    )
 
    return  vest_raw_transaction_df