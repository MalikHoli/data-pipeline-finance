import pandas as pd
from typing import Final

from src.common.logging import logger

# =========================================
# Importing helper functions and constants
# =========================================
from src.transformers.helper import (
    _clean_convert_currency_column_to_numeric,
    _derive_month_end_date_for_postgres_posting,
    _fetch_usd_to_inr_exch_rate_from_Frankfurter_API,
)

COLUMNS_TO_DROP_FROM_PARSER: Final = [
    "Description",
]

DATE_FORMAT_FOR_FRANKFURTER_API: Final = "%Y-%m-%d"

COLUMNS_TO_RENAME: Final = {
    "Symbol":"symbol",
    "Quantity":"quantity",
    "Market Price":"market_price",
    "Market Value":"market_value",
    "Cost Price":"unit_cost",
    "Unrealized":"gain",
    "TD Cost Basis":"total_cost",
}

SYMBOL_ROW_TO_DROP: Final = "*Cash"

# =========================
# Main transformer
# =========================
def transform_indmoney_holdings(
        indmoney_holdings_extract_df: pd.DataFrame,
        month_year: str,
) -> pd.DataFrame:
    """
    Transform raw indmoney holdings into schema that is helpful to determine invested and current value in INR    
    
    Parameters
    ----------
    indmoney_holdings_extract_df: pd.DataFrame
        Output dataframe from indmoney_holdings_parser
    month_year : str
        The period for which this indmoney statement generated
    
    Returns
    -------
    pd.DataFrame
        Final transformed dataframe holding the indmoney statement period snapshot (invested in USD & current computable in INR)
    """
    if not month_year:
        logger.error(
            "Failed to get the period information in the transformer"
        )
        raise ValueError("month_year must be provided in MM/YYYY format")
    
    logger.info("transforming indmoney holdings for %s",month_year)
    # ----------------------------------
    # reanming columns and considering interested columns and rows
    # ----------------------------------
    indmoney_holdings_transformed_df = (
        indmoney_holdings_extract_df
        .drop(columns=COLUMNS_TO_DROP_FROM_PARSER)
        .rename(columns=COLUMNS_TO_RENAME)
    )

    mask = indmoney_holdings_transformed_df["symbol"] != SYMBOL_ROW_TO_DROP
    indmoney_holdings_transformed_df = indmoney_holdings_transformed_df[mask]

    # -----------------------------------------
    # cleaning and numerical format conversion
    # -----------------------------------------
    columns_to_clean_convert = [
        col for col in indmoney_holdings_transformed_df.columns if col!="symbol"
    ]

    indmoney_holdings_transformed_df[columns_to_clean_convert] = (
        indmoney_holdings_transformed_df[columns_to_clean_convert]
        .apply(_clean_convert_currency_column_to_numeric)
    )

    # -----------------------------------------
    # inserting month end date column
    # -----------------------------------------
    indmoney_holding_date = _derive_month_end_date_for_postgres_posting(month_year)

    logger.info("inserting %s as date column for vest holdings period %s",indmoney_holding_date,month_year)

    indmoney_holdings_transformed_df["date"] = indmoney_holding_date

    # ---------------------------------------------------------------------
    # fetching usd to inr exchange rate from API and inserting as column
    # ---------------------------------------------------------------------
    usd_to_inr_exch_rate = _fetch_usd_to_inr_exch_rate_from_Frankfurter_API(indmoney_holding_date.strftime(DATE_FORMAT_FOR_FRANKFURTER_API))

    indmoney_holdings_transformed_df["exch_rate"] = usd_to_inr_exch_rate

    return indmoney_holdings_transformed_df