import pdfplumber
import pandas as pd
from typing import Final

from src.common.logging import logger
from src.parsers.pdf.bank_statement_period import extract_bank_statement_period

BANK_STATEMENT_DF_HEADER: Final = [
    'S No.', 
    'Value Date', 
    'Transaction Date', 
    'Cheque Number',
    'Transaction Remarks', 
    'Withdrawal Amount(INR)',
    'Deposit Amount(INR)', 
    'Balance(INR)',
]


def extract_bank_table_transactions(
        pdf_path: str,
        month_year: str,
) -> pd.DataFrame:
    if not pdf_path:
        logger.error("Pdf path is not provided")
        raise ValueError("Pdf path is not provided")

    logger.info("parsing bank statement for %s",month_year)

    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_inx, page in enumerate(pdf.pages):
            table = page.extract_table()
            if not table:
                continue

            # filtering the lists having the transaction information for that we are checking if the 
            # first element of the list and if its serial no then it must be a digit then thats valid 
            # transaction list
            rows = [
                row for row in table
                if row and row[0] and str(row[0]).strip().isdigit()
            ]

            df = pd.DataFrame(rows, columns=BANK_STATEMENT_DF_HEADER)
            df["source_page"] = page_inx + 1
            all_tables.append(df)

    if not all_tables:
        logger.warning("No transactions found in bank statement")
        return pd.DataFrame()

    result = pd.concat(all_tables, ignore_index=True)
    logger.info("Parsed %d lines of bank transactions for %s", len(result),month_year)
    return result