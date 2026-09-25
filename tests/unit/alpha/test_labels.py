from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from pathlib import Path

import pytest

from src.alpha.label_artifacts import write_label_artifacts
from src.alpha.labels import ExecutableLabelBuilder
from src.data.pit_store import PITStore
from src.data.schemas import MarketRecord
from src.returns.economic_return import ReturnError, economic_total_return

NY = ZoneInfo("America/New_York")


def bar(day: date, value: float, *, split: float = 1.0, dividend: float = 0.0) -> MarketRecord:
    stamp = datetime.combine(day, time(16, 5), NY)
    return MarketRecord(
        security_id="SEC_TEST", source="synthetic", source_version="v1",
        available_timestamp=stamp, ingested_at=stamp, availability_basis="synthetic",
        trade_date=day, open=value, high=value, low=value, close=value,
        raw_open=value, raw_high=value, raw_low=value, raw_close=value, volume=1000,
        dividend=dividend, split_factor=split, corporate_action_source="synthetic",
        corporate_action_source_version="v1",
    )


def test_open_to_open_return_and_excess_arithmetic():
    records = (bar(date(2024, 1, 2), 100), bar(date(2024, 1, 8), 110))
    assert economic_total_return(records, date(2024, 1, 2), date(2024, 1, 8)) == pytest.approx(.10)
    assert .10 - .04 == pytest.approx(.06)
    assert .05 - .05 == pytest.approx(0.0)


def test_split_is_economic_return_invariant():
    records = (bar(date(2024, 1, 2), 100), bar(date(2024, 1, 5), 50, split=2))
    assert economic_total_return(records, date(2024, 1, 2), date(2024, 1, 5)) == pytest.approx(0.0)
    incomplete = (bar(date(2024, 1, 2), 100), bar(date(2024, 1, 5), 50, split=2))
    with pytest.raises(ReturnError, match="INCOMPLETE_MARKET_COVERAGE"):
        economic_total_return(incomplete, date(2024, 1, 2), date(2024, 1, 5),
                              expected_dates=(date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 5)))


def test_dividend_is_included_and_missing_price_is_invalid():
    records = (bar(date(2024, 1, 2), 100), bar(date(2024, 1, 5), 99, dividend=2))
    assert economic_total_return(records, date(2024, 1, 2), date(2024, 1, 5)) == pytest.approx(.01)
    with pytest.raises(ReturnError, match="MISSING_EXIT_VALUE"):
        economic_total_return((bar(date(2024, 1, 2), 100),), date(2024, 1, 2), date(2024, 1, 5))
    with pytest.raises(ReturnError, match="UNSUPPORTED_CORPORATE_ACTION"):
        economic_total_return((bar(date(2024, 1, 2), 100),
                               bar(date(2024, 1, 5), 100).model_copy(
                                   update={"corporate_action_source": "unsupported-event"})),
                              date(2024, 1, 2), date(2024, 1, 5))


def test_label_module_is_physically_separate_from_features_and_preprocessing():
    source = Path("src/alpha/labels.py").read_text()
    assert "src.features" not in source
    assert "src.preprocessing" not in source


def test_holiday_schedule_and_label_interval(feature_data, config, tmp_path):
    bundle, calendar = feature_data
    store = PITStore(bundle, calendar, config)
    signal = datetime(2024, 7, 3, 16, 10, tzinfo=NY)
    entry, _ = store.next_execution_open(signal)
    assert entry.astimezone(NY).date() == date(2024, 7, 5)
    signals = (datetime(2024, 7, 3, 16, 10, tzinfo=NY),
               datetime(2024, 7, 10, 16, 10, tzinfo=NY))
    frame = ExecutableLabelBuilder(store, dataset_version="label-test").build(signals)
    assert frame.is_forward_looking is True
    assert frame.rows
    assert all(row.label_end_timestamp == row.exit_execution_timestamp for row in frame.rows)
    assert all(row.entry_execution_timestamp < row.exit_execution_timestamp
               for row in frame.rows if row.label_valid)
    write_label_artifacts(frame, tmp_path, git_commit=None, config_hash=config.config_hash(),
                          working_tree_hash="synthetic")
    assert (tmp_path / "label_manifest.json").exists()
    assert (tmp_path / "label_schema.json").exists()


def test_missing_benchmark_is_invalid(feature_data, config):
    bundle, calendar = feature_data
    market = tuple(row for row in bundle.market if row.security_id != "SEC_SPY")
    store = PITStore(bundle.model_copy(update={"market": market}), calendar, config)
    signals = (datetime(2024, 8, 2, 16, 10, tzinfo=NY),
               datetime(2024, 8, 9, 16, 10, tzinfo=NY))
    frame = ExecutableLabelBuilder(store, dataset_version="label-test").build(signals)
    reasons = {row.invalid_reason for row in frame.rows}
    assert "MISSING_BENCHMARK" in reasons
