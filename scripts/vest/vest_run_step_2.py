import sys
from pathlib import Path
from datetime import datetime
import logging
import re

# Allow `python scripts/...` to import from `src/`
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.logging import logger
from src.pipelines.execution_mode import LoadExecutionMode

from src.pipelines.vest.vest_holdings_to_postgres import run as run_vest_holdings_pipeline
from src.pipelines.vest.vest_raw_transactions_to_postgres import run as run_vest_raw_pipeline
from src.pipelines.vest.vest_month_end_balance_and_or_transformed_transaction_to_postgres import (
    run as run_vest_month_end_and_transformed_pipeline,
)

# -------------------------------------------------------------------
# Logging Setup to create .txt log file
# -------------------------------------------------------------------
LOG_DIR = Path("logs")

#**************************************************
# If the folder does not exist → it is created
# If it already exists → nothing happens
LOG_DIR.mkdir(exist_ok=True)
#**************************************************


#**************************************************
# sys.argv gives list containing the command used to start the script
# .stem extracts the filename without extension.
# Get current script name (without .py)
script_name = Path(sys.argv[0]).stem
#**************************************************

# Timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# Creates the full file path.
log_file = LOG_DIR / f"{script_name}_{timestamp}.txt"

# Creates a handler that writes logs
file_handler = logging.FileHandler(log_file)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Uses the same format for the file. So console and file logs look identical
file_handler.setFormatter(formatter)

# Connects the file output to the logger
# Now: logger.info("Hello")
# also writes into the log file.
logger.addHandler(file_handler)

# -------------------------------------------------------------------
# Constants (kept fixed to reduce complexity as requested)
# -------------------------------------------------------------------
INPUT_DIR = Path("data/inbound/vest_statement")
FILE_PATTERN = "Stmt_VSTF_*"
LOAD_MODE = LoadExecutionMode.LOAD_ALL
PERIOD_RE = re.compile(r"([A-Za-z]{3})(\d{4})$")
MONTH_INDEX = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
RUN_MODE = "full"
BACKUP_BEFORE_TRUNCATE = False

#-------------------------------------------------------------
# Helper functions
#-------------------------------------------------------------
def _sort_key(path: Path) -> tuple[int, int, str]:
    """Sort files chronologically from suffix (e.g., Apr2025)."""
    match = PERIOD_RE.search(path.stem)
    if not match:
        return (9999, 99, path.stem.lower())

    month = MONTH_INDEX.get(match.group(1).lower(), 99)
    year = int(match.group(2))
    return (year, month, path.stem.lower())
#----------------------------------------------------------------

def main() -> None:
    # 1) Validate folder
    if not INPUT_DIR.exists():
        raise FileNotFoundError(f"Input directory not found: {INPUT_DIR}")

    # 2) Collect files matching the fixed pattern
    files = [p for p in INPUT_DIR.glob(FILE_PATTERN) if p.is_file()]
    
    if not files:
        raise FileNotFoundError(
            f"No files found in {INPUT_DIR} matching pattern: {FILE_PATTERN}"
        )

    # 3) Run files in chronological order for predictable dependencies
    files = sorted(files, key=_sort_key)

    logger.info("Starting ACTUAL RUN batch | run_mode=%s", RUN_MODE)

    # 4) Run pipeline for each file in dry-run mode
    for file_path in files:
        logger.info("[RUN] Processing: %s", file_path)

        logger.info("*" * 70)
        # Pipeline 2: holdings
        run_vest_holdings_pipeline(
            pdf_path=file_path,
            dry_run=False,
            run_mode=RUN_MODE,
            backup_before_truncate=BACKUP_BEFORE_TRUNCATE,
        )
        logger.info("*" * 70)
        # Pipeline 3: raw transactions
        run_vest_raw_pipeline(
            pdf_path=file_path,
            dry_run=False,
            run_mode=RUN_MODE,
            backup_before_truncate=BACKUP_BEFORE_TRUNCATE,
        )
        logger.info("*" * 70)
        # Pipeline 4: month-end + transformed transactions
        run_vest_month_end_and_transformed_pipeline(
            pdf_path=str(file_path),
            dry_run=False,
            load_mode=LOAD_MODE,
            run_mode=RUN_MODE,
            backup_before_truncate=BACKUP_BEFORE_TRUNCATE,
        )
        logger.info("*" * 70)
    logger.info("ACTUAL RUN batch completed | files=%d", len(files))


if __name__ == "__main__":
    main()