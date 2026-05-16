import pandas as pd
from sqlalchemy.engine import Engine


class IndmoneyReferenceRepository:
    """Read-side queries required by vest pipelines.

    Why this exists even when loaders already exist:
    - loaders are write-focused (DataFrame -> table inserts)
    - repositories are read/query-focused (table -> DataFrame for business logic)
    - pipeline stays orchestration-centric and avoids embedding large SQL blocks
    """

    def __init__(
            self, 
            read_engine: Engine,
    ):
        self._read_engine = read_engine

    def fetch_deposits_and_compute_exchange_rate(
        self,
    ) -> pd.DataFrame:
        query = """
        SELECT 
            bank.deposit_date,
            ROUND(bank.inr_deposit / indmoney.usd_deposit, 2) AS exchange_rate_1_usd_to_inr,
            indmoney.usd_deposit,
            bank.inr_deposit    
        FROM (
            SELECT 
                deposit_date,
                inr_deposit,
                ROW_NUMBER() OVER (ORDER BY deposit_date) AS rn
            FROM indmoney_deposits_bank_statement
        ) bank
        LEFT JOIN (
            SELECT 
                deposit_date,
                usd_deposit,
                ROW_NUMBER() OVER (ORDER BY deposit_date) AS rn
            FROM indmoney_deposits_indmoney_statement
        ) indmoney
        ON bank.rn = indmoney.rn;
        """
        return pd.read_sql(
            query,
            self._read_engine,
        )
