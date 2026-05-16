from pathlib import Path
from src.common.db import get_write_engine
from src.common.logging import logger
from src.parsers.pdf.indmoney_statement_period import extract_indmoney_statement_period
from src.parsers.pdf.indmoney_statement_transactions import extract_indmoney_detailed_transactions
from src.transformers.indmoney.indmoney_raw_transactions_transformer import transform_indmoney_raw_transactions
from src.loaders.postgres.indmoney.indmoney_statement_raw_transactions_loader import load_indmoney_raw_transactions
from src.pipelines.indmoney.validations import validate_indmoney_raw_transactions_df

def run(
        pdf_path: str | Path,
        dry_run: bool = False,
        run_mode: str = "delta",
        backup_before_truncate: bool = False,
) -> None:
    """
    End-to-end pipeline: parse → transform → validate → load indmoney raw transactions into postgres

    Parameters
    ----------
    pdf_path: str | Path
        Path to the indmoney statement PDF file
    dry_run: bool
        When True, runs all steps except the final postgres write
    run_mode: str
        Loading strategy (e.g. "delta", "full") forwarded to the loader
    backup_before_truncate: bool
        When True, backs up the postgres table before truncating in full-load mode

    Returns
    -------
    None
    """
    logger.info("Starting indmoney raw transaction pipeline")

    month_year = extract_indmoney_statement_period(pdf_path)

    indmoney_raw_transactions_parsed_df = extract_indmoney_detailed_transactions(pdf_path, month_year)

    indmoney_raw_transaction_df = transform_indmoney_raw_transactions(indmoney_raw_transactions_parsed_df)

    validate_indmoney_raw_transactions_df(indmoney_raw_transaction_df)

    load_indmoney_raw_transactions(
        indmoney_raw_transaction_df,
        get_write_engine,
        dry_run,
        run_mode,
        backup_before_truncate,
    )

    logger.info("indmoney raw transactions pipeline finished successfully | Period: %s", month_year)