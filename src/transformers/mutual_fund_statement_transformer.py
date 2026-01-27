import numpy as np
import pandas as pd

from src.common.logging import logger

# =========================================
# Importing helper functions and constants
# =========================================
from src.transformers.helper import (
    EXCEL_ORIGIN,
    NAV_DATE_FORMAT,
    GSHEET_OUTPUT_DATE_FORMAT,
    _clean_convert_currency_column_to_numeric,
    _round_mutual_fund_investment_amount,
    _derive_month_end_date_from_NAV_for_gsheet_posting,
)

# =========================
# Main transformer
# =========================
def transform_mutual_fund_statement(
    mf_summary_extract: pd.DataFrame,
    mf_name_mapping: pd.DataFrame,
    fund_master: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transforms raw mutual fund CAS summary extract into final schema.

    Parameters
    ----------
    mf_summary_extract : pd.DataFrame
        Output dataframe from mutual_fund_statement_transactions parser
    mf_name_mapping : pd.DataFrame
        The dataframe fetched from the postgres to map statement fund names to one suitable for google sheet write
    fund_master : pd.DataFrame
        The dataframe fetched from the postgres having the all the attributes of fund necessary to store in google sheet

    Returns
    -------
    pd.DataFrame
        Final transformed dataframe ready for persistence or analytics
    """
    mf_summary_extract_len = len(mf_summary_extract)

    logger.info(
        "Starting mutual fund summary transformation | rows=%d",
        mf_summary_extract_len,
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

    # logging warning if any rows are getting removed due to merge
    removed_rows = df[df["mf_name_spreadsheet"].isna()]["Scheme Details"].unique()

    if len(removed_rows) > 0:
        logger.warning(
            "MF summary rows removed due to missing mapping. Schemes: %s",
            ", ".join(removed_rows)
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
    )

    unmatched_rows = df[df["fund_type"].isna()]["mf_name_spreadsheet"]

    df.drop(columns=["mf_name_spreadsheet"])

    if len(unmatched_rows) > 0:
        logger.warning(
            "Rows without fund attributes detected. Schemes: %s",
            ", ".join(unmatched_rows)
        )

    # ----------------------------------
    # Date derivations
    # ----------------------------------
    logger.info("Deriving reporting date and google spreadsheet link")

    df["NAV Date"] = pd.to_datetime(
        df["NAV Date"],
        format=NAV_DATE_FORMAT,
        errors="coerce",
    )

    df["date"] = _derive_month_end_date_from_NAV_for_gsheet_posting(df["NAV Date"])

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

    df["date"] = df["date"].dt.strftime(GSHEET_OUTPUT_DATE_FORMAT)
    df["link"] = (
        pd.to_datetime(df["date"], format=GSHEET_OUTPUT_DATE_FORMAT)
        - EXCEL_ORIGIN
    ).dt.days

    # ----------------------------------
    # Market value normalization
    # ----------------------------------
    logger.info("cleaning of market value format")

    df["Current Value"] = (
        _clean_convert_currency_column_to_numeric(df["Market Value\n(INR)"])
        .round(0)
        .astype("Int64")
    )

    # ----------------------------------
    # Invested value normalization
    # ----------------------------------
    logger.info("cleaning of invested value format")

    invested_value = _clean_convert_currency_column_to_numeric(
        df["Invested Value\n(INR)"]
    )

    df["Investment Amount"] = (
    pd.Series(
        np.where(
            df["investment_value_flag"] == "X",
            invested_value.round(0),
            invested_value.apply(_round_mutual_fund_investment_amount),
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
