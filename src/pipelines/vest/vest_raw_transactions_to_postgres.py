from pathlib import Path

from src.common.db import get_write_engine
from src.common.logging import logger

from src.parsers.pdf.vest_statement_period import extract_vest_statement_period
from src.parsers.pdf.vest_statement_transactions import extract_vest_detailed_transactions
from src.transformers.vest.vest_raw_transactions_transformer import transform_vest_raw_transactions
from src.loaders.postgres.vest.vest_statement_raw_transactions_loader import load_vest_raw_transactions

def run(
        pdf_path: Path,
        dry_run: bool = False,
) -> None:
    """
    Runs the vest transactions pdf → postgres pipeline.

    Parameters
    ----------
    excel_path : Path
        Path to vest pdf
    dry_run : bool
        If True, executes full pipeline except postgres write
    """
    logger.info("Starting vest raw transaction pipeline")

    month_year = extract_vest_statement_period(pdf_path)

    vest_raw_transactions_parsed_df = extract_vest_detailed_transactions(pdf_path,month_year)

    vest_raw_transaction_df = transform_vest_raw_transactions(vest_raw_transactions_parsed_df)
 
    load_vest_raw_transactions(
        vest_raw_transaction_df,
        get_write_engine,
        dry_run,
    )

    logger.info("vest raw transactions pipeline finished successfully | Period: %s", month_year)        