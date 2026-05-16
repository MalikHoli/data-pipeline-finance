import pandas as pd
from typing import Final,Callable
from sqlalchemy.engine import Engine

from src.common.logging import logger
from src.loaders.postgres.common import _loading_to_postgres

POSTGRES_TABLE_NAME: Final = "indmoney_usd_to_inr_deposit_exch_rate"

# =========================
# Main loader
# =========================
def load_investment_amount_exch_rate(
        indmoney_investment_amount_exch_rate_computed_df: pd.DataFrame,
        get_write_engine: Callable[[], Engine],
        dry_run: bool,
        run_mode: str = "delta",
        backup_before_truncate: bool = False,
) -> None:
    """
    loads the data from indmoney investment amount exchange rate information to postgres    
    
    Parameters
    ----------
    indmoney_investment_amount_exch_rate_computed_df: pd.DataFrame
        Output dataframe from the repository (SQL query that cretes a table based on the "indmoney_deposits_bank_statement" and
        "indmoney_deposits_indmoney_statement" postgres table)
    get_write_engine
        Zero-argument callable that returns a SQLAlchemy write-enabled
        Postgres engine.
    dry_run : bool
        If True, executes full pipeline except postgres write.
    run_mode : str
        "delta" appends rows. "full" truncates target table once before load.
    backup_before_truncate : bool
        Whether to create a timestamped backup table before truncate in full mode.  
    
    Returns
    -------
    None
    """
    logger.info("Starting vest transaction amount exchange rate loader")

    _loading_to_postgres(
        indmoney_investment_amount_exch_rate_computed_df,
        POSTGRES_TABLE_NAME,
        get_write_engine,
        dry_run,
        run_mode,
        backup_before_truncate,
    )