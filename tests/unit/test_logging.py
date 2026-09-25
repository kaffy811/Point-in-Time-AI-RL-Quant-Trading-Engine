import logging

from src.utils.logging import configure_logging


def test_logging_setup_is_idempotent_and_preserves_root() -> None:
    root_handlers = list(logging.getLogger().handlers)
    configure_logging()
    configure_logging()
    assert len(logging.getLogger("quant_engine").handlers) == 1
    assert logging.getLogger().handlers == root_handlers
    assert not logging.getLogger("quant_engine").propagate
