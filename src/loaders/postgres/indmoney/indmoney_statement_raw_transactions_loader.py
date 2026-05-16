import pandas as pd
from typing import Final, Callable
from sqlalchemy.engine import Engine
from src.common.logging import logger
from src.loaders.postgres.common import _loading_to_postgres

POSTGRES_TABLE_NAME: Final = "indmoney_detailed_statement"

def load_indmoney_raw_transactions(
        indmoney_raw_transaction_df: pd.DataFrame,
        get_write_engine: Callable[[], Engine],
        dry_run: bool,
        run_mode: str = "delta",
        backup_before_truncate: bool = False,
) -> None:
    """
    Load transformed indmoney raw transactions into the postgres table `indmoney_detailed_statement`

    Parameters
    ----------
    indmoney_raw_transaction_df: pd.DataFrame
        Output dataframe from transform_indmoney_raw_transactions
    get_write_engine: Callable[[], Engine]
        Factory that returns a SQLAlchemy engine with write access
    dry_run: bool
        When True, logs the intended operation without writing to postgres
    run_mode: str
        Loading strategy passed to _loading_to_postgres (e.g. "delta", "full")
    backup_before_truncate: bool
        When True, backs up the table before truncating in full-load mode

    Returns
    -------
    None
    """
    logger.info("Starting indmoney raw transaction loader")
    _loading_to_postgres(
        indmoney_raw_transaction_df,
        POSTGRES_TABLE_NAME,
        get_write_engine,
        dry_run,
        run_mode,
        backup_before_truncate,
    )