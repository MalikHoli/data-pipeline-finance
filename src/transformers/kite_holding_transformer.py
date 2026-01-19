import pandas as pd
from calendar import monthrange

from src.common.logging import logger
from typing import Final

from src.parsers.excel.kite_holding_period import extract_kite_holding_period

# getting the engine to read data from postgres db
from src.common.db import get_read_engine

# =========================
# Constants (schema safety)
# These variables are intended to be a constant and must not be reassigned.
# =========================
EXCEL_ORIGIN: Final = pd.Timestamp("1899-12-30")
OUTPUT_DATE_FORMAT: Final = "%d/%m/%Y"

# =========================
# Helper functions
# =========================
def _derive_month_end_date(
        month_year: str,
        ) -> str:
    month_str, year_str = month_year.split("/")
    month = int(month_str)
    year = int(year_str)
    
    # Get actual last day of the month
    last_day = monthrange(year, month)[1]

    # Apply rule:
    # - February → actual last day (28/29)
    # - Other months → always 30
    final_day = last_day if month == 2 else 30

    final_date = pd.Timestamp(year, month, final_day).strftime(OUTPUT_DATE_FORMAT)

    return final_date

# =========================
# Main transformer
# =========================
def transform_kite_holding(
        kite_holding_extract: pd.DataFrame,
        month_year: str
) -> pd.DataFrame:
    """
    Docstring for transform_kite_holding
    
    :param kite_holding_extract: Description
    :type kite_holding_extract: pd.DataFrame
    :return: Description
    :rtype: DataFrame
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

    kite_holding_date = _derive_month_end_date(month_year)

    kite_holding_extract["date"] = pd.to_datetime(
        kite_holding_date,
        format=OUTPUT_DATE_FORMAT,
        errors="coerce",
    )

    kite_holding_extract["link"] = (
        pd.to_datetime(kite_holding_extract["date"], format=OUTPUT_DATE_FORMAT)
        - EXCEL_ORIGIN
    ).dt.days

    # ----------------------------------
    # "Current Value" column
    # ----------------------------------
    kite_holding_extract["Current Value"] = (
    kite_holding_extract["Quantity Available"]*pd.to_numeric(kite_holding_extract["Previous Closing Price"])
    .round(0)
    .astype("Int64")   # nullable integer
    )

    # ----------------------------------
    # "Investment Amount" column
    # ----------------------------------
    kite_holding_extract["Investment Amount"] = (
    kite_holding_extract["Quantity Available"]*pd.to_numeric(kite_holding_extract["Average Price"])
    .round(0)
    .astype("Int64")   # nullable integer
    )

    # to remove practically non-possible records
    kite_holding_extract = kite_holding_extract[kite_holding_extract["Current Value"] > 0]

    engine = get_read_engine()

    # ----------------------------------
    # Load reference / dimension tables
    # ----------------------------------
    logger.info("Loading fund_master_data dimension table")
    fund_master = pd.read_sql(
        "SELECT * FROM fund_master_data",
        engine,
    )

    # ----------------------------------
    # Attach fund dimensions
    # ----------------------------------
    logger.info("getting other attributes of stocks using fund_master_data table")
    kite_holdings_refined_df = pd.merge(kite_holding_extract, fund_master, left_on='Symbol',right_on='fund_name', how='left')

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