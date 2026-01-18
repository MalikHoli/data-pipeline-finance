
from src.common.logging import logger

def append_rows(
    sheets_service,
    spreadsheet_id: str,
    sheet_name: str,
    rows: list[list]
):
    # Get the Sheets API entry point from the service client
    sheet = sheets_service.spreadsheets()

    # Read column A to determine how many rows are already populated
    # This is used to find the first empty row for appending data
    range_to_check = f"{sheet_name}!A:A"
    result = sheet.values().get(
        spreadsheetId=spreadsheet_id,
        range=range_to_check
    ).execute()


    values = result.get("values", [])
    first_blank_row = len(values) + 1

    # Start writing from the first empty row in column A
    range_to_update = f"{sheet_name}!A{first_blank_row}"

    logger.info(
        "Appending %d rows to sheet '%s' starting at row %d",
        len(rows),
        sheet_name,
        first_blank_row
    )

    try:
        # Actual write operation — network + auth + quota dependent
        sheet.values().update(
            spreadsheetId=spreadsheet_id,
            range=range_to_update,
            valueInputOption="USER_ENTERED",
            body={"values": rows}
        ).execute()

    except Exception:
        # Log once at the boundary where failure actually matters
        logger.error(
            "Failed to append rows to Google Sheet '%s' at row %d",
            sheet_name,
            first_blank_row,
            exc_info=True #exc_info=True tells the logger to include the full exception details in the log.
        )
        raise

############ this is temp code to show how to use it##############################################
# from src.sinks.google_sheets.client import get_sheets_service
# from src.sinks.google_sheets.writer import append_rows
# from src.common.config import (
#     GOOGLE_SHEETS_CREDENTIALS,
#     INVESTMENT_SHEET_ID,
# )

# service = get_sheets_service(GOOGLE_SHEETS_CREDENTIALS)

# append_rows(
#     sheets_service=service,
#     spreadsheet_id=INVESTMENT_SHEET_ID,
#     sheet_name="Investment",
#     rows=sheet_data,
# )