# RDR-008-LABEL — Executable Forward-Return Label Convention

**Status: IMPLEMENTED CONTRACT — P1-05**

The label interval is resolved from explicit exchange-calendar sessions:

```text
E_t   = first scheduled execution open after signal_timestamp
E_t+1 = first scheduled execution open after the next signal timestamp
```

The security and SPY returns use the same `[E_t, E_t+1]` interval and the shared economic-return primitive. The target is simple excess return, `security_total_return - benchmark_total_return`. A label is invalid, with an explicit reason code, when prices, benchmark data, schedule, or supported corporate-action inputs are unavailable. Labels are never imputed.

`label_end_timestamp` equals the exit execution timestamp and is retained for later purge/embargo construction. This record does not implement purge or embargo. It also does not claim that synthetic corporate-action semantics represent a real provider; that remains an open Gate A risk under RDR-004/RDR-005/RDR-011.
