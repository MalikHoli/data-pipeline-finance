import pandas as pd

from src.common.logging import logger

# =========================================
# Importing helper functions and constants
# =========================================
from src.transformers.helper import (
    _derive_month_end_date_for_gsheet_posting,
    GSHEET_OUTPUT_DATE_FORMAT,
    EXCEL_ORIGIN,
)

# =========================
# Main transformer
# =========================
def transform_kite_holding(
        kite_holding_extract: pd.DataFrame,
        month_year: str,
        fund_master: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transforms raw kite holdings extract into final schema.

    Parameters
    ----------
    kite_holding_extract : pd.DataFrame
        Output dataframe from kite_holding parser
    month_year : str
        The period for which this kite holding information belongs to
    fund_master : pd.DataFrame
        The dataframe fetched from the postgres having the all the attributes of fund necessary to store in google sheet

    Returns
    -------
    pd.DataFrame
        Final transformed dataframe ready for persistence or analytics
    """
    if not month_year:
        logger.error(
            "Failed to get the period information in the transformer"
        )
        raise ValueError("month_year must be provided in MM/YYYY format")
    # ----------------------------------
    # Date derivations
    # ----------------------------------
    logger.info("Deriving reporting date and google spreadsheet link")

    kite_holding_date = _derive_month_end_date_for_gsheet_posting(month_year)

    kite_holding_extract["date"] = pd.to_datetime(
        kite_holding_date,
        format=GSHEET_OUTPUT_DATE_FORMAT,
        errors="coerce",
    )

    kite_holding_extract["link"] = (
        pd.to_datetime(kite_holding_extract["date"], format=GSHEET_OUTPUT_DATE_FORMAT)
        - EXCEL_ORIGIN
    ).dt.days

    # ----------------------------------
    # Data safety & validation
    # ----------------------------------
    REQUIRED_COLUMNS = {
        "Quantity Available",
        "Previous Closing Price",
        "Average Price",
        "Symbol",
    }

    missing = REQUIRED_COLUMNS - set(kite_holding_extract.columns)

    if missing:
        logger.error("Missing required columns: %s", missing)
        raise ValueError(f"Missing required columns: {missing}")

    # ----------------------------------
    # "Current Value" column
    # ----------------------------------
    prev_close = pd.to_numeric(
    kite_holding_extract["Previous Closing Price"],
    errors="coerce"
    )

    if prev_close.isna().any():
        logger.warning(
            "Found non-numeric 'Previous Closing Price' values; coercing to NaN and filling with 0"
        )

    # Convert NaN to 0 AFTER warning
    prev_close = prev_close.fillna(0)

    kite_holding_extract["Current Value"] = (
    kite_holding_extract["Quantity Available"]*prev_close
    .round(0)
    .astype("Int64")   # nullable integer
    )

    # ----------------------------------
    # "Investment Amount" column
    # ----------------------------------
    avg_price = pd.to_numeric(
    kite_holding_extract["Average Price"],
    errors="coerce"
    )

    if avg_price.isna().any():
        logger.warning(
            "Found non-numeric 'Average Price' values; coercing to NaN and filling with 0"
        )

    # Convert NaN to 0 AFTER warning
    avg_price = avg_price.fillna(0)

    kite_holding_extract["Investment Amount"] = (
    kite_holding_extract["Quantity Available"]*avg_price
    .round(0)
    .astype("Int64")   # nullable integer
    )

    # to remove practically non-possible records
    kite_holding_extract = kite_holding_extract[kite_holding_extract["Current Value"] > 0]

    # ----------------------------------
    # Attach fund dimensions
    # ----------------------------------
    logger.info("getting other attributes of stocks using fund_master_data table")
    kite_holdings_refined_df = pd.merge(
                                            kite_holding_extract, 
                                            fund_master, 
                                            left_on='Symbol',
                                            right_on='fund_name', 
                                            how='left',
                                        )

    unmatched = kite_holdings_refined_df["investment_category"].isna().sum()
    if unmatched:
        logger.warning("Unmatched symbols in fund_master_data: %d", unmatched)

    # ----------------------------------
    # Rearrange required columns
    # ----------------------------------
    kite_holdings_final = kite_holdings_refined_df[
        [
            "date",
            "investment_category",
            "investment_type",
            "fund_type",
            "fund_sub_type",
            "fund_name_spreadsheet",
            "Investment Amount",
            "Current Value",
            "purpose",
            "link",
            ]
        ]

    logger.info(
        "kite holding transformation completed for period %s | rows=%d",
        month_year,len(kite_holdings_final),
    )

    return kite_holdings_final