import re
import pdfplumber
import pandas as pd
from datetime import datetime
from typing import Final

BANK_STATEMENT_DF_HEADER: Final = [
    'S No.', 
    'Value Date', 
    'Transaction Date', 
    'Cheque Number',
    'Transaction Remarks', 
    'Withdrawal Amount(INR)',
    'Deposit Amount(INR)', 
    'Balance(INR)',
]

(
    COL_SNO,
    COL_VALUE_DATE,
    COL_TXN_DATE,
    COL_CHEQUE,
    COL_REMARKS,
    COL_WITHDRAWAL,
    COL_DEPOSIT,
    COL_BALANCE,
) = BANK_STATEMENT_DF_HEADER

from src.common.logging import logger

# -----------------------------
# V1: Legacy table-based parser
# -----------------------------
def _parse_period_v1_format(
        lines: list[str],
) -> str | None:
    """Extract MM/YYYY from legacy 'Transaction Date from ...' format."""

    # Text indicator specific to legacy statement format
    indicator = "Transaction Date from "

    for line in lines:
        # Normalize line by removing leading/trailing spaces
        line = line.strip()

        if indicator in line:
            # Extract last 7 characters assuming MM/YYYY format
            month_year = line[-7:]

            # Validate extracted value strictly matches MM/YYYY
            if re.fullmatch(r"(0[1-9]|1[0-2])/\d{4}", month_year):
                return month_year

            # Log warning if indicator matched but format is unexpected
            logger.warning(
                "V1 parser matched but invalid format: %s",
                month_year
            )

    # Return None if this format is not applicable
    return None

# -----------------------------
# V2: New line-based parser
# -----------------------------
def _parse_period_v2_format(
        lines: list[str],
) -> str | None:
    """Extract MM/YYYY from header format like 'January 31, 2026'."""

    # Text indicator specific to newer statement header format
    indicator = "Statement of Transactions in Saving Account no."

    for line in lines:
        # Normalize line for consistent matching
        line = line.strip()

        if indicator in line:
            # Extract date like "January 31, 2026" using regex
            match = re.search(r"[A-Za-z]+ \d{1,2}, \d{4}", line)

            if match:
                date_str = match.group()

                try:
                    # Parse full month date into datetime object
                    dt = datetime.strptime(date_str, "%B %d, %Y")

                    # Convert to MM/YYYY format for pipeline consistency
                    return dt.strftime("%m/%Y")

                except ValueError:
                    # Log if parsing fails due to unexpected format change
                    logger.warning(
                        "V2 parser failed to parse date: %s",
                        date_str
                    )

    # Return None if this format is not applicable
    return None

# combining parsing logic of various format in the list for export
PERIOD_PARSERS = [
    _parse_period_v1_format,
    _parse_period_v2_format,
]

# -----------------------------
# V1: Legacy table-based parser
# -----------------------------
def _parse_transactions_v1_format(
        pdf_path: str
) -> pd.DataFrame:
    """
    Extract transactions using legacy table format (pdfplumber.extract_table).
    """

    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_inx, page in enumerate(pdf.pages):
            table = page.extract_table()
            if not table:
                continue
            
            # filtering the lists having the transaction information for that we are checking if the 
            # first element of the list and if its serial no then it must be a digit then thats valid 
            # transaction list
            rows = [
                row for row in table
                if row and row[0] and str(row[0]).strip().isdigit()
            ]

            if not rows:
                continue

            df = pd.DataFrame(rows, columns=BANK_STATEMENT_DF_HEADER)
            df["source_page"] = page_inx + 1
            all_tables.append(df)

    if not all_tables:
        return pd.DataFrame()

    result = pd.concat(all_tables, ignore_index=True)

    logger.info("Parsed %d transactions using V1 format", len(result))

    return result

# -----------------------------
# V2: New line-based parser
# -----------------------------
def _parse_transactions_v2_format(
        pdf_path: str
) -> pd.DataFrame:
    """
    Extract transactions from new format:
    - Line contains 'NRS/USD' → remarks
    - Next line contains: SNo Date Amount Balance
    """

    all_lines = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_lines.extend(text.split("\n"))

    records = []

    for i in range(len(all_lines)):
        line = all_lines[i].strip()

        if "NRS/USD" in line:
            remarks = line

            if i + 1 >= len(all_lines):
                continue

            next_line = all_lines[i + 1].strip()

            match = re.match(
                r"(\d+)\s+(\d{2}\.\d{2}\.\d{4})\s+([\d.]+)\s+([\d.]+)",
                next_line
            )

            if not match:
                continue

            s_no, date, amount, balance = match.groups()

            records.append({
                COL_SNO: s_no,
                COL_VALUE_DATE: date,
                COL_TXN_DATE: date,
                COL_CHEQUE: None,
                COL_REMARKS: remarks,
                COL_WITHDRAWAL: amount,
                COL_DEPOSIT: None,
                COL_BALANCE: balance,
            })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # Ensure strict schema alignment
    df = df.reindex(columns=BANK_STATEMENT_DF_HEADER)

    logger.info("Parsed %d transactions using V2 format", len(df))

    return df

# combining parsing logic of various format in the list for export
TRANSACTION_PARSERS = [
    _parse_transactions_v1_format,
    _parse_transactions_v2_format,
]