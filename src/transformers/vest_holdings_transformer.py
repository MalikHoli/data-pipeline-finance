import pandas as pd

from src.common.logging import logger

# =========================================
# Importing helper functions and constants
# =========================================
from src.transformers.helper import (
    _clean_convert_currency_column_to_numeric,
    _derive_month_end_date_for_postgres_posting,
    _fetch_usd_to_inr_exch_rate_from_Frankfurter_API,
)

# =========================
# Initializing variables
# =========================
columns_to_clean_convert = []

# =========================
# Main transformer
# =========================
def transform_vest_holdings(
        vest_holdings_extract_df: pd.DataFrame,
        month_year: str,
) -> pd.DataFrame:
    """
    Transform raw vest holdings into schema that is helpful to determine invested and current value in INR    
    
    Parameters
    ----------
    vest_holdings_extract_df: pd.DataFrame
        Output dataframe from vest_holdings_parser
    month_year : str
        The period for which this vest statement generated
    
    Returns
    -------
    pd.DataFrame
        Final transformed dataframe holding the vest statement period snapshot (invested & current computable in INR)
    """
    if not month_year:
        logger.error(
            "Failed to get the period information in the transformer"
        )
        raise ValueError("month_year must be provided in MM/YYYY format")
    
    logger.info("transforming vest holdings for %s",month_year)
    # ----------------------------------
    # considering interested columns
    # ----------------------------------
    vest_holdings_transformed_df = (
        vest_holdings_extract_df
        .drop(columns=["account_type","description"])
    )

    # -----------------------------------------
    # cleaning and numerical format conversion
    # -----------------------------------------
    columns_to_clean_convert = [
        col for col in vest_holdings_transformed_df.columns if col!="symbol"
    ]

    vest_holdings_transformed_df[columns_to_clean_convert] = (
        vest_holdings_transformed_df[columns_to_clean_convert]
        .apply(_clean_convert_currency_column_to_numeric)
    )

    # -----------------------------------------
    # inserting month end date column
    # -----------------------------------------
    vest_holding_date = _derive_month_end_date_for_postgres_posting(month_year)

    logger.info("inserting %s as date column for vest holdings period %s",vest_holding_date,month_year)

    vest_holdings_transformed_df["date"] = vest_holding_date

    # ---------------------------------------------------------------------
    # fetching usd to inr exchange rate from API and inserting as column
    # ---------------------------------------------------------------------
    # build the helper function for _fetch_usd_to_inr_exch_rate_from_Frankfurter_API
    usd_to_inr_exch_rate = _fetch_usd_to_inr_exch_rate_from_Frankfurter_API(vest_holding_date)

    vest_holdings_transformed_df["exch_rate"] = _clean_convert_currency_column_to_numeric(usd_to_inr_exch_rate)

    return vest_holdings_transformed_df