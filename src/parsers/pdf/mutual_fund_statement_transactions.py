import pdfplumber
import pandas as pd
from src.common.logging import logger
from src.parsers.pdf.mutual_fund_statement_period import extract_mutual_fund_statement_period

def extract_mutual_fund_statement(pdf_path: str) -> pd.DataFrame:
    if not pdf_path:
        logger.error("Pdf path is not provided")
        raise ValueError("Pdf path is not provided")

    month_year = extract_mutual_fund_statement_period(pdf_path)

    logger.info("parsing mutual fund statement for %s",month_year)

    all_tables = []  # list to collect DataFrames

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx in range(1, len(pdf.pages)):  # start at 1 to skip page 1
            page = pdf.pages[page_idx]
            
            table = page.extract_table()
            if table:
                # First row = header, rest = data
                header = table[0]
                rows = table[1:]
                
                df = pd.DataFrame(rows, columns=header)
                df["source_page"] = page_idx + 1  # for reference (human page number)
                all_tables.append(df)

    # Combine all page tables into one DataFrame
    if all_tables:
        mutual_fund_summary_table = pd.concat(all_tables, ignore_index=True)

    # this provides lenght of dataframe 
    result = len(mutual_fund_summary_table)

    if result == 0:
        logger.warning("No transactions found in mutual fund CAS summary statement")
        return pd.DataFrame()

    # dropping unnecessary rows and columns
    mutual_fund_summary_table_final = mutual_fund_summary_table[mutual_fund_summary_table["Folio No."].notna()].drop(columns=["Client Id"])

    # this provides lenght of final dataframe 
    result = len(mutual_fund_summary_table_final)

    logger.info("Parsed %d lines of mutual funds for %s", result,month_year)
    return mutual_fund_summary_table_final