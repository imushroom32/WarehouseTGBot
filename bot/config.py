import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///warehouse.db')
MANAGER_TELEGRAM_ID = os.getenv('MANAGER_TELEGRAM_IDS')

MANAGER_TELEGRAM_IDS = [id for id in os.getenv("MANAGER_TELEGRAM_IDS", "").split(",")]
