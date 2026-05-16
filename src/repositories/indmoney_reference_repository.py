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
        """
        here query itself do few checks like if the bank statement deposits and indmoney
        deposits have same number of rows and none of relevent postgres table should be empty
        """
        query = """
            WITH
                counts AS MATERIALIZED (
                    SELECT
                    (SELECT COUNT(*) FROM indmoney_deposits_bank_statement)     AS bank_cnt,
                    (SELECT COUNT(*) FROM indmoney_deposits_indmoney_statement) AS indmoney_cnt
                ),
                guard AS MATERIALIZED (
                    SELECT
                    CASE WHEN bank_cnt = 0
                        THEN CAST(format(
                        'Pre-check failed: indmoney_deposits_bank_statement has 0 records'
                        ) AS INTEGER) END,
                    CASE WHEN indmoney_cnt = 0
                        THEN CAST(format(
                        'Pre-check failed: indmoney_deposits_indmoney_statement has 0 records'
                        ) AS INTEGER) END,
                    CASE WHEN bank_cnt <> indmoney_cnt
                        THEN CAST(format(
                        'Pre-check failed: record count mismatch — indmoney_deposits_bank_statement has %%s rows but indmoney_deposits_indmoney_statement has %%s rows',
                        bank_cnt, indmoney_cnt
                        ) AS INTEGER) END
                    FROM counts
                )
            SELECT
                bank.deposit_date,
                ROUND(bank.inr_deposit / indmoney.usd_deposit, 2) AS exchange_rate_1_usd_to_inr,
                indmoney.usd_deposit,
                bank.inr_deposit
            FROM (
                SELECT deposit_date, inr_deposit, ROW_NUMBER() OVER (ORDER BY deposit_date) AS rn
                FROM indmoney_deposits_bank_statement
            ) bank
            LEFT JOIN (
                SELECT deposit_date, usd_deposit, ROW_NUMBER() OVER (ORDER BY deposit_date) AS rn
                FROM indmoney_deposits_indmoney_statement
            ) indmoney ON bank.rn = indmoney.rn
            CROSS JOIN guard
        """
        return pd.read_sql(
            query,
            self._read_engine,
            parse_dates=["deposit_date"],
        )
