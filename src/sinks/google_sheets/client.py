from google.oauth2 import service_account
from googleapiclient.discovery import build
from src.common.logging import logger
from googleapiclient.errors import GoogleAPIError

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def get_sheets_service(service_account_file: str):
    logger.info("Starting Google Sheets service initialization")

    if not service_account_file:
        logger.error("Service account file path is missing")
        raise ValueError("Service account file path must be provided")

    try:
        # Load credentials from service account JSON (no network call yet)
        logger.info("Loading service account credentials")
        creds = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=SCOPES
        )

        # Build the Sheets API client (lazy — no API call until used)
        logger.info("Creating Google Sheets API client")
        service = build("sheets", "v4", credentials=creds)

        # Success path: return fully initialized client
        logger.info("Google Sheets service created successfully")
        return service

    except FileNotFoundError:
        # Configuration or deployment issue (wrong path, missing file)
        logger.error("Service account file not found", exc_info=True)
        raise # Re-raise so caller knows this is a hard failure

    except GoogleAPIError:
        # Google-side failure (auth, permissions, quota, API issues)
        logger.error("Google API error while creating Sheets service", exc_info=True)
        raise

    except Exception:
        # Safety net for unexpected bugs; should never be silent
        logger.error("Unexpected error while creating Sheets service", exc_info=True)
        raise