import sys
from pathlib import Path
import logging
from datetime import datetime
import re

# Allow `python scripts/...` to import from `src/`
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.logging import logger
from src.pipelines.indmoney.indmoney_raw_transactions_to_postgres import run as indmoney_raw_transactions_pipeline_run

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
INPUT_DIR = Path("data/inbound/indmoney_statement")

RUN_MODE = "full"
BACKUP_BEFORE_TRUNCATE = False

#-------------------------------------------------------------
# Helper functions
#-------------------------------------------------------------

#----------------------------------------------------------------

def main() -> None:
    # 1) Validate folder
    if not INPUT_DIR.exists():
        raise FileNotFoundError(f"Input directory not found: {INPUT_DIR}")

    files = [p for p in INPUT_DIR.iterdir() if p.is_file()]

    logger.info("Starting Indmoney raw transactions DRY RUN batch | run_mode=%s", RUN_MODE)

    # 4) Run pipeline for each file in dry-run mode
    for file_path in files:
        logger.info("[DRY RUN] Processing: %s", file_path)

        logger.info("*" * 70)
        # Pipeline 2: holdings
        indmoney_raw_transactions_pipeline_run(
            pdf_path=file_path,
            dry_run=True,
        )
        logger.info("*" * 70)
        
    logger.info("DRY RUN batch completed | files=%d", len(files))


if __name__ == "__main__":
    main()