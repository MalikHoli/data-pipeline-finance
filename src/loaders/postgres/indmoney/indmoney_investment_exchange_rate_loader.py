import pandas as pd
from typing import Final, Callable
from sqlalchemy.engine import Engine

from src.common.logging import logger
from src.loaders.postgres.common import _loading_to_postgres

POSTGRES_TABLE_NAME: Final = "indmoney_usd_to_inr_deposit_exch_rate"


def load_indmoney_investment_amount_exch_rate(df: pd.DataFrame, get_write_engine: Callable[[], Engine], dry_run: bool) -> None:
    logger.info("Starting indmoney transaction amount exchange rate loader")
    _loading_to_postgres(df, POSTGRES_TABLE_NAME, get_write_engine, dry_run)
