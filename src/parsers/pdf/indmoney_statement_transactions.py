import pdfplumber
import pandas as pd

from src.common.logging import logger

TRANSACTION_SECTION_HEADER = "transaction"


def _find_transaction_section_rows(table: list[list[str | None]]) -> list[list[str | None]]:
    for row_idx, row in enumerate(table):
        first_cell = str(row[0]).strip().lower() if row and row[0] is not None else ""
        if first_cell == TRANSACTION_SECTION_HEADER:
            return table[row_idx + 1 :]

        # fallback for template drift where full header row may appear directly
        normalized = [str(c).strip().lower() if c is not None else "" for c in row]
        if "trade date" in normalized and "entry type" in normalized and "amount" in normalized:
            return [row] + table[row_idx + 1 :]

    return []


def extract_indmoney_detailed_transactions(pdf_path: str, month_year: str) -> pd.DataFrame:
    if not pdf_path:
        logger.error("Pdf path is not provided")
        raise ValueError("Pdf path is not provided")

    logger.info("parsing INDmoney detailed transactions for %s", month_year)

    section_rows: list[list[str | None]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table is None:
                continue

            rows = _find_transaction_section_rows(table)
            if rows:
                section_rows.extend(rows)

    if len(section_rows) < 2:
        logger.warning("No transactions found in INDmoney statement")
        return pd.DataFrame()

    indmoney_transactions_df = pd.DataFrame(section_rows[1:], columns=section_rows[0])
    indmoney_transactions_df = indmoney_transactions_df.dropna(how="all")

    logger.info("Parsed %d lines of INDmoney transactions for %s", len(indmoney_transactions_df), month_year)
    return indmoney_transactions_df
