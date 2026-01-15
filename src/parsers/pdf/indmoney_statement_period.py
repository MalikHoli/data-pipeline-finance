import pdfplumber
from datetime import datetime
from src.common.logging import logger

def extract_indmoney_statement_period(pdf_path: str) -> str:
    
    logger.info("Parsing pdf %s",pdf_path)

    transaction_period_text_indicator = "Monthly Statement Period:"

    with pdfplumber.open(pdf_path) as pdf:
        # Extracting first page text from pdf (generally period information present in the 1st page
        page = pdf.pages[0]
        text = page.extract_text()
        lines = text.split("\n")


    for line in lines:
        if transaction_period_text_indicator in line:
            # Extract the part AFTER "Monthly Statement Period:"
            period_text = line.split(transaction_period_text_indicator, 1)[1].strip().title() # Normalize text (JUNE → June)

            # Example expected value:
            # "June - 2025"
            try:
                dt = datetime.strptime(period_text, "%B - %Y")

                year = dt.year
                month = dt.month
            
            except ValueError:
                logger.error("not found period information in %s , pdf template might have changed",pdf_path)
                raise ValueError(f"could not parse period from {pdf_path}")

            # Stop once we find the first valid match
            break

    month_year = str(month)+'/'+str(year)

    logger.info("This vest statement is for %s",month_year)
    return month_year