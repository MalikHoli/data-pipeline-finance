import pdfplumber
import pandas as pd

from src.common.logging import logger


def _find_holdings_section_rows(table: list[list[str | None]]) -> list[list[str | None]]:
    for row_idx, row in enumerate(table):
        normalized = [str(c).strip().lower() if c is not None else "" for c in row]

        if len(normalized) == 8 and normalized[0] == "holdings":
            return table[row_idx + 1 :]

        # fallback for drift: direct headers may be present
        if "symbol" in normalized and "market value" in normalized and "unrealized" in normalized:
            return [row] + table[row_idx + 1 :]

    return []


def extract_indmoney_holdings(pdf_path: str, month_year: str) -> pd.DataFrame:
    if not pdf_path:
        logger.error("Pdf path is not provided")
        raise ValueError("Pdf path is not provided")

    logger.info("parsing INDmoney holdings for %s", month_year)

    holdings_rows: list[list[str | None]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table is None:
                continue
            rows = _find_holdings_section_rows(table)
            if rows:
                holdings_rows.extend(rows)

    if len(holdings_rows) < 2:
        logger.warning("No holdings section rows found in INDmoney statement")
        return pd.DataFrame()

    df = pd.DataFrame(holdings_rows[1:], columns=holdings_rows[0]).dropna(how="all")
    logger.info("Parsed %d holdings rows for %s", len(df), month_year)
    return df
