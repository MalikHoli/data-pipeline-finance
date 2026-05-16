# Older Python versions needed:Set[str] but code has set[str]
# This import makes modern syntax safe and consistent.
from __future__ import annotations 

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.common.logging import logger

# Tracks tables already prepared in this Python process during full mode.
_PREPARED_TABLES_FOR_FULL_LOAD: set[str] = set()

# Allowlist for table names that can be used in structural SQL statements.
_ALLOWED_FULL_LOAD_TABLES = {
    "vest_usd_to_inr_deposit_exch_rate",
    "vest_detailed_statement",
    "vest_month_end_balance",
    "vest_summary_statement",
    "vest_detailed_statement_transformed",
    "indmoney_deposits_bank_statement",
    "indmoney_deposits_indmoney_statement",
    "indmoney_usd_to_inr_deposit_exch_rate",
}


class TableRepository:
    """repository for table-level write preparation."""

    def __init__(
            self, 
            write_engine: Engine,
    ):
        self._write_engine = write_engine

    def prepare_table_for_full_load(
        self,
        table_name: str,
        backup_before_truncate: bool = False,
    ) -> None:
        """Prepare a table for a full load once per process."""
        self._validate_table_name(table_name)

        if table_name in _PREPARED_TABLES_FOR_FULL_LOAD:
            logger.info(
                "Skipping table preparation because it already ran in this process | table=%s",
                table_name,
            )
            return

        with self._write_engine.begin() as conn:
            exists = conn.execute(
                text("SELECT to_regclass(:table_name)"),
                {"table_name": table_name},
            ).scalar()

            if not exists:
                logger.warning(
                    "Table not found, skipping pre-load truncate: %s",
                    table_name,
                )
            else:
                if backup_before_truncate:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_table = f"{table_name}__bkp_{timestamp}"
                    conn.execute(
                        text(
                            f'CREATE TABLE "{backup_table}" AS TABLE "{table_name}"'
                        )
                    )
                    logger.info("Created backup table: %s", backup_table)

                conn.execute(text(f'TRUNCATE TABLE "{table_name}"'))
                
                logger.info("Truncated destination table: %s", table_name)

        _PREPARED_TABLES_FOR_FULL_LOAD.add(table_name)

    @staticmethod
    def _validate_table_name(
        table_name: str,
    ) -> None:
        """Validate structural SQL input before using string interpolation."""
        if table_name not in _ALLOWED_FULL_LOAD_TABLES:
            raise ValueError(
                "Invalid table name for full-load preparation: %s" % table_name
            )
