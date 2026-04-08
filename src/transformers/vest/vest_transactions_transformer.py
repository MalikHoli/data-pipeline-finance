import pandas as pd

from src.common.logging import logger

# =========================================
# Importing helper functions and constants
# =========================================
from src.transformers.helper import (
    _allocate_wallet_amount_to_transactions,
    _assign_buy_exchange_rates_with_inr_amount,
    _clean_convert_currency_column_to_numeric,
    _convert_vest_month_end_date_for_postgres_posting,
    MONTH_END_BLALANCE_POSTGRES_TABLE_COLUMN_NAMES,
    VEST_STATEMENT_TRANSACTIONS_TRANSFORMER_CONVERT_TO_NUMERIC,
    VEST_MONTH_END_BALANCE_CONVERT_TO_POSTGRES_DATE,
    VEST_MONTH_END_BALANCE_CONVERT_TO_NUMERIC
)

# =========================
# Main transformer
# =========================
def transform_vest_transactions(
        vest_raw_trasaction_df: pd.DataFrame,
        prev_month_end_vest_wallet_balance_df: pd.DataFrame,
        curr_month_vest_wallet_credit_df: pd.DataFrame,
        credit_amounts_exchg_rate_df: pd.DataFrame,
        current_statement_month_last_date: str,
        month_year: str,
) -> tuple[
            pd.DataFrame,
            pd.DataFrame,
    ]:
    """
    Transform raw vest transactions into schema that is helpful to calculate invested amount in INR 
    
    Parameters
    ----------
    vest_transactions_extract_df: pd.DataFrame,
        Output dataframe from vest_transactions_parser
    prev_month_end_vest_wallet_balance_df: pd.DataFrame,
        Output dataframe post querying the vest_month_end_balance postgres table
    curr_month_vest_wallet_credit_df: pd.DataFrame,
        Output dataframe post querying the vest_detailed_statement postgres table for current month vest wallet credits
    credit_amounts_exchg_rate_df: pd.DataFrame,
        Output dataframe post querying the vest_usd_to_inr_deposit_exch_rate table
    current_statement_month_last_date: str,
        provides the last date of the month for which vest statement holds information
    month_year : str
        The period for which this vest statement generated
    
    Returns
    -------
    pd.DataFrame
        Final transformed dataframe holding the month end vest wallet balance ready for persistance or analytics
    pd.DataFrame
        Final vest transactions transformed dataframe ready for persistance or analytics
    """
    if not month_year:
        logger.error(
            "Failed to get the period information in the transformer"
        )
        raise ValueError("month_year must be provided in MM/YYYY format")
    
    # ----------------------------------
    # Vest buy transactions filteration
    # ----------------------------------
    vest_buy_transactions_df = (
        vest_raw_trasaction_df[
            vest_raw_trasaction_df["activity"].isin(["BUY", "JNLC"])
        ]
        .copy()
        .reset_index(drop=True)
    )
 
    if vest_buy_transactions_df.empty:
        logger.warning(
            "There were no buy transactions in vest statement for period %s",
            month_year,
        )

        vest_month_end_balance_df = pd.DataFrame(
            [
                [
                    current_statement_month_last_date,
                    prev_month_end_vest_wallet_balance_df.loc[0,"balance"],
                ]
            ],
                columns=MONTH_END_BLALANCE_POSTGRES_TABLE_COLUMN_NAMES,
        )

        vest_month_end_balance_df[VEST_MONTH_END_BALANCE_CONVERT_TO_POSTGRES_DATE] = (
            vest_month_end_balance_df[VEST_MONTH_END_BALANCE_CONVERT_TO_POSTGRES_DATE]
            .apply(_convert_vest_month_end_date_for_postgres_posting)
        )

        vest_month_end_balance_df[VEST_MONTH_END_BALANCE_CONVERT_TO_NUMERIC] = (
        vest_month_end_balance_df[VEST_MONTH_END_BALANCE_CONVERT_TO_NUMERIC]
        .apply(_clean_convert_currency_column_to_numeric)
    )

        return (
            vest_month_end_balance_df, # returning month_end_balance of previous month
            pd.DataFrame(), # returning empty transformed df
        )
        
    # =========================
    # Initializing variables
    # =========================
    vest_wallet_amount_list = []
    vest_wallet_amount_exchg_rate_list = []

    # -----------------------------------------------------------
    # Vest wallet amount and respective exchage rate collection
    # -----------------------------------------------------------
    # add to the vest wallet amount list for further operations only if previous month end balance is +ve
    if prev_month_end_vest_wallet_balance_df.loc[0,"balance"] > 0:
        vest_wallet_amount_list.extend(prev_month_end_vest_wallet_balance_df["balance"].tolist()) # has only previous month balance

    # collect current month vest wallet credit amount (df will be empty in case there are no credits)
    vest_wallet_amount_list.extend(curr_month_vest_wallet_credit_df["amount"].tolist())

    # collect the respective wallet amounts exchange rate
    vest_wallet_amount_exchg_rate_list.extend(credit_amounts_exchg_rate_df["exchange_rate_1_usd_to_inr"].tolist())


    # ---------------------------------------------------------------
    # Imp checkpoint - each wallet amounts should have respective exchage rate
    # ---------------------------------------------------------------
    if len(vest_wallet_amount_list) != len(vest_wallet_amount_exchg_rate_list):
        logger.error(
            f"Expected {len(vest_wallet_amount_list)} exchange rates, but got {len(vest_wallet_amount_exchg_rate_list)}. "
            "This mismatch suggests inconsistent data mapping between vest wallet amounts and exchange rates."
        )
        raise ValueError(
            "Something is wrong: ambiguity in finding the exchange rate for the credit amounts. "
        )
    else:
        logger.info(
            "length of vest wallet amount list is same as exchange rate list i.e. %d",
            len(vest_wallet_amount_list)
        ) 
 
    # Amount column is in -ve as its buy value in statement
    # converting it to +ve
    vest_buy_transactions_df["amount"] = vest_buy_transactions_df["amount"]*(-1)

    if (vest_buy_transactions_df["amount"]<0).any():
        logger.warning(
            "Negative amount detected check the statement | Period = %s",
            month_year,
        )

    # --------------------------------------------------------------------------------------
    # creating new columns and defaulting to False to avoid NaN in upcoming transformation
    # --------------------------------------------------------------------------------------
    vest_buy_transactions_df["free_flag"] = False
    vest_buy_transactions_df["crossover_flag"] = False
    
    #------------------------------------------
    # Applying transformations
    # note that loggers are already present in helper functions
    #-------------------------------------------
    vest_wallet_amount_allocated_df,remaining_balance = _allocate_wallet_amount_to_transactions(
        vest_wallet_amount_list,
        vest_buy_transactions_df,
        amount_col = "amount",
    )

    vest_transactions_transformed_df = _assign_buy_exchange_rates_with_inr_amount(
        vest_wallet_amount_allocated_df,
        vest_wallet_amount_exchg_rate_list,
        amount_col="amount",
    )

    #------------------------------------------
    # formatting of the numrtic columns
    #------------------------------------------
    logger.info("cleaning, formatting of newly created columns as per postgres schema")

    vest_transactions_transformed_df[VEST_STATEMENT_TRANSACTIONS_TRANSFORMER_CONVERT_TO_NUMERIC] = (
        vest_transactions_transformed_df[VEST_STATEMENT_TRANSACTIONS_TRANSFORMER_CONVERT_TO_NUMERIC]
        .apply(_clean_convert_currency_column_to_numeric)
        .astype(float)
    )

    
    logger.info(
        "vest transaction table transformed | rows=%d",
        len(vest_transactions_transformed_df),
    )

    vest_month_end_balance_df = pd.DataFrame(
        [
            [
                current_statement_month_last_date,
                remaining_balance,
        ]
    ],
          columns=MONTH_END_BLALANCE_POSTGRES_TABLE_COLUMN_NAMES,
    )

    vest_month_end_balance_df[VEST_MONTH_END_BALANCE_CONVERT_TO_POSTGRES_DATE] = (
        vest_month_end_balance_df[VEST_MONTH_END_BALANCE_CONVERT_TO_POSTGRES_DATE]
        .apply(_convert_vest_month_end_date_for_postgres_posting)
    )

    vest_month_end_balance_df[VEST_MONTH_END_BALANCE_CONVERT_TO_NUMERIC] = (
        vest_month_end_balance_df[VEST_MONTH_END_BALANCE_CONVERT_TO_NUMERIC]
        .apply(_clean_convert_currency_column_to_numeric)
    )


    logger.info(
        "vest month end balance df prepared | rows=%d",
        len(vest_month_end_balance_df),
    )

    return  vest_month_end_balance_df,vest_transactions_transformed_df