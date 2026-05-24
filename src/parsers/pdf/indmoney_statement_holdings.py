import pdfplumber
import pandas as pd
from typing import Final

from src.common.logging import logger

# =========================
# Constants (schema safety)
# These variables are intended to be a constant and must not be reassigned.
# =========================
TO_DETECT_HOLDINGS_SECTION_HEADER_INDMONEY: Final = ['Holdings', None, None, None, None, None, None, None]

#==================================================================
# Main Parser 
#==================================================================
def extract_indmoney_holdings(
        pdf_path: str,
        month_year: str,
) -> pd.DataFrame:
    """
    To be done

    """
    if not pdf_path:
        logger.error("Pdf path is not provided")
        raise ValueError("Pdf path is not provided")

    logger.info("parsing indmoney holdings for %s",month_year)

    #=============================
    # Initializing variables
    #=============================
    all_rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table is None:
                continue

            for row_idx, row in enumerate(table):
                if row == TO_DETECT_HOLDINGS_SECTION_HEADER_INDMONEY:
                    all_rows.extend(table[row_idx + 1 :])

    if len(all_rows) <= 1:
        logger.warning("No holdings rows found in INDmoney statement")
        return pd.DataFrame()

    indmoney_holdings_df = pd.DataFrame(all_rows[1:], columns=all_rows[0])

    logger.info(
        "Parsed %d lines of INDmoney holdings for %s",
        len(indmoney_holdings_df),
        month_year,
    )
    return indmoney_holdings_df