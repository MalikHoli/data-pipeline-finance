from pathlib import Path

from src.parsers.pdf.indmoney_statement_transactions import extract_indmoney_detailed_transactions
from src.parsers.pdf.indmoney_statement_period import extract_indmoney_statement_period
from src.transformers.indmoney.indmoney_deposits_from_indmoney_statement_transformer import transform_indmoney_statement_to_get_indmoney_deposits
from src.loaders.postgres.indmoney.indmoney_deposits_from_indmoney_statement_loader import load_indmoney_deposits_from_indmoney_statement_transactions

from src.common.db import get_write_engine
from src.common.logging import logger

def run(
        pdf_path: Path,
        dry_run: bool = False,
        run_mode: str = "delta",
        backup_before_truncate: bool = False,
) -> None:
    """
    Runs the vest holding pdf → postgres pipeline.

    Parameters
    ----------
    excel_path : Path
        Path to indmoney pdf
    dry_run : bool
        If True, executes full pipeline except postgres write
    run_mode : str
        "delta" appends rows. "full" enables one-time pre-load truncate.
    backup_before_truncate : bool
        Whether to create a timestamped backup table before truncate in full mode.
    """
    logger.info("Starting indmoney deposit transactions pipeline")

    month_year = extract_indmoney_statement_period(pdf_path)

    indmoney_transactions_df = extract_indmoney_detailed_transactions(pdf_path,month_year)

    indmoney_deposits_from_indomeny_transactions_df = transform_indmoney_statement_to_get_indmoney_deposits(
        indmoney_transactions_df,
        month_year
    )

    load_indmoney_deposits_from_indmoney_statement_transactions(
        indmoney_deposits_from_indomeny_transactions_df,
        get_write_engine,
        dry_run,
        run_mode,
        backup_before_truncate,
    )

    logger.info("indmoney deposits from indmoney transactions pipeline finished successfully | Period: %s", month_year)        
