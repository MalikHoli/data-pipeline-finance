import pdfplumber
import pandas as pd
from src.common.logging import logger

def extract_mutual_fund_statement_period(pdf_path: str) -> str:

    logger.info("Parsing pdf %s",pdf_path)

    # initializing the variable that is going to store period information
    nav_date = None

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx in range(1, len(pdf.pages)):
            page = pdf.pages[page_idx]

            table = page.extract_table()
            if not table:
                continue

            header = table[0]
            rows = table[1:]
            df = pd.DataFrame(rows, columns=header)

            if df.empty:
                continue

            if "NAV Date" not in df.columns:
                continue

            # Get first non-null NAV Date value
            nav_date = (
                df["NAV Date"]
                .dropna()
                .astype(str)
                .str.strip()
                .iloc[0]
            )

            break

    if not nav_date:
        logger.error("could not find the NAV Date from the mutual fund statement")
        raise ValueError("could not extract period from mutual fund statement")
    
    logger.info("Found NAV Date as %s",nav_date)

    dt = pd.to_datetime(nav_date, format="%d-%b-%Y")
    month_year = str(dt.month)+'/'+str(dt.year)

    logger.info("This mutual fund statement is for %s",month_year)

    return month_year