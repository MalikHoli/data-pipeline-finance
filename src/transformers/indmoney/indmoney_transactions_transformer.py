import pandas as pd

from src.common.logging import logger

from src.transformers.helper import (
    _allocate_wallet_amount_to_transactions,
    _assign_buy_exchange_rates_with_inr_amount,
    _clean_convert_currency_column_to_numeric,
    _convert_vest_month_end_date_for_postgres_posting,
    MONTH_END_BLALANCE_POSTGRES_TABLE_COLUMN_NAMES,
    INDMONEY_STATEMENT_TRANSACTIONS_TRANSFORMER_CONVERT_TO_NUMERIC,
    INDMONEY_MONTH_END_BALANCE_CONVERT_TO_POSTGRES_DATE,
    INDMONEY_MONTH_END_BALANCE_CONVERT_TO_NUMERIC,
)


def transform_indmoney_transactions(
        indmoney_raw_transaction_df: pd.DataFrame,
        prev_month_end_indmoney_balance_df: pd.DataFrame,
        curr_month_usd_deposits_df: pd.DataFrame,
        credit_amounts_exchg_rate_df: pd.DataFrame,
        current_statement_month_last_date: str,
        month_year: str,
) -> tuple[
            pd.DataFrame,
            pd.DataFrame,
    ]:
    """
    Transform raw indmoney transactions into schema that calculates invested amount in INR.

    Parameters
    ----------
    indmoney_raw_transaction_df: pd.DataFrame
        Output dataframe from transform_indmoney_raw_transactions (all activities)
    prev_month_end_indmoney_balance_df: pd.DataFrame
        Output dataframe from querying indmoney_month_end_balance for the previous month
    curr_month_usd_deposits_df: pd.DataFrame
        Output dataframe from querying indmoney_usd_to_inr_deposit_exch_rate for current month USD deposits
    credit_amounts_exchg_rate_df: pd.DataFrame
        Output dataframe from querying indmoney_usd_to_inr_deposit_exch_rate for exchange rates
    current_statement_month_last_date: str
        Last date of the statement month (YYYY-MM-DD)
    month_year: str
        The period for which this indmoney statement was generated (MM/YYYY)

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        - indmoney_month_end_balance_df: month end balance ready for persistence
        - indmoney_transactions_transformed_df: transformed buy transactions ready for persistence
    """
    if not month_year:
        logger.error("Failed to get the period information in the transformer")
        raise ValueError("month_year must be provided in MM/YYYY format")

    # ----------------------------------
    # Filter to buy transactions only
    # ----------------------------------
    indmoney_buy_transactions_df = (
        indmoney_raw_transaction_df[
            indmoney_raw_transaction_df["activity"].isin(["buy"])
        ]
        .copy()
        .reset_index(drop=True)
    )

    if indmoney_buy_transactions_df.empty:
        logger.warning(
            "There were no buy transactions in indmoney statement for period %s",
            month_year,
        )

        indmoney_month_end_balance_df = pd.DataFrame(
            [
                [
                    current_statement_month_last_date,
                    prev_month_end_indmoney_balance_df.loc[0, "balance"],
                ]
            ],
            columns=MONTH_END_BLALANCE_POSTGRES_TABLE_COLUMN_NAMES,
        )

        indmoney_month_end_balance_df[INDMONEY_MONTH_END_BALANCE_CONVERT_TO_POSTGRES_DATE] = (
            indmoney_month_end_balance_df[INDMONEY_MONTH_END_BALANCE_CONVERT_TO_POSTGRES_DATE]
            .apply(_convert_vest_month_end_date_for_postgres_posting)
        )

        indmoney_month_end_balance_df[INDMONEY_MONTH_END_BALANCE_CONVERT_TO_NUMERIC] = (
            indmoney_month_end_balance_df[INDMONEY_MONTH_END_BALANCE_CONVERT_TO_NUMERIC]
            .apply(_clean_convert_currency_column_to_numeric)
        )

        return (
            indmoney_month_end_balance_df,
            pd.DataFrame(),
        )

    # =========================
    # Build credit amounts list
    # =========================
    indmoney_credit_amount_list = []
    indmoney_credit_exchg_rate_list = []

    if prev_month_end_indmoney_balance_df.loc[0, "balance"] > 0:
        indmoney_credit_amount_list.extend(prev_month_end_indmoney_balance_df["balance"].tolist())

    indmoney_credit_amount_list.extend(curr_month_usd_deposits_df["usd_deposit"].tolist())

    indmoney_credit_exchg_rate_list.extend(
        credit_amounts_exchg_rate_df["exchange_rate_1_usd_to_inr"].tolist()
    )

    # ---------------------------------------------------------------
    # Checkpoint: credit amounts must align 1:1 with exchange rates
    # ---------------------------------------------------------------
    if len(indmoney_credit_amount_list) != len(indmoney_credit_exchg_rate_list):
        logger.error(
            "Expected %d exchange rates, but got %d. "
            "This mismatch suggests inconsistent data mapping between credit amounts and exchange rates.",
            len(indmoney_credit_amount_list),
            len(indmoney_credit_exchg_rate_list),
        )
        raise ValueError(
            "Something is wrong: ambiguity in finding the exchange rate for the credit amounts."
        )
    else:
        logger.info(
            "Length of indmoney credit amount list matches exchange rate list: %d",
            len(indmoney_credit_amount_list),
        )

    if (indmoney_buy_transactions_df["amount"] < 0).any():
        logger.warning(
            "Negative buy amount detected in indmoney statement | Period = %s",
            month_year,
        )

    # ---------------------------------------------------------------
    # Pre-initialise flag columns to avoid NaN in downstream steps
    # ---------------------------------------------------------------
    indmoney_buy_transactions_df["free_flag"] = False
    indmoney_buy_transactions_df["crossover_flag"] = False

    # ------------------------------------------
    # Apply credit allocation + exchange rates
    # ------------------------------------------
    indmoney_credit_allocated_df, remaining_balance = _allocate_wallet_amount_to_transactions(
        indmoney_credit_amount_list,
        indmoney_buy_transactions_df,
        amount_col="amount",
    )

    indmoney_transactions_transformed_df = _assign_buy_exchange_rates_with_inr_amount(
        indmoney_credit_allocated_df,
        indmoney_credit_exchg_rate_list,
        amount_col="amount",
    )

    # ------------------------------------------
    # Format newly created numeric columns
    # ------------------------------------------
    logger.info("Cleaning and formatting newly created columns as per postgres schema")

    indmoney_transactions_transformed_df[INDMONEY_STATEMENT_TRANSACTIONS_TRANSFORMER_CONVERT_TO_NUMERIC] = (
        indmoney_transactions_transformed_df[INDMONEY_STATEMENT_TRANSACTIONS_TRANSFORMER_CONVERT_TO_NUMERIC]
        .apply(_clean_convert_currency_column_to_numeric)
        .astype(float)
    )

    logger.info(
        "Indmoney transaction table transformed | rows=%d",
        len(indmoney_transactions_transformed_df),
    )

    # ------------------------------------------
    # Build month end balance df
    # ------------------------------------------
    indmoney_month_end_balance_df = pd.DataFrame(
        [
            [
                current_statement_month_last_date,
                remaining_balance,
            ]
        ],
        columns=MONTH_END_BLALANCE_POSTGRES_TABLE_COLUMN_NAMES,
    )

    indmoney_month_end_balance_df[INDMONEY_MONTH_END_BALANCE_CONVERT_TO_POSTGRES_DATE] = (
        indmoney_month_end_balance_df[INDMONEY_MONTH_END_BALANCE_CONVERT_TO_POSTGRES_DATE]
        .apply(_convert_vest_month_end_date_for_postgres_posting)
    )

    indmoney_month_end_balance_df[INDMONEY_MONTH_END_BALANCE_CONVERT_TO_NUMERIC] = (
        indmoney_month_end_balance_df[INDMONEY_MONTH_END_BALANCE_CONVERT_TO_NUMERIC]
        .apply(_clean_convert_currency_column_to_numeric)
    )

    logger.info(
        "Indmoney month end balance df prepared | rows=%d",
        len(indmoney_month_end_balance_df),
    )

    return indmoney_month_end_balance_df, indmoney_transactions_transformed_df
