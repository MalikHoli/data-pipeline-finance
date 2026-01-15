import pdfplumber
import re
from src.common.logging import logger

def extract_bank_statement_period(pdf_path: str) -> str:

    logger.info("Parsing pdf %s",pdf_path)

    transaction_period_text_indicator = "Transaction Date from "

    with pdfplumber.open(pdf_path) as pdf:
        # we are interested in 1st page to extract transaction period
        page = pdf.pages[0]
        text = page.extract_text()
        if not text:
            logger.error("No text found in the 1st page of bank statement hence not able to get transaction period")
            raise ValueError("No text found in the 1st page of bank statement")

    lines = text.split("\n")
    for line in lines:
        line = line.strip()   
        if transaction_period_text_indicator in line:
            # last 7 character should give us MM/YYYY format string
            month_year = line[-7:] 
            
            # checking if the format of text is not like MM/YYYY
            if not re.fullmatch(r"(0[1-9]|1[0-2])/\d{4}", month_year):
                logger.error("format of the transaction period is not matching MM/YYYY")
                raise ValueError(f"Invalid month/year format: {month_year}")

    logger.info("This bank statement is for %s",month_year)
    return month_year