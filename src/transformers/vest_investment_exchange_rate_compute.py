import pandas as pd

from src.common.logging import logger

# =========================================
# Importing helper functions and constants
# =========================================
from src.transformers.helper import (
    VEST_DEPOSIT_INDICATOR_TRANSACTION_REMARKS_START,
    _extract_deposit_value_in_USD,
    _clean_convert_currency_column_to_numeric,
)

# =========================
# Main transformer
# =========================
def transform_vest_statement_to_get_investment_exchange_rate(
        bank_statement_df: pd.DataFrame,
        month_year: str,
):
    """
    Transforms raw bank statement to determine the amount deposited in Vest platform for investment
    We have acess to both USD and INR amount based on which exchange rate is calculated
    this exchange rate is useful to determine the US stocks investment/buy amount in INR

    Parameters
    ----------
    bank_statement_df: pd.DataFrame
        Output dataframe from bank statement parser
    month_year: str
        output from bank statement period parser

    Returns
    -------
    pd.DataFrame
        Final transformed dataframe ready with buy exchange rate for persistence or analytics
    """
    bank_statement_extract_len = len(bank_statement_df)

    logger.info(
        "Starting bank statement transformation to get investment exchange rate | rows=%d",
            bank_statement_extract_len,
    )

    # Vest deposits are identified by a strict transaction remark prefix
    # This acts as a business rule, not a data-cleaning heuristic
    df = bank_statement_df[
        bank_statement_df["Transaction Remarks"].astype(str).str.startswith(VEST_DEPOSIT_INDICATOR_TRANSACTION_REMARKS_START)
    ].copy()

    filtered_rows = len(df)

    if filtered_rows>0:
        logger.info(
            "Filterd bank statement to get the vest deposit transactions | rows remainined=%d",
                filtered_rows,
        )
    else:
        logger.warning(
            "No vest deposit transactions found for period %s",
            month_year
        )

    # ----------------------------------
    # Calculate exchage rate
    # ----------------------------------
    logger.info("started calculating exchange rate")
    # fetching USD amount deposited in Vest
    df["USD Value"] = _extract_deposit_value_in_USD(df["Transaction Remarks"])

    usd_missing = df["USD Value"].isna().sum()

    if usd_missing > 0:
        logger.warning(
            "USD extraction failed for %d vest deposit rows | check transaction remarks format",
            usd_missing,
        )

    df = df.copy()

    df["Withdrawal Amount(INR)_num"] = _clean_convert_currency_column_to_numeric(df["Withdrawal Amount(INR)"])

    df["exchange rate"] = (
        df["Withdrawal Amount(INR)_num"] / df["USD Value"]
    ).round(2)

    invalid_rates = df["exchange rate"].isna().sum()

    if invalid_rates > 0:
        logger.warning(
            "Exchange rate could not be computed for %d rows (division by zero or missing values)",
            invalid_rates,
    )
    
    # These are the only columns we want to insert into Postgres
    insert_df = df[
        [
            "Transaction Date", 
            "exchange rate", 
            "USD Value", 
            "Withdrawal Amount(INR)",
        ]
    ].copy()

    logger.info("renaming columns to match postgres schema names")

    insert_df.rename(
    columns={
        "Transaction Date": "deposit_date",
        "exchange rate": "exchange_rate_1_usd_to_inr",
        "USD Value":"usd_deposit",
        "Withdrawal Amount(INR)":"inr_deposit",
        },
        inplace=True,
    )

    # ----------------------------------------
    # Date and numeric column formatting
    # ---------------------------------------
    logger.info("formatting columns to suit postgres schema types")

    insert_df["deposit_date"] = pd.to_datetime(
        insert_df["deposit_date"],
        dayfirst=True,
    ).dt.date

    insert_df["exchange_rate_1_usd_to_inr"] = _clean_convert_currency_column_to_numeric(
        insert_df["exchange_rate_1_usd_to_inr"]
    )
    insert_df["usd_deposit"] = _clean_convert_currency_column_to_numeric(
        insert_df["usd_deposit"]
    )
    insert_df["inr_deposit"] = _clean_convert_currency_column_to_numeric(
        insert_df["inr_deposit"]
    )
