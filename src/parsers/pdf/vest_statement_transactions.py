import pdfplumber
import pandas as pd
import re

from src.common.logging import logger
from src.parsers.pdf.vest_statement_period import extract_vest_statement_period

def extract_vest_detailed_transactions(pdf_path: str) -> pd.DataFrame:
    if not pdf_path:
        logger.error("Pdf path is not provided")
        raise ValueError("Pdf path is not provided")

    month_year = extract_vest_statement_period(pdf_path)

    logger.info("parsing vest transactions for %s",month_year)
    
    # below variable declaration is for readability
    # its same as "Trade Date Settle Date Currency Activity Type Symbol / Description Quantity Price Amount"
    text_to_detect_start_of_detailed_transactions = (
        "Trade Date "
        "Settle Date " 
        "Currency "
        "Activity Type "
        "Symbol / Description "
        "Quantity "
        "Price "
        "Amount"
    )

    # this ensured one more check to sure we are recognizing transaction record
    # as each transaction starts with date in MM/DD/YYY format
    date_pattern = re.compile(r"^\d{2}/\d{2}/\d{4}\b")

    text_to_detect_end_of_detailed_transactions = "SWEEP ACTIVITY"

    parsed_rows = []
    
    capture = False


    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.split("\n")

            for line in lines:
                line = line.strip()

                # STOP condition
                # stop searching rest of the pdf text
                if text_to_detect_end_of_detailed_transactions in line:
                    capture = False
                    break

                # Detect ACTIVITY section
                if line == "ACTIVITY":
                    capture = False
                    continue

                # Detect header
                if line == text_to_detect_start_of_detailed_transactions:
                    capture = True
                    continue

                # Capture data rows
                if capture:
                    # Must start with DD/MM/YYYY
                    if not date_pattern.match(line):
                        continue

                    parts = line.split()

                    # CRITICAL FIX: ensure minimum structure exists
                    # trade_date, settle_date, currency, activity, type, ..., quantity, price, amount
                    if len(parts) < 8:
                        logger.error("vest transaction structure not seems to be as per expectation")
                        raise ValueError("vest transaction structure not matching, please cehck the statement")

                    trade_date  = parts[0]
                    settle_date = parts[1]
                    currency    = parts[2]
                    activity    = parts[3]
                    type_       = parts[4]

                    amount      = parts[-1]
                    price       = parts[-2]
                    quantity    = parts[-3]

                    symbol_desc = " ".join(parts[6:-3])

                    parsed_rows.append([
                        trade_date,
                        settle_date,
                        currency,
                        activity,
                        type_,
                        symbol_desc,
                        quantity,
                        price,
                        amount
                    ])

    # Dataframe column names
    columns = [
        "Trade Date",
        "Settle Date",
        "Currency",
        "Activity",
        "Symbol",
        "Description",
        "Quantity",
        "Price",
        "Amount"
    ]

    vest_trasaction_df = pd.DataFrame(parsed_rows, columns=columns)

    # this provides lenght of dataframe 
    result = len(vest_trasaction_df)

    if result == 0:
        logger.warning("No transactions found in vest statement")
        return pd.DataFrame()

    logger.info("Parsed %d lines of vest transactions for %s", result,month_year)
    return vest_trasaction_df