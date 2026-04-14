import pdfplumber
import pandas as pd
from typing import Final
from decimal import Decimal
import re

from src.common.logging import logger

COLUMN_TO_OMIT_CHECK_FOR_EMPTY_STATEMENT: Final = "trade_date"

INDMONEY_TRANSACTION_STATEMENT_COLUMN_NAMES: Final = [
    "trade_date",
    "entry_type",
    "side",
    "symbol",
    "description",
    "quantity",
    "price",
    "amount",
    "commission",
]

def extract_indmoney_detailed_transactions(
        pdf_path: str,
        month_year: str,
) -> pd.DataFrame:
    if not pdf_path:
        logger.error("Pdf path is not provided")
        raise ValueError("Pdf path is not provided")

    logger.info("parsing INDmoney statement for %s", month_year)

    all_transactions = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()

            # run code only if table extraction was successful
            if table is not None and len(table) > 0:

                # Identify table type using first cell
                first_cell = table[0][0] if table[0] else None

                # -------------------------------
                # TRANSACTION TABLE
                # -------------------------------
                # If the table is Transaction table, capture rows after header
                if first_cell == 'Transaction':
                    # Start capturing from the row after header
                    for row in table[2:]:
                        # Skip empty rows
                        if not any(row):
                            continue

                        # Skip "No record found"
                        if row[0] == 'No record found.':
                            continue

                        all_transactions.append(row)

                # -------------------------------
                # INCOME TABLE (Dividend info)
                # -------------------------------
                # If the table is Income table, capture rows and map schema
                elif first_cell == 'Income':
                    # Skip header row and start from actual data
                    for inc_row in table[2:]:

                        # Skip completely empty rows
                        if not any(inc_row):
                            continue

                        # Skip "No record found"
                        if inc_row[0] == 'No record found.':
                            continue

                        # Skip Journal Entry(Cash) rows (robust whitespace handling)
                        entry_type = inc_row[1]
                        normalized = re.sub(r'\s+', '', entry_type) if entry_type else ""
                        
                        if normalized == 'JournalEntry(Cash)':
                        # Special mapping for cash entries
                            mapped_row = [
                                inc_row[0],                 # Trade Date
                                inc_row[1],                 # Entry Type
                                'deposit',                  # Side
                                'INDMONEY_DEPO',            # Symbol
                                inc_row[3],                 # Description
                                Decimal('1.000000'),        # Quantity
                                Decimal('1.000000'),        # Price
                                inc_row[4],                 # Amount
                                '$ --'                      # Commission
                            ]

                        else:
                            # Map dividend schema → transaction schema
                            mapped_row = [
                                inc_row[0],                 # Trade Date
                                inc_row[1],                 # Entry Type
                                'div',                      # Side
                                inc_row[2],                 # Symbol
                                inc_row[3],                 # Description
                                Decimal('1.000000'),        # Quantity
                                Decimal('1.000000'),        # Price
                                inc_row[4],                 # Amount (Net Amt)
                                '$ --'                      # Commission
                            ]

                        all_transactions.append(mapped_row)

    if not all_transactions:
        logger.warning("No transactions found in INDmoney statement")
        return pd.DataFrame()

    # Convert to DataFrame
    indmoney_transactions_df = pd.DataFrame(
        all_transactions,
        columns=INDMONEY_TRANSACTION_STATEMENT_COLUMN_NAMES
    )

    # length of df is 1 even if there are no transaction hence adding one more condition to check
    cols_to_check = [
        col for col in indmoney_transactions_df.columns
        if col != COLUMN_TO_OMIT_CHECK_FOR_EMPTY_STATEMENT
    ]
    
    # converting all None to NaN
    temp_df = indmoney_transactions_df[cols_to_check].replace('None', pd.NA)

    if temp_df.empty or temp_df.isna().all().all():
        logger.warning("No transactions found in INDmoney statement")
        return pd.DataFrame()

    logger.info(
        "Parsed %d lines of INDmoney transactions for %s",
        len(temp_df),
        month_year
    )

    return indmoney_transactions_df