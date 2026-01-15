import pandas as pd
import re
from src.common.logging import logger

def extract_kite_holding_period(pdf_excel: str) -> str:
    logger.info("Parsing excel %s",pdf_excel)

    holdings_df = pd.read_excel(pdf_excel)

    # getting the column having the holding period information
    text_df = holdings_df[holdings_df["Unnamed: 1"].notna()]

    # Extract date string from text
    dates = (
        text_df["Unnamed: 1"]
        .dropna()
        .str.extract(r'(\d{4}-\d{2}-\d{2})')[0]
        .dropna()
    )

    if dates.empty:
        logger.error(
            "Not found period information in %s, excel template might have changed",
            pdf_excel
        )
        raise ValueError(f"Could not parse period from {pdf_excel}")

    date_text = dates.iloc[0]

    # Convert to datetime
    statement_date = pd.to_datetime(date_text)

    month_year = str(statement_date.month)+'/'+str(statement_date.year)

    logger.info("This kite holding statement is for %s",month_year)
    return month_year