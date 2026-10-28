import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("/state/logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "app.log"

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

def init_logging(level=logging.DEBUG):
    """
    Initialize logging to both a rotating file and the console.
    """

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT)

    # persistent file logging
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=50_000_000, 
        backupCount=5,
    )
    file_handler.setFormatter(formatter)

    # stdout logging for testing
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
