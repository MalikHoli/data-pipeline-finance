import pandas as pd
from typing import Final, Callable
from sqlalchemy.engine import Engine

from src.common.logging import logger
from src.loaders.postgres.common import _loading_to_postgres

POSTGRES_TABLE_NAME: Final = "indmoney_detailed_statement_transformed"

def load_indmoney_transformed_transactions(
        indmoney_transactions_transformed_df: pd.DataFrame,
        get_write_engine: Callable[[], Engine],
        dry_run: bool,
        run_mode: str = "delta",
        backup_before_truncate: bool = False,
) -> None:
    """
    Load transformed indmoney transactions into postgres table `indmoney_detailed_statement_transformed`

    Parameters
    ----------
    indmoney_transactions_transformed_df: pd.DataFrame
        Output dataframe from transform_indmoney_transactions
    get_write_engine: Callable[[], Engine]
        Factory that returns a SQLAlchemy engine with write access
    dry_run: bool
        When True, runs all steps except the final postgres write
    run_mode: str
        Loading strategy (e.g. "delta", "full") forwarded to the loader
    backup_before_truncate: bool
        When True, backs up the table before truncating in full-load mode

    Returns
    -------
    None
    """
    logger.info("Starting indmoney transformed transactions loader")

    _loading_to_postgres(
        indmoney_transactions_transformed_df,
        POSTGRES_TABLE_NAME,
        get_write_engine,
        dry_run,
        run_mode,
        backup_before_truncate,
    )
