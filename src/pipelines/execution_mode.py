from enum import Enum

class LoadExecutionMode(Enum):
    """
     Explicit execution modes for the vest/indmoney pipeline.
     This enum intentionally represents a closed set of valid intents
    """
    LOAD_ALL = "load_all"
    LOAD_MONTH_END_ONLY = "load_month_end_only"
    LOAD_TRANSFORMED_TRATRANSACTIONS_ONLY = "load_transformed_transactions_only"