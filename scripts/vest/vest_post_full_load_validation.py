import sys
from pathlib import Path
import pandas as pd
from sqlalchemy.engine import Engine

# Allow `python scripts/...` to import from `src/`
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.logging import logger
from src.common.db import get_read_engine

MAX_ROWS_TO_LOG = 10


def validate_table_no_keys_with_mapping(
    engine: Engine,
    main_table: str,
    backup_table: str,
    column_mapping: dict,
) -> None:
    """
    Compare tables without keys using full row comparison.
    Handles column renaming via mapping.

    column_mapping = {
        "backup_col": "main_col"
    }
    """

    logger.info("Validating %s vs %s with column mapping", main_table, backup_table)

    backup_cols = list(column_mapping.keys())
    main_cols = list(column_mapping.values())

    # Build select with aliasing → normalize column names
    backup_select = ", ".join([f"{col} AS {col}" for col in backup_cols])
    main_select = ", ".join([
        f"{column_mapping[b]} AS {b}" for b in backup_cols
    ])

    join_conditions = " AND ".join([
        f"b.{col} = m.{col}" for col in backup_cols
    ])

    group_cols = ", ".join(backup_cols)

    with engine.connect() as conn:

        # -------------------------------
        # Missing / mismatch rows
        # -------------------------------
        query = f"""
        WITH b AS (
            SELECT {backup_select}, COUNT(*) AS cnt
            FROM {backup_table}
            GROUP BY {group_cols}
        ),
        m AS (
            SELECT {main_select}, COUNT(*) AS cnt
            FROM {main_table}
            GROUP BY {group_cols}
        )
        SELECT 
            b.*,
            COALESCE(m.cnt, 0) AS main_cnt
        FROM b
        LEFT JOIN m
        ON {join_conditions}
        WHERE m.cnt IS NULL OR b.cnt <> m.cnt
        """

        diff_df = pd.read_sql(query, conn)

        if not diff_df.empty:
            logger.warning(
                "Differences found in %s: %d rows. Sample:\n%s",
                main_table,
                len(diff_df),
                diff_df.head(MAX_ROWS_TO_LOG),
            )

        # -------------------------------
        # Extra rows (allowed)
        # -------------------------------
        extra_query = f"""
        WITH b AS (
            SELECT {backup_select}, COUNT(*) AS cnt
            FROM {backup_table}
            GROUP BY {group_cols}
        ),
        m AS (
            SELECT {main_select}, COUNT(*) AS cnt
            FROM {main_table}
            GROUP BY {group_cols}
        )
        SELECT 
            m.*,
            COALESCE(b.cnt, 0) AS backup_cnt
        FROM m
        LEFT JOIN b
        ON {join_conditions}
        WHERE b.cnt IS NULL OR m.cnt > b.cnt
        """

        extra_df = pd.read_sql(extra_query, conn)

        if not extra_df.empty:
            logger.info(
                "Extra rows in %s: %d rows (allowed). Sample:\n%s",
                main_table,
                len(extra_df),
                extra_df.head(MAX_ROWS_TO_LOG),
            )

    logger.info("Validation completed for %s", main_table)

def main() -> None:

    # # vest_detailed_statement validation
    # validate_table_no_keys_with_mapping(
    #     engine=get_read_engine(),
    #     main_table="vest_detailed_statement",
    #     backup_table="vest_detailed_statement__bkp_20260401_204427",
    #     column_mapping={ # useful in case of column name change
    #         "trade_date": "trade_date",
    #         "activity": "activity",
    #         "symbol": "symbol",
    #         "description": "description",
    #         "quantity": "quantity",
    #         "price": "price",
    #         "amount": "amount",
    #     }
    # )

    # # vest_detailed_statement_transformed validation
    # validate_table_no_keys_with_mapping(
    #     engine=get_read_engine(),
    #     main_table="vest_detailed_statement_transformed",
    #     backup_table="vest_detailed_statement_transformed__bkp_20260401_204428",
    #     column_mapping={ # useful in case of column name change
    #         "trade_date": "trade_date",
    #         "activity": "activity",
    #         "symbol": "symbol",
    #         "description": "description",
    #         "quantity": "quantity",
    #         "price": "price",
    #         "amount": "amount",
    #         "crossover_flag":"crossover_flag",
    #         "free_flag":"free_flag",
    #         "buy_exch_rate":"buy_exch_rate",
    #         "inr_amount":"inr_amount",
    #     }
    # )

    # # vest_month_end_balance validation
    # validate_table_no_keys_with_mapping(
    #     engine=get_read_engine(),
    #     main_table="vest_month_end_balance",
    #     backup_table="vest_month_end_balance__bkp_20260401_204428",
    #     column_mapping={ # useful in case of column name change
    #         "date": "date",
    #         "balance": "balance",
    #     }
    # )

    # vest_summary_statement validation
    validate_table_no_keys_with_mapping(
        engine=get_read_engine(),
        main_table="vest_summary_statement",
        backup_table="vest_summary_statement__bkp_20260401_204426",
        column_mapping={ # useful in case of column name change
            "symbol": "symbol",
            "quantity": "quantity",
            "unit_cost":"unit_cost",
            "total_cost":"total_cost",
            "market_price":"market_price",
            "market_value":"market_value",
            "gain":"gain",
            "date": "date",
            "exch_rate": "exch_rate",
        }
    )

    # # vest_usd_to_inr_deposit_exch_rate validation
    # validate_table_no_keys_with_mapping(
    #     engine=get_read_engine(),
    #     main_table="vest_usd_to_inr_deposit_exch_rate",
    #     backup_table="vest_usd_to_inr_deposit_exch_rate__bkp_20260327_224030",
    #     column_mapping={ # useful in case of column name change
    #         "deposit_date": "deposit_date",
    #         "exchange_rate_1_usd_to_inr": "exchange_rate_1_usd_to_inr",
    #         "usd_deposit":"usd_deposit",
    #         "inr_deposit":"inr_deposit",
    #     }
    # )

if __name__ == "__main__":
    main()