from typing import Final
from decimal import Decimal

import pandas as pd
from pandas.api.types import (
    is_datetime64_any_dtype, 
    is_numeric_dtype,
    is_string_dtype,
    is_bool_dtype,
)

from src.common.logging import logger

#==========================
# Constants (schema safety)
# These variables are intended to be a constant and must not be reassigned.
# =========================
MUST_HAVE_COLUMNS_INDMONEY_EXCHANGE_RATE_TRANSFORMER: Final = {
    "deposit_date",
    "exchange_rate_1_usd_to_inr",
    "usd_deposit",
    "inr_deposit",
}

MUST_HAVE_NUMERIC_COLUMNS_INDMONEY_EXCHANGE_RATE_TRANSFORMER: Final = (
    "exchange_rate_1_usd_to_inr",
    "usd_deposit",
    "inr_deposit",
)

MUST_HAVE_COLUMNS_INDMONEY_RAW_TRANSACTION_TRANSFORMER: Final = {
    "trade_date", "entry_type", "activity", "symbol", "description",
    "quantity", "price", "amount", "commission",
}
MUST_HAVE_STRING_COLUMNS_INDMONEY_RAW_TRANSACTION_TRANSFORMER: Final = (
    "entry_type", "activity", "symbol", "description",
)
MUST_HAVE_NUMERIC_COLUMNS_INDMONEY_RAW_TRANSACTION_TRANSFORMER: Final = (
    "quantity", "price", "amount", "commission",
)

MUST_HAVE_COLUMNS_INDMONEY_TRANSFORMED_TRANSACTION: Final = {
    "trade_date",
    "entry_type",
    "activity",
    "symbol",
    "description",
    "quantity",
    "price",
    "amount",
    "commission",
    "free_flag",
    "crossover_flag",
    "buy_exch_rate",
    "inr_amount",
}

MUST_HAVE_STRING_COLUMNS_INDMONEY_TRANSFORMED_TRANSACTION: Final = (
    "entry_type",
    "activity",
    "symbol",
    "description",
)

MUST_HAVE_NUMERIC_COLUMNS_INDMONEY_TRANSFORMED_TRANSACTION: Final = (
    "quantity",
    "price",
    "amount",
    "commission",
    "buy_exch_rate",
    "inr_amount",
)

MUST_HAVE_BOOL_COLUMNS_INDMONEY_TRANSFORMED_TRANSACTION: Final = (
    "free_flag",
    "crossover_flag",
)

def validate_indmoney_investment_exchange_rate_df(
        df: pd.DataFrame
) -> None:
    """
    Validate transformed indmoney investment exchange-rate dataframe schema and dtypes.
    """
    if not df.empty:
        missing_cols = MUST_HAVE_COLUMNS_INDMONEY_EXCHANGE_RATE_TRANSFORMER - set(df.columns)
        
        if missing_cols:
            logger.error("Missing required columns in transformed dataframe: %s", missing_cols)
            raise ValueError(f"Missing required columns: {missing_cols}")

        if not is_datetime64_any_dtype(df["deposit_date"]):
            raise ValueError("Column 'deposit_date' must be datetime dtype")

        for col in MUST_HAVE_NUMERIC_COLUMNS_INDMONEY_EXCHANGE_RATE_TRANSFORMER:
            if not is_numeric_dtype(df[col]):
                raise ValueError(f"Column '{col}' must be numeric dtype")
        

def validate_indmoney_raw_transactions_df(df: pd.DataFrame) -> None:
    """
    Validate the transformed indmoney raw transaction dataframe before postgres persistence

    Parameters
    ----------
    df: pd.DataFrame
        Output dataframe from transform_indmoney_raw_transactions

    Returns
    -------
    None
        Raises ValueError if any validation check fails
    """
    if df.empty:
        logger.warning("Transformed indmoney raw transaction dataframe is empty")
        return

    missing_cols = MUST_HAVE_COLUMNS_INDMONEY_RAW_TRANSACTION_TRANSFORMER - set(df.columns)
    if missing_cols:
        logger.error("Missing required columns in transformed raw transaction dataframe: %s", missing_cols)
        raise ValueError(f"Missing required columns: {missing_cols}")

    if not is_datetime64_any_dtype(df["trade_date"]):
        raise ValueError("Column 'trade_date' must be datetime dtype")

    for col in MUST_HAVE_STRING_COLUMNS_INDMONEY_RAW_TRANSACTION_TRANSFORMER:
        if not is_string_dtype(df[col]):
            raise ValueError(f"Column '{col}' must be string dtype")

    for col in MUST_HAVE_NUMERIC_COLUMNS_INDMONEY_RAW_TRANSACTION_TRANSFORMER:
        if not is_numeric_dtype(df[col]):
            raise ValueError(f"Column '{col}' must be numeric dtype")
        
        
def _compute_indmoney_segment_sums(
    df: pd.DataFrame,
    month_end_balance_df: pd.DataFrame,
    exch_rate: list[float],
    flag_col: str,
    value_col: str,
) -> list[int]:
    """Compute sums of value_col for each segment defined by True values in flag_col."""
    crossover_positions = df.index.get_indexer(df.index[df[flag_col]])

    segment_starts = [0] + list(crossover_positions)
    segment_ends = list(crossover_positions) + [len(df)]

    segment_sums = [
        df.iloc[start:end][value_col].sum()
        for start, end in zip(segment_starts, segment_ends)
    ]

    segment_sums = [int(Decimal(str(x))) for x in segment_sums]

    if not month_end_balance_df.empty and month_end_balance_df.loc[0, "balance"] > 0 and exch_rate:
        balance = month_end_balance_df.loc[0, "balance"]
        rate = exch_rate[-1]
        segment_sums[-1] = segment_sums[-1] + int(Decimal(str(balance)) * Decimal(str(rate)))

    return segment_sums


def validate_indmoney_month_end_and_transformed_transactions(
    month_end_balance_df: pd.DataFrame,
    transformed_transaction_df: pd.DataFrame,
    prev_month_end_indmoney_balance_df: pd.DataFrame,
    curr_month_usd_deposits_df: pd.DataFrame,
    credit_amounts_exchg_rate_df: pd.DataFrame,
    tolerance: int = 2,
) -> None:
    """Validate transformed indmoney transactions and reconciliation logic for month-end pipeline."""
    if transformed_transaction_df.empty:
        return

    missing_cols = MUST_HAVE_COLUMNS_INDMONEY_TRANSFORMED_TRANSACTION - set(transformed_transaction_df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    for col in MUST_HAVE_STRING_COLUMNS_INDMONEY_TRANSFORMED_TRANSACTION:
        if not is_string_dtype(transformed_transaction_df[col]):
            raise ValueError(f"Column '{col}' must be string dtype")

    for col in MUST_HAVE_NUMERIC_COLUMNS_INDMONEY_TRANSFORMED_TRANSACTION:
        if not is_numeric_dtype(transformed_transaction_df[col]):
            raise ValueError(f"Column '{col}' must be numeric dtype")

    for col in MUST_HAVE_BOOL_COLUMNS_INDMONEY_TRANSFORMED_TRANSACTION:
        if not is_bool_dtype(transformed_transaction_df[col]):
            raise ValueError(f"Column '{col}' must be bool dtype")

    if transformed_transaction_df.loc[transformed_transaction_df["free_flag"], "inr_amount"].sum() != 0:
        raise ValueError("Sum of inr_amount for free_flag=True must be 0")

    exch_rate = credit_amounts_exchg_rate_df["exchange_rate_1_usd_to_inr"].tolist()
    expected_crossover_count = max(len(exch_rate) - 1, 0)
    actual_crossover_count = int(transformed_transaction_df["crossover_flag"].sum())

    if actual_crossover_count != expected_crossover_count:
        raise ValueError(
            "Invalid crossover flag count: "
            f"expected {expected_crossover_count}, got {actual_crossover_count}"
        )

    if not prev_month_end_indmoney_balance_df.empty and not credit_amounts_exchg_rate_df.empty:

        credit_amounts = []

        balance = prev_month_end_indmoney_balance_df["balance"].iloc[0]
        if balance > 0:
            credit_amounts.append(balance)

        credit_amounts.extend(curr_month_usd_deposits_df["usd_deposit"].tolist())

        expected_inr_amounts = [
            round(amount * rate, 2)
            for amount, rate in zip(credit_amounts, exch_rate)
        ]

        segment_sums = _compute_indmoney_segment_sums(
            transformed_transaction_df,
            month_end_balance_df,
            exch_rate,
            flag_col="crossover_flag",
            value_col="inr_amount",
        )

        expected = [int(Decimal(str(x))) for x in expected_inr_amounts]

        if len(segment_sums) != len(expected):
            raise ValueError(
                f"Reconciliation segment length mismatch: actual {len(segment_sums)}, expected {len(expected)}"
            )

        if not all(abs(actual - exp) <= tolerance for actual, exp in zip(segment_sums, expected)):
            raise ValueError(
                "Segmented INR amount reconciliation failed. "
                f"actual={segment_sums}, expected={expected}, tolerance={tolerance}"
            )