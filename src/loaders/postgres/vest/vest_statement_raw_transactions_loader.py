import pandas as pd
from typing import Final,Callable
from sqlalchemy.engine import Engine

from src.common.logging import logger
from src.loaders.postgres.common import _loading_to_postgres

POSTGRES_TABLE_NAME: Final = "vest_detailed_statement"
REQUIRED_COLUMNS_LIST: Final = [
        "Trade Date",
        "Activity",
        "Symbol",
        "Description",
        "Quantity",
        "Price",
        "Amount",
]
RENAME_COLUMNS_AS_PER_POSTGRES_SCHEMA_DICT: Final = {
       "Trade Date":"trade_date",
       "Activity":"activity",
       "Symbol":"symbol",
       "Description":"description",
       "Quantity":"quantity",
       "Price":"price",
       "Amount":"amount",
}

# =========================
# Main loader
# =========================
def load_vest_raw_transactions(
        vest_parsed_trasaction_df: pd.DataFrame,
        get_write_engine: Callable[[],Engine],
        dry_run: bool,
) -> None:
    """
    loads the parsed vest pdf to postgres    
    
    Parameters
    ----------
    vest_parsed_trasaction_df: pd.DataFrame
        Output dataframe from extract_vest_detailed_transactions
    get_write_engine
        Zero-argument callable that returns a SQLAlchemy write-enabled
        Postgres engine.
    
    Returns
    -------
    None
    """
    logger.info("Starting vest raw transaction loader")

    # Selecting required columns to write
    vest_parsed_trasaction_df = vest_parsed_trasaction_df[REQUIRED_COLUMNS_LIST].copy()

    # renaming as per postgres_shema
    vest_parsed_trasaction_df.rename(
        columns=RENAME_COLUMNS_AS_PER_POSTGRES_SCHEMA_DICT,
        inplace=True,
    )
    
    _loading_to_postgres(
        vest_parsed_trasaction_df,
        POSTGRES_TABLE_NAME,
        get_write_engine,
        dry_run,
    )
