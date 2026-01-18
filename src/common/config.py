import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve project root reliably
BASE_DIR = Path(__file__).resolve().parents[2]

#Explicitly load .env
load_dotenv(BASE_DIR/".env")

#  Database
DB_HOST = os.getenv("DB_HOST","localhost")
DB_PORT = int(os.getenv("DB_PORT","5234"))
DB_NAME = os.getenv("DB_NAME")
DB_WRITE_USER = os.getenv("DB_WRITE_USER")
DB_READ_USER = os.getenv("DB_READ_USER")

#  pdf paths
BANK_STATEMENT_DIRECTORY = os.getenv("BANK_STATEMENT_DIRECTORY")
VEST_STATEMENT_DIRECTORY = os.getenv("VEST_STATEMENT_DIRECTORY")
INDMONEY_STATEMENT_DIRECTORY = os.getenv("INDMONEY_STATEMENT_DIRECTORY")

# google speadsheet
GSPREAD_SERVICE_ACCOUNT_FILE = os.getenv("GSPREAD_SERVICE_ACCOUNT_FILE")
INVESTMENT_SHEET_ID = os.getenv("INVESTMENT_SHEET_ID")