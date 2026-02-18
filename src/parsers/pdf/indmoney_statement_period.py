import pdfplumber
from datetime import datetime

from src.common.logging import logger


def extract_indmoney_statement_period(pdf_path: str) -> str:
    """
    Extracts INDMONEY statement period from the first page of the PDF.

    The parser searches for the marker `Monthly Statement Period:` and expects
    the period text in format like `June - 2025`. It then returns a normalized
    `month/year` string (`M/YYYY`) used across pipelines.

    Parameters
    ----------
    pdf_path : str
        Path to the INDMONEY account statement PDF.

    Returns
    -------
    str
        Statement period in `M/YYYY` format (example: `6/2025`).

    Raises
    ------
    ValueError
        If no text is present on page 1, if the period marker is missing,
        or if the period value cannot be parsed due to template drift.
    """
    logger.info("Parsing pdf %s", pdf_path)

    # Text we are looking for in the PDF
    transaction_period_text_indicator = "Monthly Statement Period:"

    with pdfplumber.open(pdf_path) as pdf:
        # Extracting first page text from pdf (generally period information present in the 1st page)
        page = pdf.pages[0]
        text = page.extract_text()

        if not text:
            logger.error("No text found in the first page of indmoney statement")
            raise ValueError("No text found in the first page of indmoney statement")

        lines = text.split("\n")

    month = None
    year = None

    # writing code to extract the period information (month and year for which the account statement is generated)
    for line in lines:
        if transaction_period_text_indicator not in line:
            continue

        # Extract the part AFTER "Monthly Statement Period:"
        period_text = line.split(transaction_period_text_indicator, 1)[1].strip().title()  # Normalize text (JUNE → June)

        # Example expected value: "June - 2025"
        try:
            dt = datetime.strptime(period_text, "%B - %Y")
            year = dt.year
            month = dt.month

            # Stop once we find the first valid match
            break

        except ValueError:
            logger.error("not found period information in %s , pdf template might have changed", pdf_path)
            raise ValueError(f"could not parse period from {pdf_path}")

    if month is None or year is None:
        logger.error("could not find period marker in %s", pdf_path)
        raise ValueError(f"could not parse period from {pdf_path}")

    month_year = f"{month}/{year}"

    logger.info("This indmoney statement is for %s", month_year)
    return month_year
