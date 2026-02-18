import pdfplumber
import pandas as pd

from src.common.logging import logger


def _find_income_section_rows(table: list[list[str | None]]) -> list[list[str | None]]:
    for row_idx, row in enumerate(table):
        normalized = [str(c).strip().lower() if c is not None else "" for c in row]

        if len(normalized) == 5 and normalized[0] == "income":
            return table[row_idx + 1 :]

        # fallback: if a table already starts with expected income headers
        if "trade date" in normalized and "entry type" in normalized and "net amt" in normalized:
            return [row] + table[row_idx + 1 :]

    return []


def extract_indmoney_income_transactions(pdf_path: str, month_year: str) -> pd.DataFrame:
    if not pdf_path:
        logger.error("Pdf path is not provided")
        raise ValueError("Pdf path is not provided")

    logger.info("parsing INDmoney income section for %s", month_year)

    income_rows: list[list[str | None]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table is None:
                continue
            rows = _find_income_section_rows(table)
            if rows:
                income_rows.extend(rows)

    if len(income_rows) < 2:
        logger.warning("No income section rows found in INDmoney statement")
        return pd.DataFrame()

    df = pd.DataFrame(income_rows[1:], columns=income_rows[0]).dropna(how="all")
    logger.info("Parsed %d lines of INDmoney income entries for %s", len(df), month_year)
    return df
