import pandas as pd
from typing import Final, Callable
from sqlalchemy.engine import Engine

from src.common.logging import logger
from src.loaders.postgres.common import _loading_to_postgres

POSTGRES_TABLE_NAME: Final = "indmoney_detailed_statement"


def load_indmoney_raw_transactions(df: pd.DataFrame, get_write_engine: Callable[[], Engine], dry_run: bool) -> None:
    logger.info("Starting indmoney raw transaction loader")
    _loading_to_postgres(df, POSTGRES_TABLE_NAME, get_write_engine, dry_run)
