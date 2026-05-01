import pandas as pd
from typing import Final

from src.common.logging import logger

# =========================================
# Importing helper functions and constants
# =========================================
from src.transformers.helper import (
    INDMONEY_DEPOSIT_INDICATOR_TRANSACTION_REMARKS_REGEX,
    _clean_convert_currency_column_to_numeric,
    _convert_bank_statement_for_postgres_posting
)

INDMONEY_DEPOSITS_BANK_STATEMENT_DF_RENAMING: Final = {
        "Transaction Date": "deposit_date",
        "Withdrawal Amount(INR)":"inr_deposit",
        }

COLUMNS_TO_CONVERT_NUMERIC: Final = [
    "inr_deposit",
]

COLUMNS_TO_CONVERT_DATE: Final = [
    "deposit_date",
]

COLUMNS_TO_CHECK_POSITIVE_TRANSACTION: Final = "inr_deposit"

INDMONEY_DEPOSITS_BANK_STATEMENT_DF_COLUMNS: Final = [
    "deposit_date",
    "inr_deposit",
]

# =========================
# Main transformer
# =========================
def transform_bank_statement_to_get_indmoney_deposits(
        bank_statement_df: pd.DataFrame,
        month_year: str,
)-> pd.DataFrame:
    """
    Transforms raw bank statement to determine the amount deposited in indmoney platform for investment

    Parameters
    ----------
    bank_statement_df: pd.DataFrame
        Output dataframe from bank statement parser
    month_year: str
        output from bank statement period parser

    Returns
    -------
    pd.DataFrame
        Final transformed dataframe ready with buy amount for persistence or analytics
    """
    bank_statement_extract_len = len(bank_statement_df)

    logger.info(
        "Starting bank statement transformation to get investment exchange rate | rows=%d",
            bank_statement_extract_len,
    )

    # indmoney deposits are identified by a strict transaction remarks
    # This acts as a business rule, not a data-cleaning heuristic
    remarks_mask = bank_statement_df["Transaction Remarks"].astype(str).str.contains(
        INDMONEY_DEPOSIT_INDICATOR_TRANSACTION_REMARKS_REGEX,
        case=False,  # case-insensitive
        na=False, # treat NaN as non-matching
    )

    bank_df = bank_statement_df.rename(columns=INDMONEY_DEPOSITS_BANK_STATEMENT_DF_RENAMING)

    bank_df[COLUMNS_TO_CONVERT_NUMERIC] = (
        bank_df[COLUMNS_TO_CONVERT_NUMERIC]
        .apply(_clean_convert_currency_column_to_numeric)
    )

    bank_df[COLUMNS_TO_CONVERT_DATE] = (
        bank_df[COLUMNS_TO_CONVERT_DATE]
        .apply(_convert_bank_statement_for_postgres_posting)
    )

    amount_mask = bank_df[COLUMNS_TO_CHECK_POSITIVE_TRANSACTION] > 1

    #----------------------------------------------------
    # Condition 1:
    # Transaction Remarks contains either of the INDMoney identifiers
    # Condition 2:
    # Withdrawal amount must be greater than 1 INR
    #----------------------------------------------------
    indmoney_deposits_bank_statement_df = bank_df[remarks_mask & amount_mask].copy()

    filtered_rows = len(indmoney_deposits_bank_statement_df)

    if filtered_rows>0:
        logger.info(
            "Filterd bank statement to get the indmoney deposit transactions | rows remainined=%d",
                filtered_rows,
        )

        return indmoney_deposits_bank_statement_df[INDMONEY_DEPOSITS_BANK_STATEMENT_DF_COLUMNS]
    
    else:
        logger.warning(
            "No indmoney deposit transactions found for period %s",
            month_year
        )
        return pd.DataFrame()