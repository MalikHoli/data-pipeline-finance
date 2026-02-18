from src.common.db import get_write_engine
from src.common.logging import logger

from src.parsers.pdf.indmoney_statement_period import extract_indmoney_statement_period
from src.parsers.pdf.indmoney_statement_holdings import extract_indmoney_holdings
from src.transformers.indmoney.indmoney_holdings_transformer import transform_indmoney_holdings
from src.loaders.postgres.indmoney.indmoney_statement_holdings_loader import load_indmoney_holdings


def run(pdf_path: str, dry_run: bool = False) -> None:
    logger.info("Starting indmoney holdings pipeline")

    month_year = extract_indmoney_statement_period(pdf_path)
    holdings_df = extract_indmoney_holdings(pdf_path, month_year)
    holdings_transformed_df = transform_indmoney_holdings(holdings_df, month_year)

    load_indmoney_holdings(holdings_transformed_df, get_write_engine, dry_run)
    logger.info("indmoney holdings pipeline finished successfully | Period: %s", month_year)
