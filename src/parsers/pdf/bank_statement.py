import pdfplumber
import pandas as pd
from typing import Final

from src.common.logging import logger
from src.parsers.pdf.parsing_stategies.bank_statement_format_parsers import TRANSACTION_PARSERS

def extract_bank_table_transactions(
        pdf_path: str,
        month_year: str,
) -> pd.DataFrame:

    if not pdf_path:
        logger.error("Pdf path is not provided")
        raise ValueError("Pdf path is not provided")

    logger.info("Parsing bank statement for %s", month_year)

    for parser in TRANSACTION_PARSERS:
        try:
            df = parser(pdf_path)

            if not df.empty:
                logger.info(
                    "Transactions extracted using %s for %s",
                    parser.__name__,
                    month_year,
                )
                return df

        except Exception as e:
            logger.warning(
                "Parser %s failed: %s",
                parser.__name__,
                str(e),
            )

    logger.warning("No transactions found in bank statement")
    return pd.DataFrame()