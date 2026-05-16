import sys
from pathlib import Path
import logging
from datetime import datetime

# Allow `python scripts/...` to import from `src/`
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.logging import logger
from src.pipelines.indmoney.indmoney_deposits_from_bank_transactions_to_postgres import run as run_indmoney_depo_bank
from src.pipelines.indmoney.indmoney_deposits_from_indmoney_transactions_to_postgres import run as run_indmoney_depo_ind

# -------------------------------------------------------------------
# Logging Setup to create .txt log file
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
BANK_INPUT_DIR = Path("data/inbound/bank_statement")
BANK_FILE_PATTERN = "OpTransactionHistory_*"

INDMONEY_INPUT_DIR = Path("data/inbound/indmoney_statement")

RUN_MODE = "full"
BACKUP_BEFORE_TRUNCATE = False
DRY_RUN = True


def _collect_files(input_dir: Path, file_pattern: str | None = None) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    if file_pattern:
        files = [p for p in input_dir.glob(file_pattern) if p.is_file()]
        not_found_message = (
            f"No files found in {input_dir} matching pattern: {file_pattern}"
        )
    else:
        files = [p for p in input_dir.iterdir() if p.is_file()]
        not_found_message = f"No files found in {input_dir}"

    if not files:
        raise FileNotFoundError(not_found_message)

    return sorted(files)


def main() -> None:
    logger.info("Starting INDMONEY batch | run_mode=%s", RUN_MODE)

    # Step 1: load deposits from bank transactions
    bank_files = _collect_files(BANK_INPUT_DIR, BANK_FILE_PATTERN)
    for file_path in bank_files:
        logger.info("[RUN][STEP-1] Processing bank statement: %s", file_path)
        run_indmoney_depo_bank(
            pdf_path=file_path,
            dry_run=DRY_RUN,
            run_mode=RUN_MODE,
            backup_before_truncate=BACKUP_BEFORE_TRUNCATE,
        )
        logger.info("*" * 70)

    # Step 2: load deposits from indmoney transactions
    indmoney_files = _collect_files(INDMONEY_INPUT_DIR)
    for file_path in indmoney_files:
        logger.info("[RUN][STEP-2] Processing indmoney statement: %s", file_path)
        run_indmoney_depo_ind(
            pdf_path=file_path,
            dry_run=DRY_RUN,
            run_mode=RUN_MODE,
            backup_before_truncate=BACKUP_BEFORE_TRUNCATE,
        )
        logger.info("*" * 70)

    logger.info(
        "INDMONEY batch completed | bank_files=%d | indmoney_files=%d",
        len(bank_files),
        len(indmoney_files),
    )


if __name__ == "__main__":
    main()
