from src.common.logging import logger
from src.common.db import get_read_engine
from src.common.db import get_write_engine

from src.loaders.postgres.indmoney.indmoney_investment_exchange_rate_loader import load_investment_amount_exch_rate
from src.repositories.indmoney_reference_repository import IndmoneyReferenceRepository
from src.pipelines.indmoney.validations import validate_indmoney_investment_exchange_rate_df

def run(
        dry_run: bool=False,
        run_mode: str = "full",
        backup_before_truncate: bool = False,
)-> None:
    """
    Runs the postgres query → compute investment amount exchage rate → write to another postgres table.

    Parameters
    ----------
    excel_path : Path
        Path to bank statement pdf
    dry_run : bool
        If True, executes full pipeline except postgres write
     run_mode : str
        "delta" appends rows. "full" enables one-time pre-load truncate.
    backup_before_truncate : bool
        Whether to create a timestamped backup table before truncate in full mode.
    """
    logger.info("Starting indmoney invetment amount exchange rate compute pipeline")
    
    read_engine = get_read_engine()

    indmoney_reference_repository = IndmoneyReferenceRepository(read_engine)

    indmoney_investment_amount_exch_rate_computed_df = indmoney_reference_repository.fetch_deposits_and_compute_exchange_rate()

    validate_indmoney_investment_exchange_rate_df(indmoney_investment_amount_exch_rate_computed_df)

    load_investment_amount_exch_rate(
        indmoney_investment_amount_exch_rate_computed_df,
        get_write_engine,
        dry_run,
        run_mode,
        backup_before_truncate,
    )

    logger.info("indmoney invetment amount exchange rate compute pipeline finished successfully | lines: %d", len(indmoney_investment_amount_exch_rate_computed_df))