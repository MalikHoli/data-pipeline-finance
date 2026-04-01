import pdfplumber
from src.common.logging import logger

from src.parsers.pdf.parsing_stategies.bank_statement_format_parsers import PERIOD_PARSERS

def extract_bank_statement_period(pdf_path: str) -> str:

    logger.info("Parsing pdf %s",pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        # we are interested in 1st page to extract transaction period
        page = pdf.pages[0]
        text = page.extract_text()
        if not text:
            logger.error("No text found in the 1st page of bank statement hence not able to get transaction period")
            raise ValueError("No text found in the 1st page of bank statement")

    lines = text.split("\n")

    # Try each parser until one succeeds
    for parser in PERIOD_PARSERS:
        month_year = parser(lines)

        if month_year:
            logger.info(
                "Transaction period extracted using %s: %s",
                parser.__name__,
                month_year,
            )
            return month_year

    # If no parser succeeds → fail explicitly
    logger.error(
        "Failed to extract transaction period using all known parsers"
    )
    raise ValueError(
        "Unable to determine transaction period from statement"
    )