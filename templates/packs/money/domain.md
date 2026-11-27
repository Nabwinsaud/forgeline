### Money (pack: money)

- Amounts are integers in the smallest unit (cents, paisa) or an exact decimal type. Never float or double.
- Every amount carries its currency. Never add amounts in different currencies.
- Round once, at the edge (display or invoice line), with a stated rule. Splits must add back up to the total exactly; say who gets the remainder.
- Money movements are append-only records (ledger entries). Corrections are new entries, never edits or deletes.
- Charges and payouts are idempotent: a retry with the same idempotency key must not charge twice.
- Balances are derived from entries, or checked against them. A stored balance that can drift is a bug.
- Anything that moves money, changes prices or touches refunds is high risk and needs a human to merge.
