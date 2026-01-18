"""
Mutual Fund Summary Transformer

Transforms CAS mutual fund summary extract into a normalized,
analytics-ready dataframe suitable for storage and dashboards.

Author: Your Name
Created: YYYY-MM-DD

IMPORTANT:
- This module contains NO side effects (no writes)
- It is safe to re-run on historical data
"""

from src.common.logging import logger
from typing import Final

import numpy as np
import pandas as pd

# getting the engine to read data from postgres db
from src.common.db import get_read_engine


# =========================
# Constants (schema safety)
# These variables are intended to be a constant and must not be reassigned.
# =========================

EXCEL_ORIGIN: Final = pd.Timestamp("1899-12-30")
NAV_DATE_FORMAT: Final = "%d-%b-%Y"
OUTPUT_DATE_FORMAT: Final = "%d/%m/%Y"


# =========================
# Helper functions
# =========================

def _clean_currency_column(series: pd.Series) -> pd.Series:
    """
    Cleans INR currency strings and converts them to numeric values.

    Handles:
    - commas
    - ₹ symbol
    - whitespace
    - coercion to NaN on failure
    """
    return (
        series
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.strip()
        .pipe(pd.to_numeric, errors="coerce")
    )


def _round_investment_amount(value: float) -> float:
    """
    Business rounding rule:
    - >= 1,00,000 → nearest 1,000
    - < 1,00,000 → nearest 100
    """
    if pd.isna(value):
        return value

    if value >= 100_000:
        return int(round(value, -3))
    return int(round(value, -2))


def _derive_month_end_date(nav_date: pd.Series) -> pd.Series:
    """
    Converts NAV date to financial month-end date.

    Rule:
    - NAV day 1-10 → previous month end
    - NAV day 11+ → current month end
    """
    early_days = nav_date.dt.day.between(1, 10)

    return pd.to_datetime(
        np.where(
            early_days,
            nav_date - pd.offsets.MonthEnd(1),
            nav_date + pd.offsets.MonthEnd(0)
        )
    )


# =========================
# Main transformer
# =========================

def transform_mutual_fund_statement(
    mf_summary_extract: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transforms raw mutual fund CAS summary extract into final schema.

    Parameters
    ----------
    mf_summary_extract : pd.DataFrame
        Output dataframe from mutual_fund_statement_transactions parser

    Returns
    -------
    pd.DataFrame
        Final transformed dataframe ready for persistence or analytics
    """

    logger.info(
        "Starting mutual fund summary transformation | rows=%d",
        len(mf_summary_extract),
    )

    engine = get_read_engine()

    # ----------------------------------
    # Load reference / dimension tables
    # ----------------------------------
    logger.info("Loading mutual_fund_names mapping table")
    mf_name_mapping = pd.read_sql(
        "SELECT * FROM mutual_fund_names",
        engine,
    )

    logger.info("Loading fund_master_data dimension table")
    fund_master = pd.read_sql(
        "SELECT * FROM fund_master_data",
        engine,
    )

    # ----------------------------------
    # Normalize scheme names
    # ----------------------------------
    logger.info("getting the mutual fund names in the similar format as google spreadsheet")

    df = mf_summary_extract.merge(
        mf_name_mapping,
        left_on="Scheme Details",
        right_on="mf_name",
        how="left",
    )
 
    df = (
        df[df["mf_name_spreadsheet"].notna()]
        .drop(columns=["mf_name"])
    )

    # ----------------------------------
    # Select base financial columns
    # ----------------------------------
    df = df[
        [
            "mf_name_spreadsheet",
            "Invested Value\n(INR)",
            "Market Value\n(INR)",
            "NAV Date",
            "investment_value_flag",
        ]
    ]

    # ----------------------------------
    # Attach fund dimensions
    # ----------------------------------
    logger.info("getting other attributes of mutual fund using fund_master_data table")

    df = df.merge(
        fund_master,
        left_on="mf_name_spreadsheet",
        right_on="fund_name",
        how="left",
    ).drop(columns=["mf_name_spreadsheet"])

    # ----------------------------------
    # Date derivations
    # ----------------------------------
    logger.info("Deriving reporting date and google spreadsheet link")

    df["NAV Date"] = pd.to_datetime(
        df["NAV Date"],
        format=NAV_DATE_FORMAT,
        errors="coerce",
    )

    df["date"] = _derive_month_end_date(df["NAV Date"])

    # ----------------------------------
    # deriving the month_year format
    # ----------------------------------
    # Extract unique non-null reporting dates
    nav_dates = pd.to_datetime(df["date"], errors="coerce").dropna().unique()

    if len(nav_dates) > 1:
        logger.warning(
            "Multiple NAV Dates detected in MF summary extract: %s",
            nav_dates,
        )
        month_year = "multiple NAV dates"

    elif len(nav_dates) == 1:
        nav_date = pd.Timestamp(nav_dates[0])
        month_year = f"{nav_date.month}/{nav_date.year}"

    else:
        logger.warning("No NAV Date found in MF summary extract")
        month_year = "unknown"
    # ----------------------------------

    df["date"] = df["date"].dt.strftime(OUTPUT_DATE_FORMAT)
    df["link"] = (
        pd.to_datetime(df["date"], format=OUTPUT_DATE_FORMAT)
        - EXCEL_ORIGIN
    ).dt.days

    # ----------------------------------
    # Market value normalization
    # ----------------------------------
    logger.info("cleaning of market value format")

    df["Current Value"] = (
        _clean_currency_column(df["Market Value\n(INR)"])
        .round(0)
        .astype("Int64")
    )

    # ----------------------------------
    # Invested value normalization
    # ----------------------------------
    logger.info("cleaning of invested value format")

    invested_value = _clean_currency_column(
        df["Invested Value\n(INR)"]
    )

    df["Investment Amount"] = (
    pd.Series(
        np.where(
            df["investment_value_flag"] == "X",
            invested_value.round(0),
            invested_value.apply(_round_investment_amount),
        ),
        index=df.index
    )
    .astype("Int64")
    )

    # ----------------------------------
    # Final projection
    # ----------------------------------
    mf_summary_final = df[
        [
            "date",
            "investment_category",
            "investment_type",
            "fund_type",
            "fund_sub_type",
            "fund_name",
            "Investment Amount",
            "Current Value",
            "purpose",
            "link",
        ]
    ]

    logger.info(
        "Mutual fund summary transformation completed for period %s | rows=%d",
        month_year,len(mf_summary_final),
    )

    return mf_summary_final
