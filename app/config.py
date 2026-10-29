import os
from dotenv import load_dotenv

load_dotenv()


def get_db_path() -> str:
    """Return the configured SQLite database file path from environment."""
    return os.environ.get("DATABASE_PATH", "fleetwise.db")


def get_host() -> str:
    return os.environ.get("HOST", "127.0.0.1")


def get_port() -> int:
    return int(os.environ.get("PORT", "8000"))

