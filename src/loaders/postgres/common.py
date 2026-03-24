import pandas as pd
from typing import Callable
from sqlalchemy.engine import Engine

from src.common.logging import logger
from src.repositories.full_load_operations import TableRepository

def _loading_to_postgres(
        df: pd.DataFrame,
        POSTGRES_TABLE_NAME: str,
        get_write_engine: Callable[[],Engine],
        dry_run: bool,
        run_mode: str = "delta",
        backup_before_truncate: bool = False,
) -> None:
    """
    this fucntion provides the common format for all loaders

    Parameters
    ----------
    df: pd.DataFrame
        input dataframe to load into DB
    POSTGRES_TABLE_NAME: str
        Destination postgres table name
    get_write_engine
        Zero-argument callable that returns a SQLAlchemy write-enabled
        Postgres engine.
    dry_run : bool
        If True, performs validation/logging only and skips all DB writes.
    run_mode : str
        "delta" appends rows. "full" truncates the table once per process
        before the first write to that table.
    backup_before_truncate : bool
        If True (and run_mode is "full" with dry_run=False), creates a
        timestamped backup table before truncate.
    
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
    

    # ----------------------------------
    # DRY RUN guard
    # ----------------------------------
    if dry_run:
        if run_mode == "full" or backup_before_truncate:
            logger.info(
                "Ignoring run_mode=%s and backup_before_truncate=%s because dry_run=True",
                run_mode,
                backup_before_truncate,
            )

        logger.info(
            "[DRY RUN] %d rows prepared | postgres table = %s . No data written.",
            len(df),
            POSTGRES_TABLE_NAME
        )
        return
    
    engine = get_write_engine()

    if run_mode == "full": 
        tableOperations = TableRepository(engine)
        
        tableOperations.prepare_table_for_full_load(
            POSTGRES_TABLE_NAME,
            backup_before_truncate,
        )

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