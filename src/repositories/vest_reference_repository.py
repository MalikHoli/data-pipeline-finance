import pandas as pd
from sqlalchemy.engine import Engine


class VestReferenceRepository:
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

    def fetch_prev_month_end_balance(
        self,
        prev_month_last_date: str,
    ) -> pd.DataFrame:
        query = """
        SELECT balance
        FROM vest_month_end_balance
        WHERE date=%(last_day_prev_month)s
        """
        return pd.read_sql(
            query,
            self._read_engine,
            params={"last_day_prev_month": prev_month_last_date},
        )

    def fetch_curr_month_wallet_credits(
        self,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        query = """
        SELECT amount
        FROM vest_detailed_statement
        WHERE activity='CDEP' AND trade_date BETWEEN %(start_date)s AND %(end_date)s
        ORDER BY trade_date ASC
        """
        return pd.read_sql(
            query,
            self._read_engine,
            params={
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    def fetch_curr_month_exchange_rates(
        self,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        query = """
        SELECT exchange_rate_1_usd_to_inr FROM vest_usd_to_inr_deposit_exch_rate
        WHERE deposit_date BETWEEN %(start_date)s AND %(end_date)s
        ORDER BY deposit_date ASC
        """
        return pd.read_sql(
            query,
            self._read_engine,
            params={
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    def fetch_curr_and_prev_exchange_rates(
        self,
        prev_month_start_date: str,
        prev_month_end_date: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        query = """
        SELECT exchange_rate_1_usd_to_inr
        FROM (
            SELECT deposit_date, exchange_rate_1_usd_to_inr
            FROM vest_usd_to_inr_deposit_exch_rate
            WHERE deposit_date BETWEEN %(start_date)s AND %(end_date)s
            UNION ALL
            SELECT deposit_date, exchange_rate_1_usd_to_inr
            FROM (
                SELECT deposit_date, exchange_rate_1_usd_to_inr
                FROM vest_usd_to_inr_deposit_exch_rate
                WHERE deposit_date = (
                    SELECT COALESCE(
                        (
                            SELECT MAX(deposit_date)
                            FROM vest_usd_to_inr_deposit_exch_rate
                            WHERE deposit_date BETWEEN %(prev_month_start_date)s AND %(prev_month_end_date)s
                        ),
                        (
                            SELECT MAX(deposit_date)
                            FROM vest_usd_to_inr_deposit_exch_rate
                            WHERE deposit_date <= %(prev_month_end_date)s
                        )
                    )
                )
                ORDER BY ctid DESC
                LIMIT 1
            ) t
        ) AS combined_rates
        ORDER BY deposit_date ASC;
        """
        return pd.read_sql(
            query,
            self._read_engine,
            params={
                "prev_month_start_date": prev_month_start_date,
                "prev_month_end_date": prev_month_end_date,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
