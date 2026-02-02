from pathlib import Path
import pandas as pd

from src.parsers.excel.kite_holding import extract_kite_holding
from src.transformers.kite_holding_transformer import transform_kite_holding
from src.sinks.google_sheets.client import get_sheets_service
from src.sinks.google_sheets.writer import append_rows
from src.common.logging import logger

from src.common.db import get_read_engine
from src.common.config import (
    GSPREAD_SERVICE_ACCOUNT_FILE,
    INVESTMENT_SHEET_ID,
)

SERVICE_ACCOUNT_FILE = GSPREAD_SERVICE_ACCOUNT_FILE
SPREADSHEET_ID = INVESTMENT_SHEET_ID
SHEET_NAME = "Investment"

# =========================
# Helper functions
# =========================
def dataframe_to_rows(df: pd.DataFrame) -> list[list]:
    """
    Converts a pandas DataFrame into Google Sheets compatible rows.

    Important:
    - All values are converted to strings
    - NaNs are replaced with empty strings
    """
    if df.empty:
        return []

    return df.fillna("").astype(str).values.tolist()


# =========================
# Main pipeline
# =========================
def run(
        excel_path: Path, 
        dry_run: bool = False,
) -> None:
    """
    Runs the kite holding xlsx → Google Sheets pipeline.

    Parameters
    ----------
    excel_path : Path
        Path to kite holding Excel file
    dry_run : bool
        If True, executes full pipeline except Google Sheets write
    """

    logger.info(
        "Starting kite holdings pipeline | excel=%s | dry_run=%s",
        excel_path,
        dry_run,
    )

    # ----------------------------------
    # 1. Parse
    # ----------------------------------
    kite_holdings_extract, month_year = extract_kite_holding(excel_path)

    # ----------------------------------
    # 2. Load reference data
    # ----------------------------------
    engine = get_read_engine()
    logger.info("Fetching fund_master_data dimension table")

    fund_master = pd.read_sql(
        "SELECT * FROM fund_master_data",
        engine,
    )

    # ----------------------------------
    # 3. Transform
    # ----------------------------------
    kite_holdings_transformed_final = transform_kite_holding(
        kite_holdings_extract,
        month_year,
        fund_master,
    )

    if kite_holdings_transformed_final.empty:
        logger.warning("No data produced by transformer; skipping further steps")
        return

    # ----------------------------------
    # 4. Prepare rows
    # ----------------------------------
    rows = dataframe_to_rows(kite_holdings_transformed_final)

    # ----------------------------------
    # 5. DRY RUN guard
    # ----------------------------------
    if dry_run:
        logger.info(
            "[DRY RUN] %d rows prepared for Google Sheets. No data written.",
            len(rows),
        )
        return

    # ----------------------------------
    # 6. Write to Google Sheets
    # ----------------------------------
    sheets_service = get_sheets_service(SERVICE_ACCOUNT_FILE)

    append_rows(
        sheets_service=sheets_service,
        spreadsheet_id=SPREADSHEET_ID,
        sheet_name=SHEET_NAME,
        rows=rows,
    )

    logger.info(
        "kite holdings content successfully written to Google Sheets | rows=%d",
        len(rows),
    )

    logger.info("kite holdings pipeline completed successfully")