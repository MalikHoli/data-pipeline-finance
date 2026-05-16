import sys
from pathlib import Path
import logging
from datetime import datetime

# Allow `python scripts/...` to import from `src/`
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.logging import logger
from src.pipelines.indmoney.indmoney_investment_exchange_rate_to_postgres import run as indmoney_investment_exchange_rate_run

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
DRY_RUN = True


def main() -> None:
    logger.info("INDMONEY DRY RUN for investment exchange rate pipleline | This pipeline should always run in full mode")

    # Step 1: load deposits from bank transactions
    indmoney_investment_exchange_rate_run(
        dry_run=DRY_RUN,
        run_mode="full",
        backup_before_truncate=False,
    )
    logger.info("*" * 70)


    logger.info(
        "INDMONEY DRY RUN for investment exchange rate pipleline is completed",
    )


if __name__ == "__main__":
    main()
