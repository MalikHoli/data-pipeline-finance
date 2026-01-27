import pdfplumber
import re
import pandas as pd
from src.common.logging import logger

def extract_vest_statement_period(pdf_path: str) -> str:
    
    logger.info("Fetching period information from pdf %s",pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        # Extracting first page text from pdf (generally period information present in the 1st page
        page = pdf.pages[0]
        text = page.extract_text()
        lines = text.split("\n")

    # This line has period information in like this "December 01, 2024 - December 31, 2024" i.e. (Month DD, YYYY)
    date_range_text = lines[1] 

    # 1️⃣ Extract first set of date date (December 01, 2024)
    match = re.search(r"([A-Za-z]+ \d{2}, \d{4})", date_range_text)

    if not match:
        logger.error("not found period information in %s , pdf template might have changed",pdf_path)
        raise ValueError(f"could not parse period from {pdf_path}")

    first_date_str = match.group(1)
    
    # 2️⃣ Convert to datetime
    dt = pd.to_datetime(first_date_str)

    month_year = str(dt.month)+'/'+str(dt.year)

    logger.info("This vest statement is for %s",month_year)
    return month_year