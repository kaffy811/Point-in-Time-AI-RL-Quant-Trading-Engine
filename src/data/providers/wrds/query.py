"""Allowlisted, parameterized small-sample extraction specifications."""
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
from typing import Any

TABLES = frozenset({
    "crsp.dsf_v2", "crsp.dsp500list_v2", "crsp.stksecurityinfohist",
    "crsp.stkdistributions", "crsp.stkdelists", "wrdssec_common.wciklink_cusip",
})


def identifier(value: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value):
        raise ValueError("Invalid SQL identifier")
    return '"' + value + '"'


@dataclass(frozen=True)
class QuerySpec:
    table: str
    columns: tuple[str, ...]
    identity_column: str
    identities: tuple[str | int, ...]
    date_column: str | None = None
    start: str | None = None
    end: str | None = None
    max_rows: int = 1000

    def compile(self) -> tuple[str, dict[str, Any]]:
        if self.table not in TABLES:
            raise ValueError("Source table is not allowlisted")
        if not 1 <= self.max_rows <= 10000 or not 1 <= len(self.identities) <= 10:
            raise ValueError("Extraction requires 1–10 identities and 1–10000 rows")
        if self.identity_column != ("cusip" if self.table.startswith("wrdssec") else "permno"):
            raise ValueError("Extraction must be bounded by PERMNO or WRDS CUSIP")
        if any(type(x) not in (str, int) or not str(x) or len(str(x)) > 32
               for x in self.identities):
            raise ValueError("Invalid identity parameter")
        if not self.columns or len(set(self.columns)) != len(self.columns):
            raise ValueError("Explicit unique columns required")
        if self.identity_column not in self.columns:
            raise ValueError("Identity column must be retained")
        predicate = ""
        params: dict[str, Any] = {"identities": tuple(sorted(set(self.identities), key=str)),
                                  "limit": self.max_rows + 1}
        if self.date_column:
            if self.date_column not in self.columns or not self.start or not self.end:
                raise ValueError("Date filter requires retained column and both endpoints")
            if date.fromisoformat(self.start) >= date.fromisoformat(self.end):
                raise ValueError("Date interval must be nonempty [start, end)")
            predicate = (f" AND {identifier(self.date_column)} >= %(start)s"
                         f" AND {identifier(self.date_column)} < %(end)s")
            params.update(start=self.start, end=self.end)
        elif self.start or self.end:
            raise ValueError("Date endpoints require a date column")
        sql = Path(__file__).with_name("sql").joinpath("sample.sql").read_text().format(
            columns=", ".join(identifier(c) for c in self.columns),
            table=".".join(identifier(c) for c in self.table.split(".")),
            identity_column=identifier(self.identity_column), date_predicate=predicate,
        )
        return sql, params
