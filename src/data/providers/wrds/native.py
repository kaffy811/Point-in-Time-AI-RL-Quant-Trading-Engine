"""Preserve PostgreSQL cursor types before any pandas inference can alter values."""
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import pyarrow as pa  # type: ignore[import-untyped]


def native_frame(result: Any) -> Any:
    description = result.cursor.description
    rows = result.fetchall()
    types = {
        16: pa.bool_(), 20: pa.int64(), 21: pa.int16(), 23: pa.int32(),
        700: pa.float32(), 701: pa.float64(), 25: pa.string(), 1042: pa.string(),
        1043: pa.string(), 1082: pa.date32(), 1114: pa.timestamp("us"),
        1184: pa.timestamp("us", tz="UTC"), 17: pa.binary(),
    }
    fields = []
    for column in description:
        name, oid, _, _, precision, scale, _ = column
        if oid == 1700:
            # Unconstrained NUMERIC cannot supply an authoritative fixed Arrow schema.
            if precision is None or scale is None or not 1 <= precision <= 76:
                raise ValueError("Unsupported unconstrained PostgreSQL NUMERIC")
            arrow_type = (pa.decimal128(precision, scale) if precision <= 38 else
                          pa.decimal256(precision, scale))
        elif oid in types:
            arrow_type = types[oid]
        else:
            raise ValueError("Unsupported PostgreSQL source type")
        fields.append(pa.field(name, arrow_type, nullable=True))
    frame = pd.DataFrame(rows, columns=[c[0] for c in description], dtype=object)
    frame.attrs["source_arrow_schema"] = pa.schema(fields)
    return frame
