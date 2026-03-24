from pathlib import Path

from src.parsers.pdf.vest_statement_period import extract_vest_statement_period
from src.parsers.pdf.vest_statement_holdings import extract_vest_holdings
from src.transformers.vest.vest_holdings_transformer import transform_vest_holdings
from src.loaders.postgres.vest.vest_statement_holdings_loader import load_vest_holdings
from src.pipelines.vest.validations import validate_vest_holdings_df

from src.common.db import get_write_engine
from src.common.logging import logger

def run(
        pdf_path: Path,
        dry_run: bool = False,
        run_mode: str = "delta",
        backup_before_truncate: bool = False,
) -> None:
    """
    Runs the vest holding pdf → postgres pipeline.

    Parameters
    ----------
    excel_path : Path
        Path to vest pdf
    dry_run : bool
        If True, executes full pipeline except postgres write
    run_mode : str
        "delta" appends rows. "full" enables one-time pre-load truncate.
    backup_before_truncate : bool
        Whether to create a timestamped backup table before truncate in full mode.
    """
    logger.info("Starting vest holdings pipeline")

    month_year = extract_vest_statement_period(pdf_path)

    vest_holdings_df = extract_vest_holdings(pdf_path,month_year)

    vest_holdings_transformed_df = transform_vest_holdings(
        vest_holdings_df,
        month_year
    )

    validate_vest_holdings_df(vest_holdings_transformed_df)

    load_vest_holdings(
        vest_holdings_transformed_df,
        get_write_engine,
        dry_run,
        run_mode,
        backup_before_truncate,
    )

    logger.info("vest holdings pipeline finished successfully | Period: %s", month_year)        
