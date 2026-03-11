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
MUST_HAVE_COLUMNS_VEST_EXCHANGE_RATE_TRANSFORMER: Final = {
    "deposit_date",
    "exchange_rate_1_usd_to_inr",
    "usd_deposit",
    "inr_deposit",
}

MUST_HAVE_NUMERIC_COLUMNS_VEST_EXCHANGE_RATE_TRANSFORMER: Final = (
    "exchange_rate_1_usd_to_inr",
    "usd_deposit",
    "inr_deposit",
)

MUST_HAVE_COLUMNS_VEST_RAW_TRANSACTION_TRANSFORMER: Final = {
    "trade_date",
    "activity",
    "symbol",
    "description",
    "quantity",
    "price",
    "amount",
}

MUST_HAVE_STRING_COLUMNS_VEST_RAW_TRANSACTION_TRANSFORMER: Final = (
    "activity",
    "symbol",
    "description",
)

MUST_HAVE_NUMERIC_COLUMNS_VEST_RAW_TRANSACTION_TRANSFORMER: Final = (
    "quantity",
    "price",
    "amount",
)

MUST_HAVE_COLUMNS_VEST_HOLDING_TRANSFORMER: Final = {
    "symbol",
    "quantity",
    "unit_cost",
    "total_cost",
    "market_price",
    "market_value",
    "gain",
    "date",
    "exch_rate",
}

MUST_HAVE_STRING_COLUMNS_VEST_HOLDING_TRANSFORMER: Final = (
    "symbol",
)

MUST_HAVE_NUMERIC_COLUMNS_VEST_HOLDING_TRANSFORMER: Final = (
    "quantity",
    "unit_cost",
    "total_cost",
    "market_price",
    "market_value",
    "gain",
    "exch_rate",
)

MUST_HAVE_COLUMNS_VEST_TRANSFORMED_TRANSACTION: Final = {
    "activity",
    "symbol",
    "description",
    "quantity",
    "price",
    "amount",
    "free_flag",
    "crossover_flag",
    "buy_exch_rate",
    "inr_amount",
}

MUST_HAVE_STRING_COLUMNS_VEST_TRANSFORMED_TRANSACTION: Final = (
    "activity",
    "symbol",
    "description",
)

MUST_HAVE_NUMERIC_COLUMNS_VEST_TRANSFORMED_TRANSACTION: Final = (
    "quantity",
    "price",
    "amount",
    "buy_exch_rate",
    "inr_amount",
)

MUST_HAVE_BOOL_COLUMNS_VEST_TRANSFORMED_TRANSACTION: Final = (
    "free_flag",
    "crossover_flag",
)

def validate_vest_investment_exchange_rate_df(
        df: pd.DataFrame
) -> None:
    """
    Validate transformed vest investment exchange-rate dataframe schema and dtypes.
    """
    if not df.empty:
        missing_cols = MUST_HAVE_COLUMNS_VEST_EXCHANGE_RATE_TRANSFORMER - set(df.columns)
        
        if missing_cols:
            logger.error("Missing required columns in transformed dataframe: %s", missing_cols)
            raise ValueError(f"Missing required columns: {missing_cols}")

        if not is_datetime64_any_dtype(df["deposit_date"]):
            raise ValueError("Column 'deposit_date' must be datetime dtype")

        for col in MUST_HAVE_NUMERIC_COLUMNS_VEST_EXCHANGE_RATE_TRANSFORMER:
            if not is_numeric_dtype(df[col]):
                raise ValueError(f"Column '{col}' must be numeric dtype")
        

def validate_vest_raw_transactions_df(
        df: pd.DataFrame
) -> None:
    """Validate transformed vest raw-transactions dataframe schema and dtypes."""
    if df.empty:
        logger.error("Transformed vest raw transaction dataframe is empty")
        raise ValueError("Transformed vest raw transaction dataframe is empty")

    missing_cols = MUST_HAVE_COLUMNS_VEST_RAW_TRANSACTION_TRANSFORMER - set(df.columns)
    if missing_cols:
        logger.error("Missing required columns in transformed raw transaction dataframe: %s", missing_cols)
        raise ValueError(f"Missing required columns: {missing_cols}")

    if not is_datetime64_any_dtype(df["trade_date"]):
        raise ValueError("Column 'trade_date' must be datetime dtype")

    for col in MUST_HAVE_STRING_COLUMNS_VEST_RAW_TRANSACTION_TRANSFORMER:
        if not is_string_dtype(df[col]):
            raise ValueError(f"Column '{col}' must be string dtype")

    for col in MUST_HAVE_NUMERIC_COLUMNS_VEST_RAW_TRANSACTION_TRANSFORMER:
        if not is_numeric_dtype(df[col]):
            raise ValueError(f"Column '{col}' must be numeric dtype")
        
def validate_vest_holdings_df(
        df: pd.DataFrame
) -> None:
    """Validate transformed vest holdings dataframe schema, quality, and dtypes."""
    if df.empty:
        logger.error("Transformed vest holdings dataframe is empty")
        raise ValueError("Transformed vest holdings dataframe is empty")

    missing_cols = MUST_HAVE_COLUMNS_VEST_HOLDING_TRANSFORMER - set(df.columns)
    if missing_cols:
        logger.error("Missing required columns in transformed holdings dataframe: %s", missing_cols)
        raise ValueError(f"Missing required columns: {missing_cols}")

    if not df.notna().all().all():
        logger.error("Transformed vest holdings dataframe contains NA values")
        raise ValueError("Transformed vest holdings dataframe contains NA values")

    gain_parentheses_mask = df["gain"].astype(str).str.contains(r"[()]", regex=True)
    if gain_parentheses_mask.any():
        invalid_gain_values = df.loc[gain_parentheses_mask, "gain"]
        raise ValueError(
            "Invalid gain values found containing parentheses:\n"
            f"{invalid_gain_values}"
        )

    if not is_datetime64_any_dtype(df["date"]):
        raise ValueError("Column 'date' must be datetime dtype")

    for col in MUST_HAVE_STRING_COLUMNS_VEST_HOLDING_TRANSFORMER:
        if not is_string_dtype(df[col]):
            raise ValueError(f"Column '{col}' must be string dtype")

    for col in MUST_HAVE_NUMERIC_COLUMNS_VEST_HOLDING_TRANSFORMER:
        if not is_numeric_dtype(df[col]):
            raise ValueError(f"Column '{col}' must be numeric dtype")

def _compute_segment_sums(
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
        segment_sums[-1] = segment_sums[-1] + int(balance * Decimal(str(rate)))

    return segment_sums


def validate_vest_month_end_and_transformed_transactions(
    month_end_balance_df: pd.DataFrame,
    transformed_transaction_df: pd.DataFrame,
    prev_month_end_vest_wallet_balance_df: pd.DataFrame,
    curr_month_vest_wallet_credit_df: pd.DataFrame,
    credit_amounts_exchg_rate_df: pd.DataFrame,
    tolerance: int = 2,
) -> None:
    """Validate transformed vest transactions and reconciliation logic for month-end pipeline."""
    if transformed_transaction_df.empty:
        return

    missing_cols = MUST_HAVE_COLUMNS_VEST_TRANSFORMED_TRANSACTION - set(transformed_transaction_df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    for col in MUST_HAVE_STRING_COLUMNS_VEST_TRANSFORMED_TRANSACTION:
        if not is_string_dtype(transformed_transaction_df[col]):
            raise ValueError(f"Column '{col}' must be string dtype")

    for col in MUST_HAVE_NUMERIC_COLUMNS_VEST_TRANSFORMED_TRANSACTION:
        if not is_numeric_dtype(transformed_transaction_df[col]):
            raise ValueError(f"Column '{col}' must be numeric dtype")

    for col in MUST_HAVE_BOOL_COLUMNS_VEST_TRANSFORMED_TRANSACTION:
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

    if not prev_month_end_vest_wallet_balance_df.empty and not credit_amounts_exchg_rate_df.empty:
    
        wallet_balance = []

        balance = prev_month_end_vest_wallet_balance_df["balance"].iloc[0]

        if balance > 0:
            wallet_balance.append(balance)

        wallet_balance.extend(curr_month_vest_wallet_credit_df["amount"].tolist())

        expected_inr_amounts = [
            round(balance * rate, 2)
            for balance, rate in zip(wallet_balance, exch_rate)
        ]

        segment_sums = _compute_segment_sums(
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