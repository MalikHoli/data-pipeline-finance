import pandas as pd

from src.common.logging import logger
from src.transformers.helper import (
    MONTH_END_BLALANCE_POSTGRES_TABLE_COLUMN_NAMES,
    _allocate_wallet_amount_to_transactions,
    _assign_buy_exchange_rates_with_inr_amount,
    _clean_convert_currency_column_to_numeric,
)

TRANSFORMED_NUMERIC_COLUMNS = ["buy_exch_rate", "inr_amount"]


def transform_indmoney_transactions(
    indmoney_raw_transaction_df: pd.DataFrame,
    prev_month_end_balance_df: pd.DataFrame,
    curr_month_wallet_credit_df: pd.DataFrame,
    credit_amounts_exchg_rate_df: pd.DataFrame,
    current_statement_month_last_date: str,
    month_year: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    buy_df = indmoney_raw_transaction_df[
        indmoney_raw_transaction_df["activity"].isin(["buy"])
    ].copy()

    if buy_df.empty:
        logger.warning("No buy transactions found in indmoney for %s", month_year)
        return (
            pd.DataFrame([[current_statement_month_last_date, 0.0]], columns=MONTH_END_BLALANCE_POSTGRES_TABLE_COLUMN_NAMES),
            pd.DataFrame(),
        )

    wallet_amount_list = []
    wallet_rate_list = []

    if not prev_month_end_balance_df.empty and prev_month_end_balance_df.loc[0, "balance"] > 0:
        wallet_amount_list.extend(prev_month_end_balance_df["balance"].tolist())

    wallet_amount_list.extend(curr_month_wallet_credit_df["usd_deposit"].tolist())
    wallet_rate_list.extend(credit_amounts_exchg_rate_df["exchange_rate_1_usd_to_inr"].tolist())

    if len(wallet_amount_list) != len(wallet_rate_list):
        raise ValueError(
            f"Expected {len(wallet_amount_list)} exchange rates, but got {len(wallet_rate_list)}. "
            "This mismatch suggests inconsistent data mapping between indmoney wallet amounts and exchange rates."
        )

    buy_df["free_flag"] = False
    buy_df["crossover_flag"] = False

    wallet_amount_allocated_df, remaining_balance = _allocate_wallet_amount_to_transactions(
        wallet_amount_list,
        buy_df,
        amount_col="amount",
    )

    transformed_df = _assign_buy_exchange_rates_with_inr_amount(
        wallet_amount_allocated_df,
        wallet_rate_list,
        amount_col="amount",
    )

    transformed_df[TRANSFORMED_NUMERIC_COLUMNS] = (
        transformed_df[TRANSFORMED_NUMERIC_COLUMNS]
        .apply(_clean_convert_currency_column_to_numeric)
        .astype(float)
    )

    month_end_balance_df = pd.DataFrame(
        [[current_statement_month_last_date, remaining_balance]],
        columns=MONTH_END_BLALANCE_POSTGRES_TABLE_COLUMN_NAMES,
    )

    logger.info("Transformed indmoney buy transactions rows=%d", len(transformed_df))
    return month_end_balance_df, transformed_df
