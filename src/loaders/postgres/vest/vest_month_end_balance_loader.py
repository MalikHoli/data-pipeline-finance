import pandas as pd
from typing import Final,Callable
from sqlalchemy.engine import Engine

from src.common.logging import logger
from src.loaders.postgres.common import _loading_to_postgres

POSTGRES_TABLE_NAME: Final = "vest_month_end_balance"

# =========================
# Main loader
# =========================
def load_vest_month_end_balance(
        vest_month_end_balance_df: pd.DataFrame,
        get_write_engine: Callable[[], Engine],
        dry_run: bool,
        run_mode: str = "delta",
        backup_before_truncate: bool = False,
) -> None:
    """
    loads the data from vest month end balance information to postgres    
    
    Parameters
    ----------
    vest_month_end_balance_df: pd.DataFrame
        Output dataframe from transform_vest_transactions holding the month end balance information
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
    logger.info("Starting vest month end balance loader")

    _loading_to_postgres(
        vest_month_end_balance_df,
        POSTGRES_TABLE_NAME,
        get_write_engine,
        dry_run,
        run_mode,
        backup_before_truncate,
    )