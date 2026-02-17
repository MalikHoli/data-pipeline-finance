import pandas as pd
import numpy as np
from calendar import monthrange
import re
from decimal import Decimal
import requests

from src.common.logging import logger

from typing import Final,Sequence
# =========================
# Constants (schema safety)
# These variables are intended to be a constant and must not be reassigned.
# =========================
GSHEET_OUTPUT_DATE_FORMAT: Final = "%d/%m/%Y"
VEST_STATEMENT_OUTPUT_DATE_FORMAT: Final = "%m/%d/%Y"
POSTGRES_OUTPUT_DATE_FORMAT: Final = "%Y-%m-%d"
NAV_DATE_FORMAT: Final = "%d-%b-%Y"
EXCEL_ORIGIN: Final = pd.Timestamp("1899-12-30")
VEST_DEPOSIT_INDICATOR_TRANSACTION_REMARKS_START: Final = "NRS/USD"
VEST_DEPOSIT_INDICATOR_TRANSACTION_REMARKS_END: Final = "@"
RENAME_VEST_TRANSFORMED_TRANSACTIONS_COLUMNS_AS_PER_POSTGRES_SCHEMA_DICT: Final = {
       "Trade Date":"trade_date",
       "Activity":"activity",
       "Symbol":"symbol",
       "Description":"description",
       "Quantity":"quantity",
       "Price":"price",
       "Amount":"amount",
}
MONTH_END_BLALANCE_POSTGRES_TABLE_COLUMN_NAMES: Final = ["date","balance"]
VEST_RAW_TRANSACTIONS_REQUIRED_COLUMNS_LIST: Final = [
        "trade_date",
        "activity",
        "symbol",
        "description",
        "quantity",
        "price",
        "amount",
]
VEST_STATEMENT_TRANSACTIONS_CONVERT_TO_NUMERIC: Final = ['amount', 'quantity', 'price']
VEST_STATEMENT_TRANSACTIONS_CONVERT_TO_POSTGRES_DATE: Final = ['trade_date']
VEST_STATEMENT_TRANSACTIONS_TRANSFORMER_CONVERT_TO_NUMERIC: Final = ['buy_exch_rate', 'inr_amount']

#=============================================================
def _convert_vest_date_for_postgres_posting(
        series: pd.Series,
) -> pd.Series:
    """
    Convert vest statement default date format (MM/DD/YYYY) to suitable for postgres (YYYY-MM-DD)
    """
    return(
        pd.to_datetime(
            series,
            format=VEST_STATEMENT_OUTPUT_DATE_FORMAT,
            errors="coerce",
        )
        .dt.normalize() #removes time component (sets to midnight)
    )

#=============================================================
def _derive_month_end_date_for_gsheet_posting(
        month_year: str,
) -> str:
    """
    derive date from period(MM/YYYY) which can be used as date while writing to googlesheet

    Rule:
    - February → actual last day (28/29)
    - Other months → always 30
    """
    month_str, year_str = month_year.split("/")
    month = int(month_str)
    year = int(year_str)
    
    # Get actual last day of the month
    last_day = monthrange(year, month)[1]

    final_day = last_day if month == 2 else 30

    final_date = (
        pd.Timestamp(year, month, final_day)
        .strftime(GSHEET_OUTPUT_DATE_FORMAT)
    )

    return final_date

#===============================================================
def _derive_month_end_date_for_postgres_posting(
        month_year: str,
) -> pd.Timestamp:
    """
    derive date from period(MM/YYYY) which can be used as date while writing to postgres

    Rule:
    - February → actual last day (28/29)
    - Other months → always 30
    """
    month_str, year_str = month_year.split("/")
    month = int(month_str)
    year = int(year_str)
    
    # Get actual last day of the month
    last_day = monthrange(year, month)[1]

    final_day = last_day if month == 2 else 30

    final_date = (
        pd.Timestamp(year, month, final_day)
        .normalize()
    )

    return final_date

#=============================================================
def _clean_convert_currency_column_to_numeric(
        series: pd.Series,
) -> pd.Series:
    """
    Cleans currency strings and converts them to numeric values.

    Handles:
    - commas
    - ₹,$ symbol
    - whitespace
    - coercion to NaN on failure
    """
    return (
        series
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.strip()
        .str.replace(
            r"^\((.*)\)$",     # Match values fully wrapped in parentheses
            r"-\1",            # Replace with negative sign
            regex=True
    )
        .pipe(pd.to_numeric, errors="coerce")
    )

#=============================================================
def _round_mutual_fund_investment_amount(
        value: float,
) -> float:
    """
    Business rounding rule:
    - >= 1,00,000 → nearest 1,000
    - < 1,00,000 → nearest 100
    """
    if pd.isna(value):
        return value

    if value >= 100_000:
        return int(round(value, -3))
    return int(round(value, -2))

#=============================================================
def _derive_month_end_date_from_NAV_for_gsheet_posting(
        nav_date: pd.Series,
) -> pd.Series:
    """
    Converts NAV date to financial month-end date.

    Rule:
    - NAV day 1-10 → previous month end
    - NAV day 11+ → current month end
    """
    early_days = nav_date.dt.day.between(1, 10)

    return pd.to_datetime(
        np.where(
            early_days,
            nav_date - pd.offsets.MonthEnd(1),
            nav_date + pd.offsets.MonthEnd(0)
        )
    )

#=============================================================
def _extract_deposit_value_in_USD(
        series: pd.Series,
) -> pd.Series:
    """
    Extracts USD deposit amount from Vest transaction remarks.
    
    Rule:
    - Extract string between NRS/USD and @ [as per current pdf format]
    - convert the string to numeric
    """
    # escape is used as markers may contain regex-special characters later
    start = re.escape(VEST_DEPOSIT_INDICATOR_TRANSACTION_REMARKS_START)
    end = re.escape(VEST_DEPOSIT_INDICATOR_TRANSACTION_REMARKS_END)

    pattern = rf"{start}\s*([0-9]+(?:\.[0-9]+)?)\s*{end}"

    return(
        series
        .str.extract(pattern)[0]
        .pipe(pd.to_numeric, errors="coerce")
    )

#=====================================================================
def _allocate_wallet_amount_to_transactions(
        vest_wallet_amounts: Sequence[float], #this allows list, tuple, NumPy arrays, etc.
        df: pd.DataFrame, 
        amount_col: str = "amount",
) -> tuple[
    pd.DataFrame,
    float
]:
    """
    PURPOSE
    -------
    This function allocates one or more VEST WALLET amounts against a list of
    transaction rows (typically BUY transactions).

    It simulates real brokerage / ledger behavior where:
    - Vest wallet balances are used to fund buys
    - Buys may exceed wallet balances
    - Excess buys may be funded by dividends or sell transactions sources

    The function:
    - Walks through transactions sequentially
    - Subtracts amounts from wallet balances
    - Splits rows when a wallet balance is partially consumed
    - Flags rows that are funded by "free money" (dividends, etc.)
    - Returns both:
        1. Modified DataFrame
        2. Final remaining balance (positive or negative)


    PARAMETERS
    ----------
    vest_wallet_amounts : list of float
        List of vest wallet balances in the order they were received.
        Example: [152.58, 272, 272]

    df : pandas.DataFrame
        Original transaction DataFrame.
        Must contain a numeric column named `amount_col`.

    amount_col : str
        Column name that holds transaction amounts (default = "amount").


    RETURNS
    -------
    (DataFrame, float)
        - Modified DataFrame with split rows and flags
        - Remaining balance:
            > 0  → unused vest wallet balance
            < 0  → amount funded by dividends / unknown source
    """

    # --------------------------------------------------------------
    # LOG A: Function entry / high-level intent
    # --------------------------------------------------------------
    logger.info(
        "Allocating %d vest wallet balance(s) across %d transaction row(s)",
        len(vest_wallet_amounts),
        len(df)
    )

    # ------------------------------------------------------------------
    # Defensive copy:
    # We NEVER mutate the original DataFrame passed by the caller.
    # This avoids side effects and subtle bugs.
    # ------------------------------------------------------------------
    df = df.copy()

    # ------------------------------------------------------------------
    # preserving the data types of all columns of df in the dictonary format
    # later we can enforce same formats to all columns for consistancy and predictable data type output
    # ------------------------------------------------------------------
    original_dtypes = df.dtypes.to_dict()

    # ------------------------------------------------------------------
    # start_idx:
    # Indicates from which row we should start consuming transactions.
    #
    # Initially = 0 (start from first transaction).
    # After a split, we resume from the REMAINDER row.
    # ------------------------------------------------------------------
    start_idx = 0

    # ------------------------------------------------------------------
    # remaining_balance:
    # Tracks leftover wallet balance (positive)
    # OR deficit funded by free money (negative).
    # This is returned to the caller for reconciliation purposes.
    # ------------------------------------------------------------------
    remaining_balance = 0.0

    # Total number of vest wallet balances (used to detect "last wallet")
    total_wallets = len(vest_wallet_amounts)

    # ------------------------------------------------------------------
    # OUTER LOOP:
    # Process each vest wallet balance sequentially, in the order received.
    # ------------------------------------------------------------------
    for wallet_idx, wallet_amount in enumerate(vest_wallet_amounts):

        # --------------------------------------------------------------
        # remaining:
        # Running balance for the CURRENT vest wallet.
        # Starts as the wallet amount and reduces as rows are consumed.
        # --------------------------------------------------------------
        remaining = wallet_amount

        # --------------------------------------------------------------
        # crossover_row:
        # Index where the wallet balance is exhausted mid-row.
        # If it stays None → wallet was not exhausted.
        # --------------------------------------------------------------
        crossover_row = None

        # --------------------------------------------------------------
        # INNER LOOP:
        # Walk transaction rows starting from start_idx.
        # --------------------------------------------------------------
        for idx in range(start_idx, len(df)):
            amt = df.loc[idx, amount_col]

            # Subtract transaction amount from current wallet balance
            remaining -= amt

            # If remaining goes negative, we crossed this row
            if remaining < 0:
                crossover_row = idx
                break

        # --------------------------------------------------------------
        # CASE 1:
        # Wallet balance was NOT exhausted (transactions ended first).
        # --------------------------------------------------------------
        if crossover_row is None:
            # remaining is positive → unused wallet balance
            remaining_balance += remaining
            continue

        # --------------------------------------------------------------
        # CASE 2:
        # Wallet balance exhausted within a row → SPLIT REQUIRED
        # --------------------------------------------------------------

        # Amount that could NOT be covered by wallet balance
        remainder_amount = abs(remaining)

        # Amount that WAS covered by wallet balance
        used_amount = df.loc[crossover_row, amount_col] - remainder_amount

        # --------------------------------------------------------------
        # LOG C: Wallet exhaustion + split details
        # --------------------------------------------------------------
        logger.info(
            "Vest wallet %.2f exhausted at row %d | used=%.2f, remainder=%.2f",
            wallet_amount,
            crossover_row+1, #crossover_row has index information now actual row position
            used_amount,
            remainder_amount
        )

        # --------------------------------------------------------------
        # Create "used" row (covered by wallet balance)
        # --------------------------------------------------------------
        row_used = df.loc[crossover_row].copy()
        row_used[amount_col] = used_amount

        # --------------------------------------------------------------
        # Create "remainder" row (not covered by wallet balance)
        # --------------------------------------------------------------
        row_remainder = df.loc[crossover_row].copy()
        row_remainder[amount_col] = remainder_amount

        # --------------------------------------------------------------
        # Rebuild DataFrame with split rows
        # --------------------------------------------------------------
        upper = df.iloc[:crossover_row]
        lower = df.iloc[crossover_row + 1:]

        df = pd.concat(
            [
                upper,
                row_used.to_frame().T,      # covered portion
                row_remainder.to_frame().T, # uncovered portion
                lower
            ],
            ignore_index=True
        )

        # made sure columns have uniform data types after concatination
        df = df.astype(original_dtypes)

        # --------------------------------------------------------------
        # CASE 2A:
        # This is the LAST vest wallet.
        # Everything from now on is FREE-FUNDED.
        # --------------------------------------------------------------
        if wallet_idx == total_wallets - 1:

            # ----------------------------------------------------------
            # LOG D: Transition to free-funded state
            # ----------------------------------------------------------
            logger.warning(
                "All vest wallet balances exhausted; free-funding begins at row %d with deficit %.2f",
                crossover_row + 1,
                remainder_amount
            )

            # Mark remainder row as free-funded
            df.loc[crossover_row + 1, "free_flag"] = True
            remaining_balance -= remainder_amount

            # ----------------------------------------------------------
            # All rows AFTER remainder row are FULLY free-funded
            # ----------------------------------------------------------
            for idx in range(crossover_row + 2, len(df)):
                df.loc[idx, "free_flag"] = True
                remaining_balance -= df.loc[idx, amount_col]

            # No more wallets → stop completely
            break

        # --------------------------------------------------------------
        # CASE 2B:
        # NOT the last vest wallet.
        # Remainder will be consumed by NEXT vest wallet.
        # --------------------------------------------------------------
        else:
            # Mark remainder row as crossover point for audit/debugging
            df.loc[crossover_row + 1, "crossover_flag"] = True

            # Resume next vest wallet from remainder row
            start_idx = crossover_row + 1

    # --------------------------------------------------------------
    # Final cleanup: enforce numeric + rounding for remaining_balance
    # --------------------------------------------------------------
    # Step 1: Convert to Decimal for precision
    balance_decimal = Decimal(str(remaining_balance))

    # Step 2: Round to 2 decimal places
    remaining_balance = round(balance_decimal, 2)  # → Decimal('0.00')

    # --------------------------------------------------------------
    # LOG E: Final summary for reconciliation
    # --------------------------------------------------------------
    logger.info(
        "Vest wallet allocation complete. Final remaining balance: %.2f",
        remaining_balance
    )

    # ------------------------------------------------------------------
    # FINAL RETURN
    # ------------------------------------------------------------------
    return df, remaining_balance

#======================================================================
def _assign_buy_exchange_rates_with_inr_amount(
    modified_df: pd.DataFrame,
    vest_wallet_exchange_rates: Sequence[float],
    amount_col: str = "Amount",
) -> pd.DataFrame:
    """
    Assigns exchange rates to 'buy_exch_rate' and computes 'inr_amount'
    as buy_exch_rate * amount, rounded to 2 decimal places.

    Parameters
    ----------
    modified_df : pd.DataFrame
        Input DataFrame containing 'amount' and optional flag columns

    vest_wallet_exchange_rates : Sequence[float]
        Exchange rates applied sequentially per vest wallet usage

    Returns
    -------
    pd.DataFrame
        Modified DataFrame with 'buy_exch_rate' and 'inr_amount' columns

    Raises
    ------
    ValueError
        - If both crossover_flag and free_flag are True for a row
        - If exchange rate list is exhausted unexpectedly
    """

    # --------------------------------------------------------------
    # LOG A: Function entry
    # --------------------------------------------------------------
    logger.info(
        "Assigning exchange rates to %d transaction row(s) using %d rate(s)",
        len(modified_df),
        len(vest_wallet_exchange_rates),
    )

    # Defensive copy: never mutate caller DataFrame
    df = modified_df.copy()

    # Validate amount column exists
    if amount_col not in df.columns:
        raise ValueError(
            f"Input DataFrame must contain the '{amount_col}' column."
        )

    # Convert amount column to numeric safely
    df[amount_col] = _clean_convert_currency_column_to_numeric(df[amount_col])

    # Initialize output columns
    df["buy_exch_rate"] = pd.NA
    df["inr_amount"] = pd.NA

    # Index to track current exchange rate
    rate_idx = 0

    # --------------------------------------------------------------
    # Iterate over transaction rows sequentially
    # --------------------------------------------------------------
    for idx, row in df.iterrows():

        # ----------------------------------------------------------
        # Conflict detection: both flags cannot be True
        # ----------------------------------------------------------
        if row["crossover_flag"] and row["free_flag"]:
            logger.error(
                "Flag conflict at row %d: both crossover_flag and free_flag are True",
                idx,
            )
            raise ValueError(
                f"Conflict detected: both crossover_flag and free_flag are True "
                f"in row {idx}. Row content:\n{row.to_dict()}"
            )

        # ----------------------------------------------------------
        # CASE 1: Free-funded transaction → zero exchange rate
        # ----------------------------------------------------------
        if row["free_flag"]:
            df.at[idx, "buy_exch_rate"] = 0.0
            df.at[idx, "inr_amount"] = 0.0
            continue

        # ----------------------------------------------------------
        # CASE 2: Crossover row → advance exchange rate
        # ----------------------------------------------------------
        if row["crossover_flag"]:
            rate_idx += 1

        # ----------------------------------------------------------
        # Guard: exchange rate exhaustion
        # ----------------------------------------------------------
        if rate_idx >= len(vest_wallet_exchange_rates) and len(vest_wallet_exchange_rates) != 0:
            logger.warning(
                "Exchange rate list exhausted at row %d (needed index %d)",
                idx,
                rate_idx,
            )
            raise ValueError(
                f"Exchange rate list exhausted at row {idx}. "
                f"Need {rate_idx + 1} rates but only have {len(vest_wallet_exchange_rates)}. "
                f"Remaining rows: {len(df) - idx} rows."
            )

        # Safety guard: handle empty rate list
        if len(vest_wallet_exchange_rates) == 0:
            exch_rate = 0.0
        else:
            exch_rate = vest_wallet_exchange_rates[rate_idx]

        # Assign exchange rate
        df.at[idx, "buy_exch_rate"] = exch_rate

        # ----------------------------------------------------------
        # Compute INR amount
        # ----------------------------------------------------------
        amount_val = row[amount_col]
        if pd.isna(amount_val):
            df.at[idx, "inr_amount"] = pd.NA
            
            logger.error(
                "Found the NA amount in the vest statement | row = %s",
                row.to_dict(),         
            )

            raise ValueError("Missing amount in vest transaction; aborting pipeline")
        else:
            df.at[idx, "inr_amount"] = round(float(amount_val) * float(exch_rate), 2)

    # --------------------------------------------------------------
    # LOG E: Final summary
    # --------------------------------------------------------------
    logger.info(
        "Exchange rate assignment complete. Total INR value: %.2f",
        pd.to_numeric(df["inr_amount"], errors="coerce").sum(skipna=True),
    )

    # Final cleanup: enforce numeric + rounding
    df["inr_amount"] = pd.to_numeric(df["inr_amount"], errors="coerce").round(2)

    return df

#======================================================================
def _fetch_usd_to_inr_exch_rate_from_Frankfurter_API(
        date: str,
) -> float:
    """
    Fetches exchage rate information from the free Frankfurter API for passed date
    fetched exchange rate is rounded to 2 decimal places

    Parameters
    ----------
    date: str
        Input date string pertaining to vest statement date (end date we put in gsheet)
    
    Returns
    -------
    flat
        returns the exchange for the passed date string
    """
    #--------------------------------------------------
    # Building API URL dynamically using date
    #---------------------------------------------------
    url = f"https://api.frankfurter.dev/v1/{date}?base=USD&symbols=INR"

    #--------------------------------------------------
    # Calling API
    # The API returns:
    # - exchange rate for that date OR
    # - the nearest previous business day
    #---------------------------------------------------
    logger.info("Fetching exchange rate information from Frankfurter API for %s",date)

    try:
        response = requests.get(url,timeout=10)
        response.raise_for_status() # this will immediately raise an exception if HTTP status is not 200 (success)

    except requests.HTTPError:
        logger.error(
        "HTTP request failed: %s %s",
        response.status_code,
        response.text,
        exc_info=True,
        )
        raise

    data = response.json()

    exch_rate = round(float(data["rates"]["INR"]))

    logger.info("Fetched exchange rate info from Frankfurter API for %s | %f",date,exch_rate)

    return exch_rate