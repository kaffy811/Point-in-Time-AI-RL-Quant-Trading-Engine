# DATA-02 Phase A — future evidence invariance

Compared the entire preliminary result record, including status/reason and historical identifiers, using in-memory perturbations of the real input corpus. Perturbed rows were never published as real evidence.

| Check | Passed / total |
|---|---:|
| repeat | 283 / 283 |
| reverse_input_order | 283 / 283 |
| remove_future_records | 283 / 283 |
| append_future_records | 283 / 283 |
| mutate_future_payloads | 283 / 283 |
| remove_last_date_and_tmatch | 283 / 283 |

Observations with actual future history rows: 275; with actual future link rows: 281. Future positions preserve start/first-evidence dates. Mutations reuse real identifier payloads; appends duplicate only future-positioned rows.

tmatch and last filing date are excluded from historical results, so later snapshot changes cannot alter the past output. Raw audit hashes can change and are not historical features. Same-day links remain unconfirmed.

Scope: later-effective/newly evidenced rows, order independence and audit-only fields. Not proof against retroactive vendor edits to already-historical CUSIPs/first dates or validated codes; those require archived revision provenance. No model leakage metric or SEC identity approval is inferred. Gate A remains BLOCKED.
