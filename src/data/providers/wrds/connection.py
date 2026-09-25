"""Interactive local credentials; no credential files, SQL logs, or raw errors."""
from collections.abc import Callable
import getpass
import sys
import time
from typing import Any

from .native import native_frame


class ProviderError(RuntimeError):
    """Sanitized provider failure; deliberately excludes upstream exception text."""


def interactive_factory() -> Callable[[], Any]:
    if not sys.stdin.isatty():
        raise ProviderError("WRDS authentication requires the user's local interactive terminal")
    username = input("WRDS username: ").strip()
    password = getpass.getpass("WRDS password (memory only): ")
    if not username or not password:
        raise ProviderError("WRDS authentication requires nonempty credentials")

    def connect() -> Any:
        import sqlalchemy as sa
        import wrds  # type: ignore[import-untyped]

        # Avoid WRDS.connect(), which offers to persist plaintext .pgpass credentials.
        db = wrds.Connection(autoconnect=False, verbose=False)
        url = sa.URL.create("postgresql+psycopg2", username=username, password=password,
                            host="wrds-pgdata.wharton.upenn.edu", port=9737, database="wrds")
        db.engine = sa.create_engine(
            url, echo=False, hide_parameters=True, isolation_level="AUTOCOMMIT",
            connect_args={"sslmode": "require", "connect_timeout": 30,
                          "options": "-c default_transaction_read_only=on -c statement_timeout=60000"},
        )
        try:
            db.connection = db.engine.connect()
        except Exception:
            db.engine.dispose()
            raise
        return db
    return connect


def transient(exc: Exception) -> bool:
    original = getattr(exc, "orig", exc)
    code = getattr(original, "pgcode", None)
    # Auth, SQL, entitlement, and cancellation errors are never retried.
    return bool(code and (code.startswith("08") or code in {"57P01", "57P02", "57P03"})) or (
        code is None and (isinstance(exc, (ConnectionError, TimeoutError))
                         or bool(getattr(exc, "connection_invalidated", False)))
    )


class Connector:
    def __init__(self, factory: Callable[[], Any], attempts: int = 3,
                 sleep: Callable[[float], None] = time.sleep):
        if not 1 <= attempts <= 5:
            raise ValueError("Attempts must be between 1 and 5")
        self.factory, self.attempts, self.sleep = factory, attempts, sleep

    def query(self, sql: str, params: dict[str, Any]) -> Any:
        for attempt in range(self.attempts):
            db = None
            try:
                db = self.factory()
                with db.connection.exec_driver_sql(sql, params) as result:
                    return native_frame(result)
            except Exception as exc:
                if not transient(exc) or attempt + 1 == self.attempts:
                    raise ProviderError("WRDS request failed; check local authentication, "
                                        "entitlement, schema, and connectivity") from None
            finally:
                if db is not None:
                    try:
                        db.close()
                    except Exception:
                        pass  # Never expose driver messages or obscure an earlier failure.
            self.sleep(float(2 ** attempt))
        raise AssertionError("unreachable")

    def health(self) -> bool:
        result = self.query("SELECT 1 AS ok", {})
        return bool(result.iloc[0]["ok"] == 1)
