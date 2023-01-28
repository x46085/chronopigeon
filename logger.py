import logging
import os


# Log to the screen
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter(
    '%(asctime)s: "%(filename)s" (line: %(lineno)d) - %(levelname)s ' +
    '%(message)s'
))

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOGLEVEL", "INFO"))
logger.addHandler(stream_handler)
