"""Application configuration and logging setup."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
if LOG_LEVEL not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}:
    LOG_LEVEL = "DEBUG"

LOG_FILE = os.getenv("LOG_FILE", "finder.log")

logger = logging.getLogger("profile-checker")
logger.setLevel(LOG_LEVEL)

ch = logging.StreamHandler()
ch.setLevel(LOG_LEVEL)

fh = logging.FileHandler(LOG_FILE)
fh.setLevel(LOG_LEVEL)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
fh.setFormatter(formatter)

logger.addHandler(ch)
logger.addHandler(fh)
