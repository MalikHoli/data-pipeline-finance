import pandas as pd
from typing import Final,Callable
from sqlalchemy.engine import Engine

from src.common.logging import logger
from src.loaders.postgres.common import _loading_to_postgres

POSTGRES_TABLE_NAME: Final = "vest_summary_statement"

# =========================
# Main loader
# =========================
def load_vest_holdings(
        vest_holdings_transformed_df: pd.DataFrame,
        get_write_engine: Callable[[], Engine],
        dry_run: bool,
) -> None:
    """
    loads the data from vest transformer to postgres    
    
    Parameters
    ----------
    vest_holdings_transformed_df: pd.DataFrame
        Output dataframe from vest_holdings_transformer
    get_write_engine
        Zero-argument callable that returns a SQLAlchemy write-enabled
        Postgres engine.
    dry_run : bool
        If True, executes full pipeline except postgres write
        
    Returns
    -------
    None
    """
    logger.info("Starting vest holding loader")

    _loading_to_postgres(
        vest_holdings_transformed_df,
        POSTGRES_TABLE_NAME,
        get_write_engine,
        dry_run,
    )