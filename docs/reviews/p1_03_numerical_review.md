# P1-03 Independent Numerical Review

Status: completed as an independent review of the current P1-03 tree.

This review evaluates formula implementation and accounting/PIT semantics. It
does not treat the number of automated tests as evidence of numerical
correctness by itself, and it does not approve real-data completeness.

## Scope and method

The review compared the binding RDR-007 definitions with the implementations in
`src/features/momentum.py`, `risk.py`, `liquidity.py`, `fiscal.py`,
`fundamentals.py`, `market_common.py`, and the feature registry. The synthetic
fixtures and integration pipeline were also inspected. Independent calculations
were performed for representative market and accounting cases below.

## Independent hand calculations

### Market features

| Case | Independent calculation | Expected/observed implementation behavior |
|---|---|---|
| Simple return | If `P[t-20]=100` and `P[t]=110`, `ret_20d = 110/100 - 1 = 0.10`. | `market_window` requires 21 consecutive available prices and `momentum` uses the first and last total-return-chain values; this matches. |
| 12–1 momentum | With `P[t-252]=100` and `P[t-21]=331`, `P[t-21]/P[t-252]-1 = 2.31`. | The 253-price window indexes `prices[0]` and `prices[-22]`; this matches the frozen skip of the latest 21 observations. |
| Volatility | For daily log returns `[-.02,.01,-.01,.03]` repeated, the implementation uses sample standard deviation (`ddof=1`) times `sqrt(252)`. | `statistics.stdev` is the required sample standard deviation; no partial window is accepted. |
| Downside volatility | For `[-.02,.01,-.01,.03]`, the frozen semideviation is `sqrt(252*((.02^2+0+.01^2+0)/4))`. | The implementation sums `min(r,0)^2` over the full return window and divides by the full horizon, rather than taking the standard deviation of negative observations. |
| Beta | If stock log returns equal `2 * SPY log returns`, `Cov(stock,SPY)/Var(SPY)=2`. | The implementation uses aligned completed-session windows and covariance/variance sums; the common divisor cancels, yielding 2. Zero benchmark variance returns missing. |
| Maximum drawdown | For prices `[100,120,90,110]`, the window MDD is `90/120-1=-0.25`; it is not `110/120-1`. | The running-peak loop records the minimum peak-to-trough drawdown. |
| Split/dividend | A 2-for-1 split from raw 100 to raw 50 with split factor 2 gives chain gross return `2*50/100=1`. A post-split dividend of 1 gives `2*(50+1)/100=1.02`. | `total_return_prices` applies split factor and post-split dividend to the following raw bar, avoiding phantom return/volatility. |
| Dollar volume | Raw close 100 and volume 10,000 gives USD 1,000,000; raw close 50 and split-adjusted raw volume 20,000 also gives USD 1,000,000. | ADV and volume-change use raw close times raw volume, independent of the reconstructed return-price chain. |
| Amihud | A 1% simple return on USD 10,000,000 dollar volume contributes `1e6*.01/10,000,000=0.001`; the feature averages 20 such observations. | The implementation uses simple total-return-chain daily returns, absolute value, USD dollar volume, `1e6` scaling, and rejects nonpositive volume. |

The market implementations therefore agree with the approved endpoint,
price-series, horizon, and denominator conventions.

### Fundamental features and accounting semantics

| Case | Independent calculation | Expected/observed implementation behavior |
|---|---|---|
| YTD reconstruction | `Q1 YTD=100`, `Q2 YTD=230`, `Q3 YTD=360`, `FY=500` produces discrete quarters `100,130,130,140`, so TTM is `500`. | `discrete_quarters` subtracts only the preceding same-year YTD and `trailing_flow` sums four contiguous discrete quarters; overlapping YTD values are not summed. |
| TTM completeness | A TTM requires four ordinals with contiguous fiscal boundaries. Two or three quarters do not get annualized. | Missing or noncontiguous quarters return a missing result. |
| EPS semantics | `Q1 diluted EPS YTD=1.00` and `Q2 diluted EPS YTD=2.20` cannot safely imply standalone Q2 EPS `1.20` because weighted-average diluted shares can change. | The implementation explicitly returns `ytd_eps_not_additive` unless a direct quarter EPS observation exists. This preserves missingness instead of fabricating accounting data. |
| Amendment timing | If a Q2 revenue fact changes from 130 to 125 at a later filing, the earlier snapshot retains 130 and the later snapshot can use 125. | PIT revision resolution selects the latest available revision only after its availability and filing timestamps; the feature integration tests exercise this boundary. |
| Market cap | `raw_close * PIT-visible shares`, with known split chain applied from the share basis date through the anchor date. | `market_cap` uses the latest visible shares fact, raw close, and `split_chain`; unavailable/invalid split history returns missing rather than guessing. |
| Earnings yield | Negative TTM common earnings remain a negative numerator; only a nonpositive market-cap denominator is rejected. | `earnings_yield` preserves negative earnings information. |
| Book-to-market | Common equity divided by positive market cap; negative equity remains a negative ratio. | `book_to_market` does not silently clip or drop negative equity. |
| FCF yield | `TTM CFO - TTM positive CapEx`, divided by market cap. | CapEx is required to be normalized as a positive outflow; negative/un-normalized input is rejected. Periods must match. |
| ROE/ROA | ROE uses average current and prior-year common equity; ROA uses average current and prior-year assets. Nonpositive denominators are undefined. | The implementation uses exact period-end instant facts and returns missing for nonpositive denominators. |
| Gross profit/assets | TTM gross profit divided by the same average-assets convention as ROA. | The implementation shares the average-assets path with ROA. |
| Operating margin | TTM operating income divided by TTM revenue, with nonpositive revenue undefined. | The implementation reconstructs both TTM flows and requires matching periods and a positive revenue denominator. |
| Revenue growth | Current TTM revenue divided by the TTM ending four fiscal quarters earlier, minus one. | `trailing_flow(offset=4)` is used and the two TTM windows must be contiguous; nonpositive prior TTM is missing. |
| EPS growth | Current diluted-EPS TTM divided by prior diluted-EPS TTM, minus one, only when prior TTM EPS is positive. | The implementation uses the strict positive-prior rule and returns missing otherwise. |
| Debt/assets | Total debt is preferred when present; otherwise current plus long-term debt is used, divided by same-period positive assets. | The implementation follows the explicit total-debt preference and rejects nonpositive assets. |

## PIT and invariance review

The feature pipeline obtains market and fundamental inputs from `PITStore`
snapshots. `FeatureFrame` validates that every referenced observation is
available by the signal timestamp and that filing acceptance is not later than
the signal. The observed revision resolver applies both knowledge-time gates
before selecting a revision.

The integration tests compare generated feature frames after adding a future
market value or changing a later revision. The earlier feature frame remains
unchanged. The amendment boundary test separately confirms that a later
available revision may change a later snapshot. This is consistent with the
required Future Data Invariance and Future Revision Invariance properties.

The feature frame also enforces the stable `security_id` boundary and permits a
different security only for the explicitly declared SPY beta benchmark. Missing
market history remains a missing feature; it is not forward-filled or replaced
with a cross-sectional statistic.

## Findings

| Severity | Finding | Evidence | Disposition |
|---|---|---|---|
| BLOCKER | None found in the reviewed formula or PIT paths. | RDR-007 comparison and independent cases above. | — |
| HIGH | None found in the reviewed formula or PIT paths. | No reviewed implementation disagreed materially with a binding convention. | — |
| MEDIUM | Real-provider taxonomy and historical corporate-action semantics remain unvalidated. | Current artifacts are synthetic; SEC adapter coverage is a synthetic payload vertical slice. | Does not block numerical approval; required for Gate A real-data validation. |
| MEDIUM | Beta alignment is safe for the current canonical calendar contract because missing dates fail the strict window, but provider calendars must be checked in the real-data slice. | `market_window` uses completed calendar sessions and requires every requested date. | Audit explicitly during Gate A. |
| LOW | The current QA distribution statistics are full-sample diagnostics. | Artifact warning states they must never be reused as preprocessing parameters. | Preserve this boundary in P1-04. |

## Unresolved risks and limits

This review is numerical and implementation-focused. It does not establish
that real 2010–2025 data has complete historical S&P 500 membership, complete
daily bars, reliable corporate-action fields, or complete filing revisions.
Those require the real-data vertical slice and remain part of Gate A.

The synthetic fixture also cannot validate provider-specific concept mapping,
amended filing chains at production scale, or vendor handling of unusual fiscal
calendars. No learned preprocessing, labels, models, portfolio construction,
backtest, or performance claim was reviewed or implemented here.

## Recommendation

**APPROVE numerical review.**

The reviewed P1-03 calculators are consistent with RDR-007, the accounting
semantics are appropriately conservative around YTD EPS and incomplete TTM
histories, and the PIT invariance behavior is supported by the implementation
and integration tests. There are zero BLOCKER and zero HIGH findings.

This recommendation supports:

```text
P1-03 = CONDITIONAL PASS / LOCAL VERIFIED / REMOTE-CI PENDING
Gate A = PARTIAL
```

The recommendation does not close remote CI and does not upgrade Gate A until a
real historical data vertical slice has been audited.

Verification context supplied for this review: 134 local tests passed, Ruff
passed, Mypy passed, remote CI pending.
