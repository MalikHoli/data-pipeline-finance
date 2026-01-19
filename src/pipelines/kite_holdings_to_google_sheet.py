from pathlib import Path

import pandas as pd

from src.parsers.pdf.mutual_fund_statement_transactions import extract_mutual_fund_statement
from src.transformers.mutual_fund_statement_transformer import transform_mutual_fund_statement
from src.sinks.google_sheets.client import get_sheets_service
from src.sinks.google_sheets.writer import append_rows
from src.common.logging import logger

from src.common.config import (
    GSPREAD_SERVICE_ACCOUNT_FILE,
    INVESTMENT_SHEET_ID,
)

SERVICE_ACCOUNT_FILE = GSPREAD_SERVICE_ACCOUNT_FILE
SPREADSHEET_ID = INVESTMENT_SHEET_ID
SHEET_NAME = "Investment"


def dataframe_to_rows(
    df: pd.DataFrame,
) -> list[list]:
    """
    Converts a pandas DataFrame into Google Sheets compatible rows.

    Parameters
    ----------
    df : pd.DataFrame
        Final transformed dataframe
    include_header : bool
        Whether to include column headers as the first row

    Returns
    -------
    list[list]
        Rows ready for Sheets API
    """
    if df.empty:
        return []

    rows = []
    # if include_header:
    #     rows.append(df.columns.tolist())

    rows.extend(
        df.fillna("").astype(str).values.tolist()
    )
    return rows


def run(pdf_path: Path) -> None:
    """
    Runs the MF summary → Google Sheets pipeline for a single CAS PDF.

    Parameters
    ----------
    pdf_path : Path
        Path to cas_summary_report.pdf
    """

    logger.info("Starting MF statement → Google Sheets pipeline | pdf=%s", pdf_path)

    # 1. Parse
    mf_statement_extract = extract_mutual_fund_statement(pdf_path)

    # 2. Transform
    mf_statement_transformed_final = transform_mutual_fund_statement(mf_statement_extract)

    if mf_statement_transformed_final.empty:
        logger.warning("No data produced by transformer; skipping Sheets write")
        return

    # 3. Prepare rows
    rows = dataframe_to_rows(
        mf_statement_transformed_final,
    )

    # 4. Initialize Sheets service
    sheets_service = get_sheets_service(SERVICE_ACCOUNT_FILE)

    # 5. Write to Google Sheets
    append_rows(
        sheets_service=sheets_service,
        spreadsheet_id=SPREADSHEET_ID,
        sheet_name=SHEET_NAME,
        rows=rows,
    )

    logger.info(
        "MF statement successfully written to Google Sheets | rows=%d",
        len(rows),
    )

    logger.info("MF statement pipeline completed successfully")
