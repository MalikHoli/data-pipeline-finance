import pandas as pd

from src.common.logging import logger
from src.common.db import get_write_engine
from src.common.db import get_read_engine

from src.parsers.pdf.vest_statement_period import extract_vest_statement_period
from src.parsers.pdf.vest_statement_transactions import extract_vest_detailed_transactions
from src.transformers.vest.vest_raw_transactions_transformer import transform_vest_raw_transactions
from src.transformers.vest.vest_transactions_transformer import transform_vest_transactions
from src.loaders.postgres.vest.vest_month_end_balance_loader import load_vest_month_end_balance
from src.loaders.postgres.vest.vest_statement_transformed_transaction_loader import load_vest_transformed_transactions

from src.pipelines.vest.validations import validate_vest_month_end_and_transformed_transactions

from src.pipelines.execution_mode import LoadExecutionMode
from src.repositories.vest_reference_repository import VestReferenceRepository

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
)-> None:
    """
    Runs the vest statement pdf → compute month_end_vest_wallet_balance → postgres pipeline.

    Parameters
    ----------
    excel_path : Path
        Path to vest statement pdf
    dry_run : bool
        If True, executes full pipeline except postgres write
    load_mode: LoadExecutionMode
        custom LoadExecutionMode that provides the flag whether to load month_end_balance or transformed_transaction or both to postgres
     run_mode : str
        "delta" appends rows. "full" enables one-time pre-load truncate.
    backup_before_truncate : bool
        Whether to create a timestamped backup table before truncate in full mode.
    """

    if load_mode == LoadExecutionMode.LOAD_ALL:
        logger.info("Starting vest transactions and month end balance piepline")
    elif load_mode == LoadExecutionMode.LOAD_MONTH_END_ONLY:
        logger.info("Starting vest month end balance piepline")
    else:
        logger.info("Starting vest transactions piepline")
    
    month_year = extract_vest_statement_period(pdf_path)

    vest_raw_transactions_parsed_df = extract_vest_detailed_transactions(pdf_path,month_year)

    vest_raw_transaction_df = transform_vest_raw_transactions(vest_raw_transactions_parsed_df)

    (
        current_statement_month_first_date,
        current_statement_month_last_date,
        current_statement_Previous_month_first_date,
        current_statement_Previous_month_last_date,

    ) = _derive_vest_statement_dates(month_year)
    #-------------------------------------------------------------

    #=============================================================================================
    # IMP: From here we fetch data from postgres table which are required to feed to transformers
    # improvement/pondering point: can we make sure the order of vest statements to extract does not matter?
    #=============================================================================================
    read_engine = get_read_engine()
    
    # initializing vest SQL repository query class with read engine
    vest_reference_repository = VestReferenceRepository(read_engine)

    prev_month_end_vest_wallet_balance_df = vest_reference_repository.fetch_prev_month_end_balance(
        current_statement_Previous_month_last_date,
    )

    # creating a df for initial vest investment period
    if month_year == "7/2024":
        prev_month_end_vest_wallet_balance_df = pd.DataFrame(
        [
            [
                current_statement_month_last_date,
                0,
        ]
    ],
          columns=MONTH_END_BLALANCE_POSTGRES_TABLE_COLUMN_NAMES,
    )

    if prev_month_end_vest_wallet_balance_df.empty:
        logger.error(
            "No data fetched from 'vest_month_end_balance' | Date = %s", 
            current_statement_Previous_month_last_date
        )

        raise ValueError(
            "There should not be any period missing the month end blance | check for Date = %s",
            current_statement_Previous_month_last_date
        )

    if len(prev_month_end_vest_wallet_balance_df)>1:
        logger.error(
            "There should be only one record for period %s in 'vest_month_end_balance'", 
            current_statement_Previous_month_last_date
        )

        raise ValueError(
            "There should be only one record for period %s in the 'vest_month_end_balance' postgres table",
            current_statement_Previous_month_last_date
        )
    
    # getting the required months transaction details

    logger.info ("Fetching current month vest wallet deposits from 'vest_detailed_statement' postgres table")

    curr_month_vest_wallet_credit_df = vest_reference_repository.fetch_curr_month_wallet_credits(
        current_statement_month_first_date,
        current_statement_month_last_date,
    )

    if curr_month_vest_wallet_credit_df.empty:
        logger.warning(
            "No deposits found in 'vest_detailed_statement' | period = %s to %s", 
            current_statement_month_first_date,
            current_statement_month_last_date,
        )

    #-------------------------------------------------------------------------------------
    # executing query and logging respective information
    #-------------------------------------------------------------------------------------
    if prev_month_end_vest_wallet_balance_df.loc[0,"balance"] > 0:
        # if previous month end blance is +ve then we will fetch respecitve exchange rate
        # not only this we will also fetch current month credit exchange rate if its available
        logger.info ("Fetching combined current and previous month vest wallet deposits exchange rate from 'vest_usd_to_inr_deposit_exch_rate' postgres table")

        credit_amounts_exchg_rate_df = vest_reference_repository.fetch_curr_and_prev_exchange_rates(
            current_statement_Previous_month_first_date,
            current_statement_Previous_month_last_date,
            current_statement_month_first_date,
            current_statement_month_last_date,
        )

        if credit_amounts_exchg_rate_df.empty:
            logger.error(
                "No exchange rates found in 'vest_usd_to_inr_deposit_exch_rate_detailed_statement' | period = %s to %s and period = %s to %s", 
                current_statement_month_first_date,
                current_statement_month_last_date,
                current_statement_Previous_month_first_date,
                current_statement_Previous_month_last_date,
            )

            raise ValueError(
                "investigate why no exchange rate found in 'vest_usd_to_inr_deposit_exch_rate_detailed_statement' even though" \
                "there is positve month end blance for previous period" \
                "current preiod is %s", 
                month_year,
            )

    elif not curr_month_vest_wallet_credit_df.empty:
        # if the previous month end balance is -ve then we will check if there are any wallet credit for curr month
        # if yes then respective exchange rate will be fetched
        logger.info ("Fetching current month vest wallet deposits exchange rate from 'vest_usd_to_inr_deposit_exch_rate' postgres table")

        credit_amounts_exchg_rate_df = vest_reference_repository.fetch_curr_month_exchange_rates(
            current_statement_month_first_date,
            current_statement_month_last_date,
        )

        if credit_amounts_exchg_rate_df.empty:
            logger.error(
                "No exchange rates found in 'vest_usd_to_inr_deposit_exch_rate_detailed_statement' | period = %s to %s", 
                current_statement_month_first_date,
                current_statement_month_last_date,
            )

            raise ValueError(
                "investigate why no exchange rate found in 'vest_usd_to_inr_deposit_exch_rate_detailed_statement' even though" \
                "there is wallet credit for current period (%s)",
                month_year,
            )
    else:
        # if there is no amount letft to do any transaction then most porbably no buy transaction for this period
        # hence no point of running any query hence we will return empty df
        credit_amounts_exchg_rate_df = pd.DataFrame()

    #-------------------------------------------------------------------------------------------------------
    #=====================End of fetching dfs from postgres=============================================

    #------------------------------------------------------------
    # running transformer to get the final ready to persists df
    #------------------------------------------------------------
    (
        vest_month_end_balance_df,
        vest_transactions_transformed_df,
     ) = transform_vest_transactions(
        vest_raw_transaction_df,
        prev_month_end_vest_wallet_balance_df,
        curr_month_vest_wallet_credit_df,
        credit_amounts_exchg_rate_df,
        current_statement_month_last_date,
        month_year,
    )

    validate_vest_month_end_and_transformed_transactions(
        vest_month_end_balance_df,
        vest_transactions_transformed_df,
        prev_month_end_vest_wallet_balance_df,
        curr_month_vest_wallet_credit_df,
        credit_amounts_exchg_rate_df,
    )
    
    #-----------------------------------------------------------
    # finally the loader to load data to postgres
    #-----------------------------------------------------------
    if load_mode in (
        LoadExecutionMode.LOAD_ALL,
        LoadExecutionMode.LOAD_MONTH_END_ONLY
    ):
        load_vest_month_end_balance(
            vest_month_end_balance_df,
            get_write_engine,
            dry_run,
            run_mode,
            backup_before_truncate,
        )

        logger.info("vest month end balance piepline finished successfully | Period: %s", month_year)

    if load_mode in (
        LoadExecutionMode.LOAD_ALL,
        LoadExecutionMode.LOAD_TRANSFORMED_TRATRANSACTIONS_ONLY
    ):
        load_vest_transformed_transactions(
            vest_transactions_transformed_df,
            get_write_engine,
            dry_run,
            run_mode,
            backup_before_truncate,
        )

        logger.info("vest transformed transaction piepline finished successfully | Period: %s", month_year)