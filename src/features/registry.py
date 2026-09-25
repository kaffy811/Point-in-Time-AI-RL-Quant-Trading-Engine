"""Explicit whitelist; no dataframe blacklist or automatic numeric-column discovery."""
from dataclasses import asdict, dataclass
from typing import Literal

from src.data.lineage import content_hash

FEATURE_SET_VERSION = "phase1_v1"
MOMENTUM = ("ret_5d", "ret_20d", "ret_60d", "ret_120d", "ret_252d",
            "momentum_12_1", "distance_to_52w_high")
REVERSAL = ("ret_1d", "ret_5d_reversal")
RISK = ("realized_vol_20d", "realized_vol_60d", "downside_vol_60d", "beta_60d", "beta_252d",
        "max_drawdown_60d", "max_drawdown_252d")
LIQUIDITY = ("adv_usd_20d", "adv_usd_60d", "log_dollar_volume_20d",
             "dollar_volume_change_20d", "amihud_20d")
FUNDAMENTALS = ("earnings_yield", "book_to_market", "fcf_yield", "roe", "roa",
                "gross_profit_to_assets", "operating_margin", "revenue_growth", "eps_growth",
                "debt_to_assets")
RAW_FEATURES = MOMENTUM + REVERSAL + RISK + LIQUIDITY + FUNDAMENTALS
MISSING_FEATURES = tuple(name + "_is_missing" for name in FUNDAMENTALS)


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    family: str
    dtype: Literal["float64", "int8"]
    definition: str
    lookback: str
    required_sources: tuple[str, ...]
    availability_rule: str
    minimum_observations: int
    unit: str
    winsorize: bool = True
    impute: bool = True
    passthrough: bool = False
    version: str = FEATURE_SET_VERSION


@dataclass(frozen=True)
class FeatureRegistry:
    entries: tuple[FeatureSpec, ...]

    def __post_init__(self) -> None:
        if tuple(e.name for e in self.entries) != RAW_FEATURES + MISSING_FEATURES:
            raise ValueError("feature registry must exactly match the frozen feature whitelist")
        if any(not e.definition or not e.lookback or e.version != FEATURE_SET_VERSION
               for e in self.entries):
            raise ValueError("registry requires versioned definitions/lookbacks")

    def content_hash(self) -> str:
        return content_hash([asdict(entry) for entry in self.entries])

    def model_features(self, version: str = FEATURE_SET_VERSION) -> tuple[str, ...]:
        if version != FEATURE_SET_VERSION:
            raise ValueError("unknown feature version")
        return tuple(e.name for e in self.entries)

    def spec(self, name: str) -> FeatureSpec:
        return next(e for e in self.entries if e.name == name)


AVAILABILITY = "All consumed observations come from PITStore and are available <= signal; filings too."


def _frozen_registry() -> FeatureRegistry:
    specs: dict[str, FeatureSpec] = {}

    def add(name: str, family: str, definition: str, lookback: str, count: int, unit: str,
            sources: tuple[str, ...] = ("market",)) -> None:
        specs[name] = FeatureSpec(name, family, "float64", definition, lookback, sources,
                                  AVAILABILITY, count, unit, True, True, False)

    for h in (1, 5, 20, 60, 120, 252):
        add(f"ret_{h}d", "reversal" if h == 1 else "momentum",
            f"P_TR[t]/P_TR[t-{h}]-1", f"{h + 1} consecutive trading prices", h + 1, "ratio")
    add("momentum_12_1", "momentum", "P_TR[t-21]/P_TR[t-252]-1",
        "253 consecutive trading prices; skip latest 21 intervals", 253, "ratio")
    add("distance_to_52w_high", "momentum", "P_TR[t]/max(P_TR[t-251:t])-1 <= 0",
        "252 consecutive trading prices", 252, "ratio")
    add("ret_5d_reversal", "reversal", "-ret_5d", "6 consecutive trading prices", 6, "ratio")
    for h in (20, 60):
        add(f"realized_vol_{h}d", "risk", f"sample_std({h} daily log TR returns, ddof=1)*sqrt(252)",
            f"{h} log returns / {h+1} consecutive trading prices", h + 1, "annualized fraction")
    add("downside_vol_60d", "risk", "sqrt(252*sum(min(log_TR_return,0)^2)/60)",
        "60 log returns / 61 consecutive prices", 61, "annualized fraction")
    for h in (60, 252):
        add(f"beta_{h}d", "risk", "sample_cov(stock log TR,SPY log TR)/sample_var(SPY log TR)",
            f"{h} aligned log returns / {h+1} prices each; zero variance => missing", h + 1,
            "ratio", ("market", "SPY_market"))
        add(f"max_drawdown_{h}d", "risk", "min(P_TR/running_peak(P_TR)-1) <= 0",
            f"{h} consecutive trading prices (not h returns)", h, "ratio")
    for h in (20, 60):
        add(f"adv_usd_{h}d", "liquidity", f"mean_{h}(raw_close*raw_volume)",
            f"{h} consecutive trading observations", h, "USD/day")
    add("log_dollar_volume_20d", "liquidity", "ln(1+adv_usd_20d)",
        "20 consecutive trading observations", 20, "log(1+USD/day)")
    add("dollar_volume_change_20d", "liquidity",
        "mean(DV[t-19:t])/mean(DV[t-39:t-20])-1; prior mean must be >0",
        "40 consecutive trading observations", 40, "ratio")
    add("amihud_20d", "liquidity", "1e6*mean_20(abs(simple_daily_TR_return)/USD_DV); all DV>0",
        "20 returns / 21 consecutive prices", 21, "1e6/USD")
    definitions = {
        "earnings_yield": "TTM common_net_income/(raw_close*PIT split-adjusted shares)",
        "book_to_market": "latest common_equity/(raw_close*PIT split-adjusted shares)",
        "fcf_yield": "(TTM operating_cash_flow-TTM positive_capex)/(raw_close*PIT shares)",
        "roe": "TTM common_net_income/mean(common_equity[t],common_equity[t-4Q]); denominator>0",
        "roa": "TTM net_income/mean(assets[t],assets[t-4Q]); denominator>0",
        "gross_profit_to_assets": "TTM gross_profit/mean(assets[t],assets[t-4Q]); denominator>0",
        "operating_margin": "TTM operating_income/TTM revenue; denominator>0",
        "revenue_growth": "TTM revenue[t]/TTM revenue[t-4Q]-1; prior TTM>0",
        "eps_growth": "TTM diluted_eps[t]/TTM diluted_eps[t-4Q]-1; prior TTM>0",
        "debt_to_assets": "latest total_debt/latest same-period assets; assets>0",
    }
    for name, definition in definitions.items():
        quarters = 8 if name in ("revenue_growth", "eps_growth") else (
            0 if name in ("book_to_market", "debt_to_assets") else 4)
        add(name, "fundamentals", definition,
            f"{quarters} contiguous discrete fiscal quarters plus exact required instant balances; "
            "quarter/YTD/FY normalization uses explicit fiscal metadata and PIT revisions",
            quarters, "ratio", ("fundamentals", "market") if name in
            ("earnings_yield", "book_to_market", "fcf_yield", "eps_growth") else ("fundamentals",))
    for name in MISSING_FEATURES:
        base = specs[name.removesuffix("_is_missing")]
        specs[name] = FeatureSpec(name, "missingness", "int8", f"1 if {base.name} is missing else 0",
                                  base.lookback, base.required_sources, AVAILABILITY,
                                  base.minimum_observations, "indicator", False, False, True)
    return FeatureRegistry(tuple(specs[name] for name in RAW_FEATURES + MISSING_FEATURES))


FEATURE_REGISTRY = _frozen_registry()
