import pandas as pd

from src.common.logging import logger
from src.common.db import get_write_engine
from src.pipelines.execution_mode import LoadExecutionMode
from src.pipelines.helper import _derive_vest_statement_dates

from src.parsers.pdf.indmoney_statement_period import extract_indmoney_statement_period
from src.parsers.pdf.indmoney_statement_transactions import extract_indmoney_detailed_transactions
from src.transformers.indmoney.indmoney_raw_transactions_transformer import transform_indmoney_raw_transactions
from src.transformers.indmoney.indmoney_transactions_transformer import transform_indmoney_transactions
from src.loaders.postgres.indmoney.indmoney_month_end_balance_loader import load_indmoney_month_end_balance
from src.loaders.postgres.indmoney.indmoney_statement_transformed_transaction_loader import load_indmoney_transformed_transactions


def run(pdf_path: str, dry_run: bool = False, load_mode: LoadExecutionMode = LoadExecutionMode.LOAD_ALL) -> None:
    if load_mode == LoadExecutionMode.LOAD_ALL:
        logger.info("Starting indmoney transactions and month end balance pipeline")
    elif load_mode == LoadExecutionMode.LOAD_MONTH_END_ONLY:
        logger.info("Starting indmoney month end balance pipeline")
    else:
        logger.info("Starting indmoney transformed transactions pipeline")

    month_year = extract_indmoney_statement_period(pdf_path)
    parsed_df = extract_indmoney_detailed_transactions(pdf_path, month_year)
    raw_df = transform_indmoney_raw_transactions(parsed_df)

    if raw_df.empty:
        logger.warning("No indmoney transactions found for %s", month_year)
        return

    (
        current_statement_month_first_date,
        current_statement_month_last_date,
        current_statement_previous_month_first_date,
        current_statement_previous_month_last_date,
    ) = _derive_vest_statement_dates(month_year)

    engine = get_write_engine()

    prev_month_balance_df = pd.read_sql(
        """
        SELECT balance
        FROM indmoney_month_end_balance
        WHERE date=%(last_day_prev_month)s
        """,
        engine,
        params={"last_day_prev_month": current_statement_previous_month_last_date},
    )

    if prev_month_balance_df.empty:
        prev_month_balance_df = pd.DataFrame([[0.0]], columns=["balance"])

    curr_month_wallet_credit_df = pd.read_sql(
        """
        SELECT usd_deposit
        FROM indmoney_usd_to_inr_deposit_exch_rate
        WHERE deposit_date BETWEEN %(start_date)s AND %(end_date)s
        """,
        engine,
        params={"start_date": current_statement_month_first_date, "end_date": current_statement_month_last_date},
    )

    curr_query = """
    SELECT exchange_rate_1_usd_to_inr FROM indmoney_usd_to_inr_deposit_exch_rate
    WHERE deposit_date BETWEEN %(start_date)s AND %(end_date)s
    ORDER BY deposit_date ASC
    """
    curr_and_prev_query = """
    SELECT exchange_rate_1_usd_to_inr
    FROM (
        SELECT deposit_date, exchange_rate_1_usd_to_inr
        FROM indmoney_usd_to_inr_deposit_exch_rate
        WHERE deposit_date BETWEEN %(start_date)s AND %(end_date)s
        UNION ALL
        SELECT deposit_date, exchange_rate_1_usd_to_inr
        FROM (
            SELECT deposit_date, exchange_rate_1_usd_to_inr
            FROM indmoney_usd_to_inr_deposit_exch_rate
            WHERE deposit_date = (
                SELECT COALESCE(
                    (SELECT MAX(deposit_date) FROM indmoney_usd_to_inr_deposit_exch_rate WHERE deposit_date BETWEEN %(prev_month_start_date)s AND %(prev_month_end_date)s),
                    (SELECT MAX(deposit_date) FROM indmoney_usd_to_inr_deposit_exch_rate WHERE deposit_date <= %(prev_month_end_date)s)
                )
            )
            ORDER BY ctid DESC
            LIMIT 1
        ) t
    ) AS combined_rates
    ORDER BY deposit_date ASC
    """

    if prev_month_balance_df.loc[0, "balance"] > 0:
        credit_amounts_exchg_rate_df = pd.read_sql(
            curr_and_prev_query,
            engine,
            params={
                "prev_month_start_date": current_statement_previous_month_first_date,
                "prev_month_end_date": current_statement_previous_month_last_date,
                "start_date": current_statement_month_first_date,
                "end_date": current_statement_month_last_date,
            },
        )
    elif not curr_month_wallet_credit_df.empty:
        credit_amounts_exchg_rate_df = pd.read_sql(
            curr_query,
            engine,
            params={"start_date": current_statement_month_first_date, "end_date": current_statement_month_last_date},
        )
    else:
        credit_amounts_exchg_rate_df = pd.DataFrame(columns=["exchange_rate_1_usd_to_inr"])

    month_end_balance_df, transformed_df = transform_indmoney_transactions(
        raw_df,
        prev_month_balance_df,
        curr_month_wallet_credit_df,
        credit_amounts_exchg_rate_df,
        current_statement_month_last_date,
        month_year,
    )

    if load_mode in (LoadExecutionMode.LOAD_ALL, LoadExecutionMode.LOAD_MONTH_END_ONLY):
        load_indmoney_month_end_balance(month_end_balance_df, get_write_engine, dry_run)

    if load_mode in (LoadExecutionMode.LOAD_ALL, LoadExecutionMode.LOAD_TRANSFORMED_TRATRANSACTIONS_ONLY):
        if transformed_df.empty:
            logger.warning("No transformed indmoney transactions to load for %s", month_year)
        else:
            load_indmoney_transformed_transactions(transformed_df, get_write_engine, dry_run)
