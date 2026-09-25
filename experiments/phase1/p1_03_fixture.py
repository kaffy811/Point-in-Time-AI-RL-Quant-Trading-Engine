"""Deterministic artificial canonical data; never a production calendar/provider substitute."""
from datetime import date, datetime, time, timedelta
from math import exp, sin
from zoneinfo import ZoneInfo

from src.data.schemas import Calendar, DataBundle

NY = ZoneInfo("America/New_York")


def timestamp(day: date, hour: int = 16, minute: int = 5) -> str:
    return datetime.combine(day, time(hour, minute), NY).isoformat()


def fixture() -> tuple[DataBundle, Calendar]:
    start, finish = date(2022, 1, 3), date(2025, 2, 7)
    days = []
    day = start
    while day <= finish:
        if day.weekday() < 5 and day not in (date(2024, 7, 4),):
            days.append(day)
        day += timedelta(days=1)
    ingestion = "2025-02-10T12:00:00-05:00"

    def base(sid: str, available: str) -> dict[str, object]:
        return dict(security_id=sid, source="synthetic-p1-03", source_version="v1",
                    available_timestamp=available, ingested_at=ingestion, availability_basis="synthetic")

    def security(sid: str, ticker: str, since: date, until: date | None = None) -> dict[str, object]:
        return dict(**base(sid, timestamp(since, 0, 0)), ticker=ticker, exchange="XNAS",
                    company_name="Artificial " + sid, sector="Synthetic", industry="Synthetic",
                    valid_from=timestamp(since, 0, 0), valid_to=timestamp(until, 0, 0) if until else None,
                    end_available_timestamp=timestamp(until, 0, 0) if until else None)

    def member(sid: str, since: date, until: date | None = None) -> dict[str, object]:
        return dict(**base(sid, timestamp(since, 0, 0)), index_id="sp500",
                    effective_from=timestamp(since, 0, 0),
                    effective_to=timestamp(until, 0, 0) if until else None,
                    end_available_timestamp=timestamp(until, 0, 0) if until else None)

    change = date(2024, 6, 10)
    securities = [security("SEC_ALPHA", "OLD", start, change),
                  security("SEC_ALPHA", "NEW", change), security("SEC_ENTRY", "ENT", start),
                  security("SEC_EXIT", "EXT", start), security("SEC_SHORT", "SHORT", start),
                  security("SEC_SPY", "SPY", start)]
    memberships = [member("SEC_ALPHA", start), member("SEC_ENTRY", date(2024, 7, 1)),
                   member("SEC_EXIT", start, date(2024, 9, 1)), member("SEC_SHORT", start)]
    market = []
    sessions = []
    for index, day in enumerate(days):
        close_hour = 13 if day == date(2024, 7, 3) else 16
        sessions.append(dict(trade_date=str(day), open_timestamp=timestamp(day, 9, 30),
                             close_timestamp=timestamp(day, close_hour, 0)))
        for sid in ("SEC_ALPHA", "SEC_ENTRY", "SEC_EXIT", "SEC_SHORT", "SEC_SPY"):
            if sid == "SEC_SHORT" and index < len(days) - 25:
                continue
            market_log = .0005 * index + .003 * sin(index * .17)
            value = 100 * exp(market_log if sid == "SEC_SPY" else 2 * market_log - .0002 * index)
            prices = {name: value for name in ("open", "high", "low", "close", "raw_open",
                                               "raw_high", "raw_low", "raw_close")}
            market.append(dict(**base(sid, timestamp(day, close_hour, 5)), trade_date=str(day),
                               **prices, volume=10000., dividend=0., split_factor=1.,
                               corporate_action_source="synthetic", corporate_action_source_version="v1"))
    fundamentals = []
    flows = {"common_net_income": (10., 20.), "net_income": (12., 22.), "revenue": (100., 200.),
             "operating_income": (20., 30.), "operating_cash_flow": (30., 40.),
             "capital_expenditures": (5., 10.), "gross_profit": (50., 60.),
             "diluted_eps": (1., 2.)}
    for sid in ("SEC_ALPHA", "SEC_ENTRY", "SEC_EXIT"):
        for year in (2023, 2024):
            for quarter, end in enumerate((date(year, 3, 31), date(year, 6, 30),
                                           date(year, 9, 30), date(year, 12, 31)), start=1):
                qstart = date(year, 3 * (quarter - 1) + 1, 1)
                accepted = timestamp(end + timedelta(days=10), 16, 37)
                for concept, annual_bases in flows.items():
                    increment = .1 if concept == "diluted_eps" else 1.
                    if concept == "diluted_eps":
                        # EPS is a ratio, so this fixture supplies direct quarter
                        # observations rather than non-additive YTD EPS.
                        value = annual_bases[year - 2023] + increment * quarter
                    else:
                        value = sum(annual_bases[year - 2023] + increment * i for i in range(quarter))
                    revision = f"{sid}:{concept}:{year}:{quarter}:r1"
                    fundamentals.append(dict(
                            **base(sid, accepted), fiscal_period_start=(
                                str(qstart) if concept == "diluted_eps" else f"{year}-01-01"
                            ),
                        fiscal_period_end=str(end), filing_accepted_at=accepted, form_type="10-K"
                        if quarter == 4 else "10-Q", accession_number=f"SYN-{year}-{quarter}",
                        fact_name=concept, value=value, unit="USD/share" if concept == "diluted_eps"
                        else "USD", period_type="duration", revision_id=revision,
                        supersedes_revision_id=None, fiscal_year=year, fiscal_quarter=quarter,
                        fiscal_year_start=f"{year}-01-01", fiscal_quarter_start=str(qstart),
                        duration_kind="quarter" if concept == "diluted_eps" else "ytd",
                        share_basis_date=str(end) if concept == "diluted_eps"
                        else None, equity_scope="single_class"))
        for year in (2022, 2023, 2024):
            for concept, value in {"assets": 1000. + 100 * (year - 2022),
                                   "common_equity": 500. + 100 * (year - 2022),
                                   "total_debt": 200., "current_debt": 50., "long_term_debt": 150.,
                                   "shares_outstanding": 100.}.items():
                end = date(year, 12, 31)
                accepted = timestamp(end + timedelta(days=10), 16, 37)
                fundamentals.append(dict(
                    **base(sid, accepted), fiscal_period_start=None, fiscal_period_end=str(end),
                    filing_accepted_at=accepted, form_type="10-K", accession_number=f"SYN-{year}-FY",
                    fact_name=concept, value=value, unit="shares" if concept == "shares_outstanding"
                    else "USD", period_type="instant", revision_id=f"{sid}:{concept}:{year}:r1",
                    supersedes_revision_id=None, equity_scope="single_class"))
    original = next(r for r in fundamentals if r["security_id"] == "SEC_ALPHA"
                    and r["fact_name"] == "common_net_income" and r.get("fiscal_year") == 2024
                    and r.get("fiscal_quarter") == 4)
    amendment = dict(original)
    amendment.update(value=90., revision_id="SEC_ALPHA:common_net_income:2024:4:r2",
                     supersedes_revision_id=original["revision_id"],
                     available_timestamp="2025-01-20T16:37:00-05:00",
                     filing_accepted_at="2025-01-20T16:37:00-05:00", form_type="10-K/A",
                     accession_number="SYN-2024-AMEND")
    fundamentals.append(amendment)
    bundle = DataBundle.model_validate(dict(securities=securities, memberships=memberships,
                                           market=market, fundamentals=fundamentals))
    calendar = Calendar.model_validate(dict(source="synthetic-weekday-calendar-NOT-official",
                                            source_version="v1", coverage_start=str(start),
                                            coverage_end=str(finish), sessions=sessions))
    return bundle, calendar
