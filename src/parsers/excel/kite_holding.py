import pandas as pd

from src.common.logging import logger
from src.parsers.excel.kite_holding_period import extract_kite_holding_period

# =========================
# Main parser
# =========================
def extract_kite_holding(excel_path: str) -> tuple[pd.DataFrame, str]:
    if not excel_path:
        logger.error("excel path is not provided")
        raise ValueError("excel path is not provided")
    
    month_year = extract_kite_holding_period(excel_path)

    logger.info("parsing kite holding for %s",month_year)

    holdings_df = pd.read_excel(excel_path)

    # 1. Find header row index
    symbol_rows = holdings_df[holdings_df["Unnamed: 1"].astype(str).str.strip().str.lower() == "symbol"]

    if symbol_rows.empty:
        logger.error(
            "Could not find 'symbol' header in %s. Available values: %s",
            excel_path,
            holdings_df["Unnamed: 1"].dropna().unique()[:10]
        )
        raise ValueError("Excel template changed: 'symbol' header not found")

    header_row_idx = symbol_rows.index[0]

    # 2. Extract headers
    header = holdings_df.loc[header_row_idx].values

    # 3. Build refined dataframe
    holdings_refined_df = holdings_df.loc[header_row_idx + 1:].copy()
    holdings_refined_df.columns = header

    # 4. Cleanup
    holdings_refined_df = holdings_refined_df.dropna(how="all") # dropping the rows having blank for all columns
    holdings_refined_df.reset_index(drop=True, inplace=True) # resetting the index
    holdings_refined_df.columns = holdings_refined_df.columns.astype(str).str.strip() #removeing space from the column names if any
    holdings_refined_df.drop(columns="nan", inplace=True) #drop nan columns

    result = len(holdings_refined_df)
    
    logger.info("Parsed %d lines for %s from kite holding", result,month_year)
    
    # month_year is necessary at the transformation layer
    return (
    holdings_refined_df,
    month_year,
    )

