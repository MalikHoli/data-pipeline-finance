import sys
from pathlib import Path
import logging
from datetime import datetime

# Allow `python scripts/...` to import from `src/`
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.logging import logger

from src.pipelines.vest.vest_investment_exchange_rate_to_postgres import run as run_vest_investment_exchange_rate_pipeline

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
INPUT_DIR = Path("data/inbound/bank_statement")
FILE_PATTERN = "OpTransactionHistory_*"
RUN_MODE = "delta"
BACKUP_BEFORE_TRUNCATE = False

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

    logger.info("Starting ACTUAL RUN batch | run_mode=%s", RUN_MODE)

    # 3) Run pipeline for each file in actual-run mode
    for file_path in files:
        logger.info("[RUN] Processing: %s", file_path)

        # Pipeline 1: investment exchange rate
        run_vest_investment_exchange_rate_pipeline(
            pdf_path=file_path,
            dry_run=False,
            run_mode=RUN_MODE,
            backup_before_truncate=BACKUP_BEFORE_TRUNCATE,
        )
        
        logger.info("*" * 70)

    logger.info("ACTUAL RUN batch completed | files=%d", len(files))


if __name__ == "__main__":
    main()