from src.common.logging import logger
from src.common.db import get_write_engine

from src.parsers.pdf.bank_statement_period import extract_bank_statement_period
from src.parsers.pdf.bank_statement import extract_bank_table_transactions
from src.parsers.pdf.indmoney_statement_period import extract_indmoney_statement_period
from src.parsers.pdf.indmoney_statement_income import extract_indmoney_income_transactions
from src.transformers.indmoney.indmoney_investment_exchange_rate_compute import transform_indmoney_investment_exchange_rate
from src.loaders.postgres.indmoney.indmoney_investment_exchange_rate_loader import load_indmoney_investment_amount_exch_rate


def run(bank_pdf_path: str, indmoney_pdf_path: str, dry_run: bool = False) -> None:
    logger.info("Starting indmoney investment amount exchange rate compute pipeline")

    bank_month_year = extract_bank_statement_period(bank_pdf_path)
    indmoney_month_year = extract_indmoney_statement_period(indmoney_pdf_path)

    bank_statement_df = extract_bank_table_transactions(bank_pdf_path, bank_month_year)
    indmoney_income_df = extract_indmoney_income_transactions(indmoney_pdf_path, indmoney_month_year)

    exchange_rate_df = transform_indmoney_investment_exchange_rate(
        bank_statement_df,
        indmoney_income_df,
        indmoney_month_year,
    )

    if exchange_rate_df.empty:
        logger.info("No indmoney deposits found hence no data written to postgres")
        return

    load_indmoney_investment_amount_exch_rate(exchange_rate_df, get_write_engine, dry_run)
    logger.info("indmoney investment amount exchange rate compute pipeline finished successfully | Period: %s", indmoney_month_year)
