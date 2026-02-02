import pandas as pd

from src.common.logging import logger

# =========================================
# Importing helper functions and constants
# =========================================
from src.transformers.helper import (
    _allocate_wallet_amount_to_transactions,
    _assign_buy_exchange_rates_with_inr_amount,
    _clean_convert_currency_column_to_numeric,
    RENAME_VEST_TRANSFORMED_TRANSACTIONS_COLUMNS_AS_PER_POSTGRES_SCHEMA_DICT,
)

# =========================
# Main transformer
# =========================
def transform_vest_transactions(
        vest_transactions_extract_df: pd.DataFrame,
        prev_month_end_vest_wallet_balance_df: pd.DataFrame,
        curr_month_vest_wallet_credit_df: pd.DataFrame,
        curr_month_credit_amounts_exchg_rate_df: pd.DataFrame,
        curr_and_Prev_month_credit_amounts_exchg_rate_df: pd.DataFrame,
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
    curr_month_credit_amounts_exchg_rate_df: pd.DataFrame,
        Output dataframe post querying the vest_usd_to_inr_deposit_exch_rate table for current statement month deposit
    curr_and_Prev_month_credit_amounts_exchg_rate_df: pd.DataFrame,
        Output dataframe post querying the vest_usd_to_inr_deposit_exch_rate table for current statement month deposit as well as previous month
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

    # =========================
    # Initializing variables
    # =========================
    vest_wallet_amount_list = []
    vest_wallet_amount_exchg_rate_list = []

    if not month_year:
        logger.error(
            "Failed to get the period information in the transformer"
        )
        raise ValueError("month_year must be provided in MM/YYYY format")
    
    # -----------------------------------------------------------
    # Vest wallet amount and respective exchage rate collection
    # -----------------------------------------------------------
    
    # checking if there is previous positive vest wallet balance from last month 
    is_prev_month_end_vest_wallet_balance_positive = not (
        prev_month_end_vest_wallet_balance_df["balance"].isna().all() # checking if there is any valid non null value in column
        or len(prev_month_end_vest_wallet_balance_df) == 0 # checking if the df is empty
        or prev_month_end_vest_wallet_balance_df["balance"].sum() <= 0 # checking if balance is -ve
    )

    # if there is previous month balance then get the respective wallet balance and exchange rates into the list
    if is_prev_month_end_vest_wallet_balance_positive:
        vest_wallet_amount_list.extend(prev_month_end_vest_wallet_balance_df["balance"].tolist())
        vest_wallet_amount_exchg_rate_list.extend(curr_and_Prev_month_credit_amounts_exchg_rate_df["exchange_rate_1_usd_to_inr"].tolist())
    
    # collect current month vest wallet credit amount
    vest_wallet_amount_list.extend(curr_month_vest_wallet_credit_df["amount"].tolist())

    # collect current month vest wallet amount exchange rate
    vest_wallet_amount_exchg_rate_list.extend(curr_month_credit_amounts_exchg_rate_df["exchange_rate_1_usd_to_inr"].tolist())

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

    # ----------------------------------
    # Vest buy transactions filteration
    # ----------------------------------
    vest_buy_transactions_df = vest_transactions_extract_df[
        vest_transactions_extract_df["Activity"].isin(["BUY", "JNLC"])
    ]

    if vest_buy_transactions_df.empty:
        logger.warning(
            "There were no buy transactions in vest statement for preiod %s",
            month_year,
        )
        
        return (pd.DataFrame(), pd.DataFrame())
    
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
        amount_col = "Amount",
    )

    vest_transactions_transformed_df = _assign_buy_exchange_rates_with_inr_amount(
        vest_wallet_amount_allocated_df,
        vest_wallet_amount_exchg_rate_list,
        amount_col="Amount",
    )

    #------------------------------------------
    # dropping unnecessary column
    # renaming columns as per postgres schema
    # formatting of the numrtic columns
    #------------------------------------------
    logger.info("cleaning, renaming and formatting as per postgres schema")

    vest_transactions_transformed_df.drop(columns="Settle Date",inplace=True)
    
    vest_transactions_transformed_df.rename(
        columns=RENAME_VEST_TRANSFORMED_TRANSACTIONS_COLUMNS_AS_PER_POSTGRES_SCHEMA_DICT
    )

    numeric_columns = ['quantity', 'price', 'amount', 'buy_exch_rate', 'inr_amount']

    vest_transactions_transformed_df[numeric_columns] = (
        vest_transactions_transformed_df[numeric_columns]
        .apply(_clean_convert_currency_column_to_numeric)
        .astype(float)
    )

    
    logger.info(
        "vest transaction table transformed | rows=%d | columns=%s",
        len(vest_transactions_transformed_df),
        list(vest_transactions_transformed_df.columns),
    )

    vest_month_end_balance_df = pd.DataFrame(
        [
            [
                current_statement_month_last_date,
                remaining_balance,
        ]
    ],
          columns=["date","balance"],
    )

    logger.info(
        "vest month end balance df prepared | rows=%d | columns=%s",
        len(vest_month_end_balance_df),
        list(vest_month_end_balance_df.columns)
    )

    return  vest_month_end_balance_df,vest_transactions_transformed_df