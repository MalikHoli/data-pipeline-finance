import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve project root reliably
BASE_DIR = Path(__file__).resolve().parents[2]

#Explicitly load .env
load_dotenv(BASE_DIR/".env")

# Configuration
#  Database
DB_HOST = os.getenv("DB_HOST","localhost")
DB_PORT = int(os.getenv("DB_PORT","5234"))
DB_NAME = os.getenv("DB_NAME")
DB_WRITE_USER = os.getenv("DB_WRITE_USER")
DB_READ_USER = os.getenv("DB_READ_USER")

#  pdf paths
BANK_STATEMENT_PDF = os.getenv("BANK_STATEMENT_PDF")
VEST_STATEMENT_PDF = os.getenv("VEST_STATEMENT_PDF")
INDMONEY_STATEMENT_PDF = os.getenv("INDMONEY_STATEMENT_PDF")
