# P1-03 feature conventions — proposal requiring Research Owner decision

Status: SUPERSEDED by Research Owner RDR-007 APPROVED WITH MODIFICATIONS. This file preserves proposal history; it is not the binding implementation specification. See docs/research_decisions.md. The feature list and PIT/no-preprocessing requirements are already authorized. The following numeric definitions resolve open RDR-007; dependent calculators will not be silently frozen before a decision.

## A. Market conventions

- Anchor to the latest completed session exposed by PITStore. A missing/stale bar or a hole inside a required session window yields missing, never shortened/forward-filled history. Pre-membership history remains legal.
- One-step economic gross return: `split_factor[t] * (raw_close[t] + dividend[t]) / raw_close[t-1]`, with dividends in post-split per-share units per P1-02. Reinvest the ex-date distribution for this feature-only total-return index. Future executable labels/accounting still require their own decision.
- `ret_Nd`: product of N economic gross returns minus one, requiring N+1 consecutive session closes. `ret_5d_reversal = -ret_5d`.
- `momentum_12_1`: total-return-index ratio from offset -252 to offset -21 (253 closes).
- `distance_to_52w_high`: latest total-return index / max of its last 252 session observations minus one.
- Realized volatility: sample standard deviation (`ddof=1`) of N economic returns × sqrt(252). Downside volatility: sqrt(mean(min(return, 0)^2)) × sqrt(252), using all 60 observations in the denominator.
- Beta: sample covariance(stock, SPY) / sample variance(SPY), same N aligned session returns; zero benchmark variance yields missing. SPY has a separately configured stable ID and is never added to the eligible universe.
- `drawdown_Nd`: minimum(total-return index / running peak - 1) over N returns (N+1 closes), i.e. maximum drawdown magnitude with negative sign.
- `adv_Nd`: mean raw_close × raw_volume in USD/day over N sessions. `log_dollar_volume_20d`: natural log of positive adv_20d.
- `volume_change_20d`: mean split-adjusted share volume over latest 20 sessions / preceding 20 sessions minus one. Only splits visible at the signal enter historical share-unit adjustment.
- `amihud_20d`: mean(abs(economic daily return)/(raw_close × raw_volume)) over 20 sessions, in 1/USD; no extra scaling. Zero dollar volume yields missing.

## B. Fundamental conventions

- No inference of quarterly values from annual/YTD reports in this version. Use explicit standalone fiscal-quarter facts; four contiguous quarters form TTM. Proposed quarter duration guard: 70–110 calendar days; no interpolation. Missing required periods stay missing.
- Canonical semantic facts (provider normalization responsibility): net_income, equity, assets, operating_cash_flow, capital_expenditures (positive cash outflow), gross_profit, operating_income, revenue, diluted_eps, total_debt, and shares_outstanding. Currency USD; EPS USD/share; shares in shares. No automatic US-GAAP tag fallback.
- Use the latest complete, co-period set visible at the signal. Do not mix different fiscal-period ends within a ratio. TTM flows must end at that set's fiscal end. ROE/ROA use the average of beginning/end equity/assets across the TTM period; gross profit/assets and debt/assets use ending assets. Operating margin = TTM operating income / TTM revenue.
- E/P = TTM net income / (current raw close × split-adjusted shares outstanding); B/P = ending equity / same market cap; FCF/P = (TTM operating cash flow - TTM capital expenditures) / same market cap.
- shares_outstanding must describe the same entire equity claim as net income/equity and the price. Mixed-class issuer-level totals must not be applied to a single share class. For this version, require an explicit single-class scope assertion in canonical provenance; otherwise these three valuation ratios remain missing. Provider/company mapping is never inferred from ticker.
- RevenueGrowth and EPSGrowth = latest standalone quarter / same fiscal quarter one year earlier - 1. Nonpositive comparison denominator yields missing with a reason, not inf. Negative numerators are allowed.
- Nonpositive denominator for any ratio yields missing with a reason. Missing facts are not replaced by earlier non-null revisions. No age cutoff is proposed without an additional decision; report fact age.

## C. Engineering behavior (no research parameter choice)

31 raw features + 10 fundamental missing indicators = 41 default model columns. Optional stateless percentile-rank view is separate and does not overwrite or enlarge the default whitelist. Per-cell input references, maximum availability, missing reason and period/session coverage are preserved. QA statistics are diagnostic only, never preprocessing parameters.
