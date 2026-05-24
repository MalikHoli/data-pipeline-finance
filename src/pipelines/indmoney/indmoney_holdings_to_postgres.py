from pathlib import Path

from src.common.db import get_write_engine
from src.common.logging import logger

from src.parsers.pdf.indmoney_statement_period import extract_indmoney_statement_period
from src.parsers.pdf.indmoney_statement_holdings import extract_indmoney_holdings
from src.transformers.indmoney.indmoney_holdings_transformer import transform_indmoney_holdings
from src.loaders.postgres.indmoney.indmoney_statement_holdings_loader import load_indmoney_holdings
from src.pipelines.indmoney.validations import validate_indmoney_holdings_df


def run(
        pdf_path: str | Path,
        dry_run: bool = False,
        run_mode: str = "delta",
        backup_before_truncate: bool = False,
) -> None:
    """
    End-to-end pipeline: parse → transform → validate → load indmoney holdings
    into the postgres table `indmoney_summary_statement`.

    Parameters
    ----------
    pdf_path : str | Path
        Path to the indmoney statement PDF file
    dry_run : bool
        When True, runs all steps except the final postgres write
    run_mode : str
        Loading strategy (e.g. "delta", "full") forwarded to the loader
    backup_before_truncate : bool
        When True, backs up the table before truncating in full-load mode

    Returns
    -------
    None
    """
    logger.info("Starting indmoney holdings pipeline")

    month_year = extract_indmoney_statement_period(pdf_path)

    indmoney_holdings_parsed_df = extract_indmoney_holdings(pdf_path, month_year)

    indmoney_holdings_transformed_df = transform_indmoney_holdings(
        indmoney_holdings_parsed_df,
        month_year,
    )

    validate_indmoney_holdings_df(indmoney_holdings_transformed_df)

    load_indmoney_holdings(
        indmoney_holdings_transformed_df,
        get_write_engine,
        dry_run,
        run_mode,
        backup_before_truncate,
    )

    logger.info("Indmoney holdings pipeline finished successfully | Period: %s", month_year)
