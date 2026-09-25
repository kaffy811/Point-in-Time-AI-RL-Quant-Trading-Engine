"""Explicit logging setup without import-time side effects."""
import logging
import time


def configure_logging() -> None:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(name)s %(message)s")
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    logger = logging.getLogger("quant_engine")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
