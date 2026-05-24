import pandas as pd

from src.common.logging import logger
from src.common.db import get_write_engine
from src.common.db import get_read_engine

from src.parsers.pdf.indmoney_statement_period import extract_indmoney_statement_period
from src.parsers.pdf.indmoney_statement_transactions import extract_indmoney_detailed_transactions
from src.transformers.indmoney.indmoney_raw_transactions_transformer import transform_indmoney_raw_transactions
from src.transformers.indmoney.indmoney_transactions_transformer import transform_indmoney_transactions
from src.loaders.postgres.indmoney.indmoney_month_end_balance_loader import load_indmoney_month_end_balance
from src.loaders.postgres.indmoney.indmoney_statement_transformed_transaction_loader import load_indmoney_transformed_transactions

from src.pipelines.indmoney.validations import validate_indmoney_month_end_and_transformed_transactions

from src.pipelines.execution_mode import LoadExecutionMode
from src.repositories.indmoney_reference_repository import IndmoneyReferenceRepository

from src.pipelines.helper import _derive_vest_statement_dates

from src.transformers.helper import (
    MONTH_END_BLALANCE_POSTGRES_TABLE_COLUMN_NAMES,
)


def run(
        pdf_path: str,
        dry_run: bool = False,
        load_mode: LoadExecutionMode = LoadExecutionMode.LOAD_ALL,
        run_mode: str = "delta",
        backup_before_truncate: bool = False,
) -> None:
    """
    Runs the indmoney statement pdf → compute month_end_indmoney_balance → postgres pipeline.

    Parameters
    ----------
    pdf_path : str
        Path to indmoney statement PDF
    dry_run : bool
        If True, executes full pipeline except postgres write
    load_mode: LoadExecutionMode
        Flag controlling whether to load month_end_balance, transformed_transactions, or both
    run_mode : str
        "delta" appends rows. "full" enables one-time pre-load truncate.
    backup_before_truncate : bool
        Whether to create a timestamped backup table before truncate in full mode.
    """

    if load_mode == LoadExecutionMode.LOAD_ALL:
        logger.info("Starting indmoney transactions and month end balance pipeline")
    elif load_mode == LoadExecutionMode.LOAD_MONTH_END_ONLY:
        logger.info("Starting indmoney month end balance pipeline")
    else:
        logger.info("Starting indmoney transactions pipeline")

    month_year = extract_indmoney_statement_period(pdf_path)

    indmoney_raw_transactions_parsed_df = extract_indmoney_detailed_transactions(pdf_path, month_year)

    indmoney_raw_transaction_df = transform_indmoney_raw_transactions(indmoney_raw_transactions_parsed_df)

    (
        current_statement_month_first_date,
        current_statement_month_last_date,
        current_statement_previous_month_first_date,
        current_statement_previous_month_last_date,
    ) = _derive_vest_statement_dates(month_year)

    #=============================================================================================
    # Fetch supporting data from postgres tables required to feed the transformer
    #=============================================================================================
    read_engine = get_read_engine()

    indmoney_reference_repository = IndmoneyReferenceRepository(read_engine)

    prev_month_end_indmoney_balance_df = indmoney_reference_repository.fetch_prev_month_end_balance(
        current_statement_previous_month_last_date,
    )

    if prev_month_end_indmoney_balance_df.empty:
        logger.warning(
            "No previous month-end balance found for Date = %s. "
            "Defaulting to 0.0 (bootstrap: first statement ever).",
            current_statement_previous_month_last_date,
        )
        prev_month_end_indmoney_balance_df = pd.DataFrame({"balance": [0.0]})

    if len(prev_month_end_indmoney_balance_df) > 1:
        logger.error(
            "There should be only one record for period %s in 'indmoney_month_end_balance'",
            current_statement_previous_month_last_date,
        )
        raise ValueError(
            "There should be only one record for period %s in the 'indmoney_month_end_balance' postgres table",
            current_statement_previous_month_last_date,
        )

    logger.info(
        "Fetching current month indmoney USD deposits from 'indmoney_usd_to_inr_deposit_exch_rate'"
    )

    curr_month_usd_deposits_df = indmoney_reference_repository.fetch_curr_month_usd_deposits(
        current_statement_month_first_date,
        current_statement_month_last_date,
    )

    if curr_month_usd_deposits_df.empty:
        logger.warning(
            "No USD deposits found in 'indmoney_usd_to_inr_deposit_exch_rate' | period = %s to %s",
            current_statement_month_first_date,
            current_statement_month_last_date,
        )

    #-------------------------------------------------------------------------------------
    # Fetch exchange rates conditionally based on whether prev month balance is positive
    #-------------------------------------------------------------------------------------
    if prev_month_end_indmoney_balance_df.loc[0, "balance"] > 0:
        logger.info(
            "Fetching combined current and previous month exchange rates from "
            "'indmoney_usd_to_inr_deposit_exch_rate'"
        )

        credit_amounts_exchg_rate_df = indmoney_reference_repository.fetch_curr_and_prev_exchange_rates(
            current_statement_previous_month_first_date,
            current_statement_previous_month_last_date,
            current_statement_month_first_date,
            current_statement_month_last_date,
        )

        if credit_amounts_exchg_rate_df.empty:
            logger.error(
                "No exchange rates found in 'indmoney_usd_to_inr_deposit_exch_rate' | "
                "period = %s to %s and period = %s to %s",
                current_statement_month_first_date,
                current_statement_month_last_date,
                current_statement_previous_month_first_date,
                current_statement_previous_month_last_date,
            )
            raise ValueError(
                "Investigate why no exchange rate found in 'indmoney_usd_to_inr_deposit_exch_rate' "
                "even though there is a positive month end balance for previous period. "
                "Current period is %s",
                month_year,
            )

    elif not curr_month_usd_deposits_df.empty:
        logger.info(
            "Fetching current month exchange rates from 'indmoney_usd_to_inr_deposit_exch_rate'"
        )

        credit_amounts_exchg_rate_df = indmoney_reference_repository.fetch_curr_month_exchange_rates(
            current_statement_month_first_date,
            current_statement_month_last_date,
        )

        if credit_amounts_exchg_rate_df.empty:
            logger.error(
                "No exchange rates found in 'indmoney_usd_to_inr_deposit_exch_rate' | "
                "period = %s to %s",
                current_statement_month_first_date,
                current_statement_month_last_date,
            )
            raise ValueError(
                "Investigate why no exchange rate found in 'indmoney_usd_to_inr_deposit_exch_rate' "
                "even though there is a USD deposit for current period (%s)",
                month_year,
            )

    else:
        credit_amounts_exchg_rate_df = pd.DataFrame()

    #=====================End of fetching dfs from postgres=====================

    #------------------------------------------------------------
    # Run transformer to get both output dfs
    #------------------------------------------------------------
    (
        indmoney_month_end_balance_df,
        indmoney_transactions_transformed_df,
    ) = transform_indmoney_transactions(
        indmoney_raw_transaction_df,
        prev_month_end_indmoney_balance_df,
        curr_month_usd_deposits_df,
        credit_amounts_exchg_rate_df,
        current_statement_month_last_date,
        month_year,
    )

    validate_indmoney_month_end_and_transformed_transactions(
        indmoney_month_end_balance_df,
        indmoney_transactions_transformed_df,
        prev_month_end_indmoney_balance_df,
        curr_month_usd_deposits_df,
        credit_amounts_exchg_rate_df,
    )

    #-----------------------------------------------------------
    # Load to postgres
    #-----------------------------------------------------------
    if load_mode in (
        LoadExecutionMode.LOAD_ALL,
        LoadExecutionMode.LOAD_MONTH_END_ONLY
    ):
        load_indmoney_month_end_balance(
            indmoney_month_end_balance_df,
            get_write_engine,
            dry_run,
            run_mode,
            backup_before_truncate,
        )

        logger.info(
            "Indmoney month end balance pipeline finished successfully | Period: %s",
            month_year,
        )

    if load_mode in (
        LoadExecutionMode.LOAD_ALL,
        LoadExecutionMode.LOAD_TRANSFORMED_TRATRANSACTIONS_ONLY
    ):
        load_indmoney_transformed_transactions(
            indmoney_transactions_transformed_df,
            get_write_engine,
            dry_run,
            run_mode,
            backup_before_truncate,
        )

        logger.info(
            "Indmoney transformed transaction pipeline finished successfully | Period: %s",
            month_year,
        )
