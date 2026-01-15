import pdfplumber
import pandas as pd
from src.common.logging import logger
from src.parsers.pdf.indmoney_statement_period import extract_indmoney_statement_period

def extract_indmoney_detailed_transactions(pdf_path: str) -> pd.DataFrame:
    if not pdf_path:
        logger.error("Pdf path is not provided")
        raise ValueError("Pdf path is not provided")

    month_year = extract_indmoney_statement_period(pdf_path)

    logger.info("parsing INDmoney statement for %s",month_year)

    all_transactions = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()

            # run code only if table extraction was successful
            if table is not None:
                # Loop through the rows in the extracted table
                for row_idx, row in enumerate(table):
                    # If the current row matches the 'Transaction' header, capture all subsequent rows
                    if row == ['Transaction', None, None, None, None, None, None, None, None]:
                        # Start capturing from the next row
                        for next_row in table[row_idx + 1:]:                        
                            all_transactions.append(next_row)

    
    # The first element of income data section of statement contains the column headers
    # Convert to DataFrame using the first row as headers
    indmoney_transactions_df = pd.DataFrame(all_transactions[1:], columns=all_transactions[0])

    # this provides lenght of dataframe 
    result = len(indmoney_transactions_df)

    if result == 0:
        logger.warning("No transactions found in INDmoney statement")
        return pd.DataFrame()

    logger.info("Parsed %d lines of INDmoney transactions for %s", result,month_year)
    return indmoney_transactions_df