"""Real conversion path, mocked DBAPI records/OIDs; no pandas adapter mock."""
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, MagicMock
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import wrds

from src.data.providers.wrds.connection import Connector, ProviderError
from src.data.providers.wrds.extract import extract
from src.data.providers.wrds.query import QuerySpec


def provider(rows, columns):
    db = wrds.Connection(autoconnect=False, verbose=False)
    db.engine = Mock()
    db.connection = Mock()
    result = MagicMock()
    result.__enter__.return_value = result
    result.cursor.description = columns
    result.fetchall.return_value = rows
    db.connection.exec_driver_sql.return_value = result
    return db


def description(name, oid, precision=None, scale=None):
    return (name, oid, None, None, precision, scale, None)


@pytest.mark.parametrize("empty", [False, True])
def test_native_date_decimal_nullable_bigint_and_empty_schema(tmp_path, empty):
    columns = [description("permno", 23), description("day", 1082),
               description("amount", 1700, 20, 9), description("big", 20),
               description("identifier", 1043)]
    rows = [] if empty else [(999999, date(2020, 1, 2), Decimal("1.123456789"),
                             9007199254740993, "0000012345"),
                            (999999, None, None, None, None)]
    db = provider(rows, columns)
    spec = QuerySpec("crsp.dsf_v2", tuple(c[0] for c in columns), "permno", (999999,),
                     "day", "2020-01-01", "2020-02-01")
    path = extract(Connector(lambda: db), spec, "native", tmp_path)
    table = pq.read_table(path.parent / "part-00000.parquet")
    assert table.schema.field("amount").type == pa.decimal128(20, 9)
    assert table.schema.field("day").type == pa.date32()
    assert table.schema.field("big").type == pa.int64()
    assert table.to_pylist() == [dict(zip(spec.columns, row)) for row in rows]
    assert json.loads(path.read_text())["date_coverage"]["min"] == (
        None if empty else "2020-01-02")
    db.connection.close.assert_called_once()


def test_all_null_retains_native_schema():
    db = provider([(None, None, None, None)], [description("d", 1082),
                  description("n", 1700, 12, 2), description("i", 20), description("b", 16)])
    frame = Connector(lambda: db).query("SELECT bounded_columns", {})
    table = pa.Table.from_pandas(frame, schema=frame.attrs["source_arrow_schema"],
                                preserve_index=False)
    assert table.schema.types == [pa.date32(), pa.decimal128(12, 2), pa.int64(), pa.bool_()]
    assert all(c.null_count == 1 for c in table.columns)


@pytest.mark.parametrize("column", [description("unknown", 99999),
                                     description("unconstrained", 1700)])
def test_unsupported_source_types_fail_closed(column):
    db = provider([(None,)], [column])
    with pytest.raises(ProviderError):
        Connector(lambda: db).query("SELECT bounded_columns", {})
    db.connection.close.assert_called_once()


def test_timestamp_and_binary_native_types():
    stamp = datetime(2020, 1, 2, 12, 0, tzinfo=timezone.utc)
    db = provider([(stamp, b"raw", 1.25)], [description("ts", 1184),
                  description("bytes", 17), description("value", 701)])
    frame = Connector(lambda: db).query("SELECT bounded_columns", {})
    table = pa.Table.from_pandas(frame, schema=frame.attrs["source_arrow_schema"],
                                preserve_index=False)
    assert table.to_pylist() == [{"ts": stamp, "bytes": b"raw", "value": 1.25}]
