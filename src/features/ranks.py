"""Optional same-signal percentile ranks; raw features and model whitelist are untouched."""
from dataclasses import dataclass
from datetime import datetime
from itertools import groupby

from src.features.contracts import FeatureFrame
from src.features.registry import RAW_FEATURES


@dataclass(frozen=True)
class RankValue:
    security_id: str
    signal_timestamp: datetime
    name: str
    value: float | None
    universe_security_ids: tuple[str, ...]


def cross_sectional_ranks(frame: FeatureFrame, names: tuple[str, ...]) -> tuple[RankValue, ...]:
    if len(set(names)) != len(names) or any(name not in RAW_FEATURES for name in names):
        raise ValueError("rank views require unique registered raw feature names")
    output = []
    for snapshot in frame.snapshots:
        rows = frame.rows_at(snapshot.signal_timestamp)
        for name in names:
            values = {row.security_id: next(v.value for v in row.values if v.name == name)
                      for row in rows}
            finite = sorted((value, sid) for sid, value in values.items() if value is not None)
            ranks: dict[str, float] = {}
            offset = 0
            for _, group in groupby(finite, key=lambda item: item[0]):
                tied = list(group)
                average_rank = (offset + 1 + offset + len(tied)) / 2
                for _, sid in tied:
                    ranks[sid] = average_rank / len(finite)
                offset += len(tied)
            for sid in sorted(values):
                output.append(RankValue(sid, snapshot.signal_timestamp, name + "_xs_rank",
                                        ranks.get(sid), snapshot.security_ids))
    return tuple(output)
