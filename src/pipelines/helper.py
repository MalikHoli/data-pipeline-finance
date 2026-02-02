import pandas as pd
import numpy as np
from calendar import monthrange
from typing import Final

from src.common.logging import logger

#==========================
# Constants (schema safety)
# These variables are intended to be a constant and must not be reassigned.
# =========================
POSTGRES_OUTPUT_DATE_FORMAT: Final = "%Y-%m-%d"

#==========================================================
def _derive_vest_statement_dates(
        month_year: str,
) -> tuple[
            str,
            str,
            str,
            str,
    ]:
    """
    This helper function takes vest statement period as input
    and provides:
    (vest statement holds a month data)
    current statement first date
    current statement last date
    current statements previous month first date
    current statements previous month last date
    """
    month_str, year_str = month_year.split("/")
    month = int(month_str)
    year = int(year_str)

    # Get actual last day of the month
    last_day = monthrange(year, month)[1]

    current_statement_month_first_date = pd.Timestamp(year, month, 1).strftime(POSTGRES_OUTPUT_DATE_FORMAT)
    current_statement_month_last_date = pd.Timestamp(year, month, last_day).strftime(POSTGRES_OUTPUT_DATE_FORMAT)

    if month == 1:
        # Get December of previous year
        num_days_in_prev_month = monthrange(year - 1, 12)[1]
        # Create last day of previous month
        last_day_prev_month_timestamp = pd.Timestamp(year - 1, 12, num_days_in_prev_month)
        # Create first day of previous month
        first_day_prev_month_timestamp = pd.Timestamp(year - 1, 12, 1)
    else:
        # Get previous month of same year
        num_days_in_prev_month = monthrange(year, month - 1)[1]
        # Create last day of previous month
        last_day_prev_month_timestamp = pd.Timestamp(year, month - 1, num_days_in_prev_month)
        # Create first day of previous month
        first_day_prev_month_timestamp = pd.Timestamp(year, month - 1, 1)
    
    current_statement_Previous_month_first_date = first_day_prev_month_timestamp.strftime(POSTGRES_OUTPUT_DATE_FORMAT)
    current_statement_Previous_month_last_date = last_day_prev_month_timestamp.strftime(POSTGRES_OUTPUT_DATE_FORMAT)

    return(
        current_statement_month_first_date,
        current_statement_month_last_date,
        current_statement_Previous_month_first_date,
        current_statement_Previous_month_last_date,
    )