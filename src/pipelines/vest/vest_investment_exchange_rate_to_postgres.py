from src.common.logging import logger
from src.common.db import get_write_engine

from src.parsers.pdf.bank_statement_period import extract_bank_statement_period
from src.parsers.pdf.bank_statement import extract_bank_table_transactions
from src.transformers.vest.vest_investment_exchange_rate_compute import transform_bank_statement_to_get_investment_exchange_rate
from src.loaders.postgres.vest.vest_investment_exchange_rate_loader import load_investment_amount_exch_rate

def run(
        pdf_path: str,
        dry_run: bool=False,
)-> None:
    """
    Runs the bank statement pdf → compute investment amount exchage rate → postgres pipeline.

    Parameters
    ----------
    excel_path : Path
        Path to bank statement pdf
    dry_run : bool
        If True, executes full pipeline except postgres write
    """
    logger.info("Starting vest invetment amount exchange rate compute pipeline")
    
    month_year = extract_bank_statement_period(pdf_path)
    
    bank_statement_df = extract_bank_table_transactions(pdf_path,month_year)
    
    vest_investment_amount_exch_rate_computed_df = transform_bank_statement_to_get_investment_exchange_rate(bank_statement_df,month_year)

    if vest_investment_amount_exch_rate_computed_df.empty:
        logger.info("No vest deposits found hence no data written to postgres")
        logger.info("vest invetment amount exchange rate compute pipeline finished successfully | Period: %s", month_year)
        return

    load_investment_amount_exch_rate(
        vest_investment_amount_exch_rate_computed_df,
        get_write_engine,
        dry_run,
    )

    logger.info("vest invetment amount exchange rate compute pipeline finished successfully | Period: %s", month_year)






