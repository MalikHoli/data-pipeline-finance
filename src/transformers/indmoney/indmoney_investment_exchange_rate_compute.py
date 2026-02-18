import re
import pandas as pd

from src.common.logging import logger
from src.transformers.helper import _clean_convert_currency_column_to_numeric

INDMONEY_DEPOSIT_REMARKS_PATTERN = re.compile(r"/INDMoney/|INDMoney\s+US\s*Sto", re.IGNORECASE)


def transform_indmoney_investment_exchange_rate(
    bank_statement_df: pd.DataFrame,
    indmoney_income_df: pd.DataFrame,
    month_year: str,
) -> pd.DataFrame:
    if bank_statement_df.empty:
        logger.warning("No bank statement rows found for %s", month_year)
        return pd.DataFrame()

    if indmoney_income_df.empty:
        logger.warning("No indmoney income rows found for %s", month_year)
        return pd.DataFrame()

    bank_df = bank_statement_df.copy()
    bank_df["Withdrawal Amount(INR)"] = _clean_convert_currency_column_to_numeric(bank_df["Withdrawal Amount(INR)"])

    bank_filtered_df = bank_df[
        bank_df["Transaction Remarks"].astype(str).str.contains(INDMONEY_DEPOSIT_REMARKS_PATTERN, na=False)
        & (bank_df["Withdrawal Amount(INR)"] > 1)
    ].copy()

    income_df = indmoney_income_df.copy()
    income_df = income_df[income_df["Entry Type"].astype(str).str.strip() == "Journal Entry(Cash)"].copy()

    income_df["Trade Date"] = pd.to_datetime(
        income_df["Trade Date"], format="%m/%d/%Y", errors="coerce"
    ).dt.strftime("%d/%m/%Y")
    income_df["USD Value"] = _clean_convert_currency_column_to_numeric(income_df["Net Amt"])

    if len(bank_filtered_df) != len(income_df):
        raise ValueError(
            "INR invested in indmoney using bank statement transaction length is not same as USD value credit "
            "showed in indmoney account statement"
        )

    income_df["Withdrawal Amount(INR)"] = bank_filtered_df["Withdrawal Amount(INR)"].tolist()
    income_df["Transaction Date"] = bank_filtered_df["Transaction Date"].tolist()

    final_df = income_df.copy()
    final_df["exchange rate"] = (final_df["Withdrawal Amount(INR)"] / final_df["USD Value"]).round(2)

    insert_df = final_df[["Transaction Date", "exchange rate", "USD Value", "Withdrawal Amount(INR)"]].copy()
    insert_df.rename(
        columns={
            "Transaction Date": "deposit_date",
            "exchange rate": "exchange_rate_1_usd_to_inr",
            "USD Value": "usd_deposit",
            "Withdrawal Amount(INR)": "inr_deposit",
        },
        inplace=True,
    )

    insert_df["deposit_date"] = pd.to_datetime(insert_df["deposit_date"], dayfirst=True, errors="coerce").dt.normalize()
    insert_df[["exchange_rate_1_usd_to_inr", "usd_deposit", "inr_deposit"]] = (
        insert_df[["exchange_rate_1_usd_to_inr", "usd_deposit", "inr_deposit"]].apply(_clean_convert_currency_column_to_numeric)
    )

    logger.info("Transformed indmoney deposit exchange rate rows=%d", len(insert_df))
    return insert_df
