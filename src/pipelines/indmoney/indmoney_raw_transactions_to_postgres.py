from src.common.db import get_write_engine
from src.common.logging import logger

from src.parsers.pdf.indmoney_statement_period import extract_indmoney_statement_period
from src.parsers.pdf.indmoney_statement_transactions import extract_indmoney_detailed_transactions
from src.transformers.indmoney.indmoney_raw_transactions_transformer import transform_indmoney_raw_transactions
from src.loaders.postgres.indmoney.indmoney_statement_raw_transactions_loader import load_indmoney_raw_transactions


def run(pdf_path: str, dry_run: bool = False) -> None:
    logger.info("Starting indmoney raw transaction pipeline")

    month_year = extract_indmoney_statement_period(pdf_path)
    parsed_df = extract_indmoney_detailed_transactions(pdf_path, month_year)
    transformed_df = transform_indmoney_raw_transactions(parsed_df)

    if transformed_df.empty:
        logger.warning("No indmoney raw transactions to load for %s", month_year)
        return

    load_indmoney_raw_transactions(transformed_df, get_write_engine, dry_run)
    logger.info("indmoney raw transactions pipeline finished successfully | Period: %s", month_year)
