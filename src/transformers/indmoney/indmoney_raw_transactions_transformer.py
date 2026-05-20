import pandas as pd
from src.common.logging import logger
from src.transformers.helper import (
    _clean_convert_currency_column_to_numeric,
    _convert_vest_date_for_postgres_posting,
    INDMONEY_RAW_TRANSACTIONS_REQUIRED_COLUMNS_LIST,
    INDMONEY_STATEMENT_TRANSACTIONS_RENAME_COLUMNS_AS_PER_POSTGRES_SCHEMA_DICT,
    INDMONEY_STATEMENT_TRANSACTIONS_CONVERT_TO_NUMERIC,
    INDMONEY_STATEMENT_TRANSACTIONS_CONVERT_TO_POSTGRES_DATE,
)

def transform_indmoney_raw_transactions(
        indmoney_raw_transactions_parsed_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transform raw indmoney transactions into schema that is compatible to upload into postgres

    Parameters
    ----------
    indmoney_raw_transactions_parsed_df: pd.DataFrame
        Output dataframe from indmoney_statement_transactions parser

    Returns
    -------
    pd.DataFrame
        Final indmoney raw transactions transformed dataframe ready for persistence or analytics
    """
    if indmoney_raw_transactions_parsed_df.empty:
        logger.warning("No transactions found from indmoney statement")
        return pd.DataFrame()

    logger.info("Starting indmoney raw transaction transformer which cleans and format columns as per postgres schema")

    indmoney_raw_transaction_df = indmoney_raw_transactions_parsed_df[INDMONEY_RAW_TRANSACTIONS_REQUIRED_COLUMNS_LIST].copy()

    indmoney_raw_transaction_df = indmoney_raw_transaction_df.rename(
        columns=INDMONEY_STATEMENT_TRANSACTIONS_RENAME_COLUMNS_AS_PER_POSTGRES_SCHEMA_DICT
    )

    indmoney_raw_transaction_df[INDMONEY_STATEMENT_TRANSACTIONS_CONVERT_TO_NUMERIC] = (
        indmoney_raw_transaction_df[INDMONEY_STATEMENT_TRANSACTIONS_CONVERT_TO_NUMERIC]
        .apply(_clean_convert_currency_column_to_numeric)
        .fillna(0)
    )

    indmoney_raw_transaction_df[INDMONEY_STATEMENT_TRANSACTIONS_CONVERT_TO_POSTGRES_DATE] = (
        indmoney_raw_transaction_df[INDMONEY_STATEMENT_TRANSACTIONS_CONVERT_TO_POSTGRES_DATE]
        .apply(_convert_vest_date_for_postgres_posting)
    )

    return indmoney_raw_transaction_df