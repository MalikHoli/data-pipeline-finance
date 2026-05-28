import sys
from pathlib import Path
import logging
from datetime import datetime

# Allow `python scripts/...` to import from `src/`
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.logging import logger
from src.pipelines.indmoney.indmoney_deposits_from_bank_transactions_to_postgres import run as run_deposits_bank
from src.pipelines.indmoney.indmoney_deposits_from_indmoney_transactions_to_postgres import run as run_deposits_indmoney
from src.pipelines.indmoney.indmoney_investment_exchange_rate_to_postgres import run as run_exchange_rate
from src.pipelines.indmoney.indmoney_holdings_to_postgres import run as run_holdings
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
BANK_INPUT_DIR      = Path("data/inbound/bank_statement")
BANK_FILE_PATTERN   = "OpTransactionHistory_*"
INDMONEY_INPUT_DIR  = Path("data/inbound/indmoney_statement")

DEPOSITS_RUN_MODE   = "full"
HOLDINGS_RUN_MODE   = "delta"
BACKUP_BEFORE_TRUNCATE = False


def _collect_bank_files() -> list[Path]:
    if not BANK_INPUT_DIR.exists():
        raise FileNotFoundError(f"Input directory not found: {BANK_INPUT_DIR}")
    files = [p for p in BANK_INPUT_DIR.glob(BANK_FILE_PATTERN) if p.is_file()]
    if not files:
        raise FileNotFoundError(
            f"No files found in {BANK_INPUT_DIR} matching pattern: {BANK_FILE_PATTERN}"
        )
    return sorted(files)


def _collect_indmoney_files() -> list[Path]:
    if not INDMONEY_INPUT_DIR.exists():
        raise FileNotFoundError(f"Input directory not found: {INDMONEY_INPUT_DIR}")
    files = [p for p in INDMONEY_INPUT_DIR.iterdir() if p.is_file()]
    if not files:
        raise FileNotFoundError(f"No files found in {INDMONEY_INPUT_DIR}")
    return files


def main() -> None:
    bank_files     = _collect_bank_files()
    indmoney_files = _collect_indmoney_files()

    logger.info(
        "Starting ACTUAL RUN step 1 | bank_files=%d | indmoney_files=%d",
        len(bank_files),
        len(indmoney_files),
    )

    # # ---------------------------------------------------------------
    # # Phase 1: Deposit extraction (prerequisite for exchange rate)
    # # ---------------------------------------------------------------
    # logger.info("=" * 70)
    # logger.info("PHASE 1: Deposits from bank statements")
    # for file_path in bank_files:
    #     logger.info("[RUN] Processing bank statement: %s", file_path)
    #     run_deposits_bank(
    #         pdf_path=file_path,
    #         dry_run=False,
    #         run_mode=DEPOSITS_RUN_MODE,
    #         backup_before_truncate=BACKUP_BEFORE_TRUNCATE,
    #     )
    #     logger.info("*" * 70)

    # logger.info("=" * 70)
    # logger.info("PHASE 2: Deposits from indmoney statements")
    # for file_path in indmoney_files:
    #     logger.info("[RUN] Processing indmoney statement: %s", file_path)
    #     run_deposits_indmoney(
    #         pdf_path=file_path,
    #         dry_run=False,
    #         run_mode=DEPOSITS_RUN_MODE,
    #         backup_before_truncate=BACKUP_BEFORE_TRUNCATE,
    #     )
    #     logger.info("*" * 70)

    # # ---------------------------------------------------------------------------
    # # Phase 2: Investment exchange rate (depends on deposits) Always full load
    # # ---------------------------------------------------------------------------
    # logger.info("=" * 70)
    # logger.info("PHASE 3: Investment exchange rate compute")
    # run_exchange_rate(
    #     dry_run=False,
    #     run_mode="full",
    #     backup_before_truncate=BACKUP_BEFORE_TRUNCATE,
    # )
    # logger.info("*" * 70)

    # ---------------------------------------------------------------
    # Phase 3: Holdings snapshot
    # ---------------------------------------------------------------
    logger.info("=" * 70)
    logger.info("PHASE 4: Holdings (indmoney_summary_statement)")
    indmoney_files_sorted = sorted(indmoney_files)
    for file_path in indmoney_files_sorted:
        logger.info("[RUN] Processing holdings: %s", file_path)
        run_holdings(
            pdf_path=file_path,
            dry_run=False,
            run_mode=HOLDINGS_RUN_MODE,
            backup_before_truncate=BACKUP_BEFORE_TRUNCATE,
        )
        logger.info("*" * 70)

    logger.info(
        "ACTUAL RUN step 1 completed | bank_files=%d | indmoney_files=%d",
        len(bank_files),
        len(indmoney_files),
    )


if __name__ == "__main__":
    main()
