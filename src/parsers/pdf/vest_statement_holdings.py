import pdfplumber
import pandas as pd
from typing import Final

from src.common.logging import logger
from src.parsers.pdf.vest_statement_period import extract_vest_statement_period

# =========================
# Constants (schema safety)
# These variables are intended to be a constant and must not be reassigned.
# =========================
TEXT_TO_DETECT_START_OF_VEST_HOLDINGS_SUMMARY: Final = (
    "Description "
    "Symbol " 
    "Quantity "
    "Unit Cost "
    "Total Cost "
    "Market Price "
    "Market Value "
    "Gain/ (Loss) "
    "A/C Type"
)
TEXT_TO_DETECT_END_OF_VEST_HOLDINGS_SUMMARY: Final = "MoneyMarket funds"

OUTPUT_DATAFRAME_COLUMNS: Final = [
        "description",
        "symbol",
        "quantity",
        "unit_cost",
        "total_cost",
        "market_price",
        "market_value",
        "gain",
        "account_type"
]

#==================================================================
# Main Parser 
#==================================================================
def extract_vest_holdings(
        pdf_path: str,
        month_year: str,
) -> pd.DataFrame:
    """
    To be done

    """
    if not pdf_path:
        logger.error("Pdf path is not provided")
        raise ValueError("Pdf path is not provided")

    logger.info("parsing vest holdings for %s",month_year)

    #=============================
    # Initializing variables
    #=============================
    parsed_rows = []
    stop_capture = False

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            if stop_capture:
                break  # stop reading further pages

            text = page.extract_text()
            if not text:
                continue

            lines = text.split("\n")
            capture = False

            for line in lines:
                line = line.rstrip()

                # 🔴 STOP condition
                if line.strip() == TEXT_TO_DETECT_END_OF_VEST_HOLDINGS_SUMMARY:
                    stop_capture = True
                    break

                # 1️⃣ Detect header
                if line == TEXT_TO_DETECT_START_OF_VEST_HOLDINGS_SUMMARY:
                    capture = True
                    continue

                # 2️⃣ Capture only valid data rows
                if capture:
                    if not (line.endswith(" C") or line.endswith(" L")):
                        continue

                    parts = line.split()

                    ac_type       = parts[-1]
                    gain_loss     = parts[-2]
                    market_value  = parts[-3]
                    market_price  = parts[-4]
                    total_cost    = parts[-5]
                    unit_cost     = parts[-6]
                    quantity      = parts[-7]
                    symbol        = parts[-8]
                    description   = " ".join(parts[:-8])

                    parsed_rows.append([
                        description,
                        symbol,
                        quantity,
                        unit_cost,
                        total_cost,
                        market_price,
                        market_value,
                        gain_loss,
                        ac_type
                    ])


    vest_holdings_df = pd.DataFrame(parsed_rows, columns=OUTPUT_DATAFRAME_COLUMNS)

    result = len(vest_holdings_df)

    if result == 0:
        logger.warning("No holding summary found in vest statement")
        return pd.DataFrame()

    logger.info("Parsed %d lines of vest holdings for %s", result,month_year)
    return vest_holdings_df