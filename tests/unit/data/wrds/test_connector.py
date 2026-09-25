"""Synthetic mocked provider tests: no live authentication or licensed records."""
from datetime import date
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pyarrow.parquet as pq
import pytest

from src.data.providers.wrds.connection import Connector, ProviderError, interactive_factory
from src.data.providers.wrds.extract import extract, json_bytes
from src.data.providers.wrds.query import QuerySpec, TABLES


def spec(**changes):
    values = dict(table="crsp.dsf_v2", columns=("permno", "date", "price"),
                  identity_column="permno", identities=(999999,), date_column="date",
                  start="2020-01-01", end="2020-02-01", max_rows=2)
    values.update(changes)
    return QuerySpec(**values)


def connection():
    db = Mock()
    result_context = Mock()
    result_context.__enter__ = Mock(return_value=db)
    result_context.__exit__ = Mock(return_value=False)
    db.connection.exec_driver_sql.return_value = result_context
    db.raw_sql.return_value = pd.DataFrame({
        "permno": [999999, 999999], "date": [date(2020, 1, 2), date(2020, 1, 3)],
        "price": [12.5, None],
    })
    return db


@pytest.fixture(autouse=True)
def native_adapter_mock(monkeypatch):
    def adapt(result):
        return result.raw_sql()
    monkeypatch.setattr("src.data.providers.wrds.connection.native_frame", adapt)
    # Lifecycle units mock the adapter; test_native.py exercises the real conversion.


def test_native_export_hashes_and_immutable_version(tmp_path):
    db = connection()
    path = extract(Connector(lambda: db), spec(), "v1", tmp_path)
    manifest = json.loads(path.read_text())
    parquet = path.parent / manifest["content_file"]
    assert pq.read_table(parquet).num_rows == 2
    assert pq.read_table(parquet)["price"].null_count == 1
    assert manifest["content_hash"] == hashlib.sha256(parquet.read_bytes()).hexdigest()
    assert manifest["schema_hash"] == hashlib.sha256(json_bytes(manifest["schema"])).hexdigest()
    sql, params = spec().compile()
    assert manifest["query_hash"] == hashlib.sha256(
        json_bytes({"sql": sql, "params": params})).hexdigest()
    assert manifest["date_coverage"]["min"] == "2020-01-02"
    assert manifest["retrieval_timestamp"].endswith("+00:00")
    with pytest.raises(FileExistsError):
        extract(Connector(lambda: db), spec(), "v1", tmp_path)
    assert db.raw_sql.call_count == 1
    db.close.assert_called_once()
    assert db.connection.exec_driver_sql.call_args.args == (sql, params)


@pytest.mark.parametrize("table", sorted(TABLES))
def test_initial_table_templates(table):
    key = "cusip" if table.startswith("wrdssec") else "permno"
    sql, params = spec(table=table, identity_column=key, columns=(key,),
                       date_column=None, start=None, end=None).compile()
    assert "LIMIT %(limit)s" in sql
    assert params["limit"] == 3


@pytest.mark.parametrize("changes", [
    {"table": "other.table"}, {"columns": ("permno", "x;drop table t")},
    {"identities": ()}, {"identities": tuple(range(11))}, {"max_rows": 10001},
    {"identity_column": "ticker"}, {"start": "2020-03-01"},
    {"date_column": None}, {"columns": ("price",)}, {"end": None},
])
def test_bad_specs_fail_before_query(changes):
    with pytest.raises(ValueError):
        spec(**changes).compile()


def test_parameters_not_interpolated_and_hash_changes():
    value = "x' OR 1=1 --"
    sql, params = spec(identities=(value,)).compile()
    assert value not in sql
    assert params["identities"] == (value,)
    assert spec(identities=(2, 1)).compile() == spec(identities=(1, 2)).compile()
    assert spec().compile() != spec(end="2020-03-01").compile()


def test_retry_reconnects_closes_and_sanitizes():
    first, second = connection(), connection()
    first.raw_sql.side_effect = ConnectionError("sensitive upstream diagnostic")
    factory = Mock(side_effect=[first, second])
    sleep = Mock()
    Connector(factory, sleep=sleep).query("SELECT 1", {})
    assert factory.call_count == 2
    first.close.assert_called_once()
    second.close.assert_called_once()
    sleep.assert_called_once_with(1.0)
    db = connection()
    db.raw_sql.side_effect = PermissionError("sensitive upstream diagnostic")
    with pytest.raises(ProviderError, match="WRDS request failed") as error:
        Connector(lambda: db).query("SELECT 1", {})
    assert "sensitive" not in str(error.value)
    assert db.raw_sql.call_count == 1


def test_retry_exhaustion():
    factory = Mock(side_effect=ConnectionError("sensitive"))
    with pytest.raises(ProviderError):
        Connector(factory, sleep=Mock()).query("SELECT 1", {})
    assert factory.call_count == 3


def test_overflow_has_no_completion_manifest(tmp_path):
    with pytest.raises(ValueError, match="cap exceeded"):
        extract(Connector(connection), spec(max_rows=1), "v1", tmp_path)
    assert not list(tmp_path.rglob("manifest.json"))
    assert not list(tmp_path.rglob("*.parquet"))


def test_noninteractive_auth_rejected(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(ProviderError, match="interactive"):
        interactive_factory()


def test_health_and_no_entitlement_claim():
    db = Mock()
    result_context = Mock()
    result_context.__enter__ = Mock(return_value=db)
    result_context.__exit__ = Mock(return_value=False)
    db.connection.exec_driver_sql.return_value = result_context
    db.raw_sql.return_value = pd.DataFrame({"ok": [1]})
    assert Connector(lambda: db).health()
    assert db.connection.exec_driver_sql.call_args.args[0] == "SELECT 1 AS ok"


def test_cli_plan_is_offline(tmp_path, monkeypatch, capsys):
    from dataclasses import asdict
    from src.data.providers.wrds.cli import main
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(asdict(spec())))
    monkeypatch.setattr("sys.argv", ["wrds-ingest", "plan", "--spec", str(path)])
    monkeypatch.setattr("src.data.providers.wrds.cli.interactive_factory",
                        Mock(side_effect=AssertionError("must stay offline")))
    main()
    assert json.loads(capsys.readouterr().out)["parameters"]["limit"] == 3


def test_research_modules_do_not_import_live_provider():
    import ast
    for path in Path("src").rglob("*.py"):
        if "providers" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            names = ([node.module or ""] if isinstance(node, ast.ImportFrom) else
                     [a.name for a in node.names] if isinstance(node, ast.Import) else [])
            assert not any(n == "wrds" or n.startswith("src.data.providers.wrds")
                           for n in names), path


def test_auth_uses_memory_only_and_readonly_connection(monkeypatch):
    import sqlalchemy
    import wrds
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "synthetic-user")
    # Runtime-generated sentinel, not a real or embedded WRDS credential.
    import secrets
    sentinel = secrets.token_urlsafe(24)
    monkeypatch.setattr("getpass.getpass", lambda _: sentinel)
    db, engine = Mock(), Mock()
    constructor = Mock(return_value=db)
    create_engine = Mock(return_value=engine)
    monkeypatch.setattr(wrds, "Connection", constructor)
    monkeypatch.setattr(sqlalchemy, "create_engine", create_engine)
    assert interactive_factory()() is db
    constructor.assert_called_once_with(autoconnect=False, verbose=False)
    db.connect.assert_not_called()
    db.create_pgpass_file.assert_not_called()
    kwargs = create_engine.call_args.kwargs
    assert kwargs["hide_parameters"] is True
    assert "default_transaction_read_only=on" in kwargs["connect_args"]["options"]
    assert sentinel not in repr(create_engine.call_args.args[0])


def test_empty_native_schema_and_missing_column_rejection(tmp_path):
    db = connection()
    db.raw_sql.return_value = db.raw_sql.return_value.iloc[:0].astype({"date": "datetime64[ns]"})
    path = extract(Connector(lambda: db), spec(), "empty", tmp_path)
    manifest = json.loads(path.read_text())
    assert manifest["row_count"] == 0
    assert manifest["date_coverage"]["min"] is None
    db.raw_sql.return_value = pd.DataFrame({"wrong": [1]})
    with pytest.raises(ValueError, match="columns"):
        extract(Connector(lambda: db), spec(), "wrong", tmp_path)


def test_cli_failure_never_prints_upstream_exception(monkeypatch, capsys):
    from src.data.providers.wrds.cli import main
    monkeypatch.setattr("sys.argv", ["wrds-ingest", "health"])
    monkeypatch.setattr("src.data.providers.wrds.cli.interactive_factory",
                        Mock(side_effect=ValueError("sensitive diagnostic")))
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert "sensitive" not in capsys.readouterr().err


def test_link_strings_and_decimal_values_are_not_coerced(tmp_path):
    from decimal import Decimal
    db = Mock()
    result_context = Mock()
    result_context.__enter__ = Mock(return_value=db)
    result_context.__exit__ = Mock(return_value=False)
    db.connection.exec_driver_sql.return_value = result_context
    db.raw_sql.return_value = pd.DataFrame({
        "cusip": ["001234567"], "cik": ["0000012345"], "amount": [Decimal("1.123456789")],
    })
    query = QuerySpec("wrdssec_common.wciklink_cusip", ("cusip", "cik", "amount"),
                      "cusip", ("001234567",))
    path = extract(Connector(lambda: db), query, "strings", tmp_path)
    rows = pq.read_table(path.parent / "part-00000.parquet").to_pylist()
    assert rows == [{"cusip": "001234567", "cik": "0000012345",
                     "amount": Decimal("1.123456789")}]
