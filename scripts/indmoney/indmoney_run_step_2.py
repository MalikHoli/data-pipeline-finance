import sys
from pathlib import Path
from datetime import datetime
import logging

# Allow `python scripts/...` to import from `src/`
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.logging import logger
from src.pipelines.execution_mode import LoadExecutionMode
from src.pipelines.indmoney.indmoney_raw_transactions_to_postgres import run as run_indmoney_raw_pipeline
from src.pipelines.indmoney.indmoney_month_end_balance_and_or_transformed_transaction_to_postgres import (
    run as run_indmoney_month_end_and_transformed_pipeline,
)
from src.parsers.pdf.indmoney_statement_period import extract_indmoney_statement_period

# -------------------------------------------------------------------
# Logging Setup
# -------------------------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

script_name = Path(sys.argv[0]).stem
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = LOG_DIR / f"{script_name}_{timestamp}.txt"

file_handler = logging.FileHandler(log_file)
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
INPUT_DIR = Path("data/inbound/indmoney_statement")
LOAD_MODE = LoadExecutionMode.LOAD_ALL
RAW_TRANSACTIONS_RUN_MODE = "delta"
MONTH_END_RUN_MODE = "delta"
BACKUP_BEFORE_TRUNCATE = False


def _sort_key(path: Path) -> tuple[int, int]:
    """
    Sort indmoney statement PDFs chronologically by reading the period from
    the PDF itself. month_year is in MM/YYYY format (e.g. "5/2022").
    Processing in chronological order ensures the month-end balance chain
    is built correctly (each month depends on the previous month's balance).
    """
    logging.disable(logging.CRITICAL)
    try:
        month_year = extract_indmoney_statement_period(path)
    finally:
        logging.disable(logging.NOTSET)
    month_str, year_str = month_year.split("/")
    return (int(year_str), int(month_str))


def main() -> None:
    if not INPUT_DIR.exists():
        raise FileNotFoundError(f"Input directory not found: {INPUT_DIR}")

    files = [p for p in INPUT_DIR.iterdir() if p.is_file()]
    if not files:
        raise FileNotFoundError(f"No files found in {INPUT_DIR}")

    files = sorted(files, key=_sort_key)

    logger.info("Starting ACTUAL RUN batch | files=%d", len(files))

    for file_path in files:
        logger.info("[RUN] Processing: %s", file_path)

        logger.info("*" * 70)
        # Pipeline 1: raw transactions
        run_indmoney_raw_pipeline(
            pdf_path=file_path,
            dry_run=False,
            run_mode=RAW_TRANSACTIONS_RUN_MODE,
            backup_before_truncate=BACKUP_BEFORE_TRUNCATE,
        )

        logger.info("*" * 70)
        # Pipeline 2: month-end balance + transformed transactions
        run_indmoney_month_end_and_transformed_pipeline(
            pdf_path=str(file_path),
            dry_run=False,
            load_mode=LOAD_MODE,
            run_mode=MONTH_END_RUN_MODE,
            backup_before_truncate=BACKUP_BEFORE_TRUNCATE,
        )
        logger.info("*" * 70)

    logger.info("ACTUAL RUN batch completed | files=%d", len(files))


if __name__ == "__main__":
    main()
