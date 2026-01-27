import pandas as pd
from typing import Callable
from sqlalchemy.engine import Engine

from src.common.logging import logger

def _loading_to_postgres(
        df: pd.DataFrame,
        POSTGRES_TABLE_NAME: str,
        get_write_engine: callable[[],Engine],
) -> None:
    """
    this fucntion provides the common format for all loaders

    Parameters
    ----------
    df: pd.DataFrame
        input dataframe by loaders
    POSTGRES_TABLE_NAME: str
        The postgres table name to write data into
    get_write_engine
        Zero-argument callable that returns a SQLAlchemy write-enabled
        Postgres engine.
    
    Returns
    -------
    None
    """
    if df.empty:
        logger.warning(
            "dataframe is empty hence returning the flow"
        )
        return
    else:
        logger.info(
            "detected dataframe with %d rows",
            len(df),
        )
    
    if not get_write_engine:
        logger.error(
            "Failed to get the SQLAlchemy write-enabled Postgres engine"
        )
        raise ValueError("Failed to get the SQLAlchemy write-enabled Postgres engine")
    
    engine = get_write_engine()

    try:
        df.to_sql(
            name=POSTGRES_TABLE_NAME,
            con=engine,
            if_exists="append",
            index=False, #prevents DataFrame index from being written as a column
        )

        logger.info(
            "Successfully inserted data into %s | rows=%d",
            POSTGRES_TABLE_NAME,
            len(df),
        )

    except Exception as exc:
        logger.error(
            "to_sql failed | table=%s | rows=%d | columns=%s",
            POSTGRES_TABLE_NAME,
            len(df),
            list(df.columns),
            exc_info=True,
        )
        raise