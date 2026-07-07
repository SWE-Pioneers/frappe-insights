# ERPNext demo-data generator

Deterministic, parameterized generator that seeds a demo company (**Summit Supply Co**)
with 18 months of sales / purchasing / accounting / stock history engineered for the
Insights ERPNext dashboard templates (see `docs/projects/erpnext_templates/plan.md`).

## Run

Needs a fresh site with `erpnext` installed — the setup wizard does **not** need to be
completed (the script runs it). `bench execute` only resolves dotted paths inside
installed apps, so import via the eval fallback:

```sh
bench --site <site> execute \
  "__import__('scripts.erpnext_demo.generate', fromlist=['run']).run"
```

Parameters (via `--kwargs`): `seed=42`, `months=18`, `scale=1.0` (volume multiplier,
use `0.05` for a quick smoke run), `end_date` (defaults to today), `force=False`
(refuses to run on a site that already has Sales Invoices).

A full run creates ~3.5k documents in ~30–45 min. Afterwards take a backup as the
instant-reset artifact (keep it local, **not** in git):

```sh
bench --site <site> backup
```

## What it engineers (mapped to the dashboard specs)

- ~20 customers with Pareto-skewed volume, each in a payment-behavior class
  (prompt / slow / delinquent) so AR ageing fills every bucket incl. 90+,
  with partial payments and a few credit notes (`is_return`).
- Quotations in an Open / Ordered / Lost mix (`order_lost_reason` set) → funnel.
- SO → DN → SI chains with monthly growth + seasonality; ~11% of SOs never
  delivered (overdue-delivery action table).
- PO → PR → PI with receipt delay vs `schedule_date` varied; some POs never
  received (overdue-PO action table).
- ~50 items in 6 groups across 2 warehouses; a dead cluster with no movement for
  90/180+ days; a few items with `Item Reorder` levels above current qty
  (reorder alerts).
- Opening stock first, then everything submitted chronologically oldest-first with
  `set_posting_time = 1` and monotonically increasing posting times — no backdated
  entries, no repost storms. Fiscal years are pre-created for the whole range.
