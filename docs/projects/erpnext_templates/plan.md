# ERPNext Dashboard Templates for Insights v3

Ship prebuilt, meaningful ERPNext analytics in Insights v3 — the immediate, bare-minimum
need of ERPNext users — without waiting for v4.

**Approach in one line:** a "Templates" gallery that appears when ERPNext is installed on
the site; each template is a workbook JSON (authored in the Insights UI, exported,
committed to this repo) that queries the existing `Site DB` data source; clicking a
template calls the existing `import_workbook()` to give the user an editable copy.

## Why this shape

- Insights v3 primitives are all we need: Workbook → Query v3 (`operations` JSON
  pipeline) → Chart v3 (config JSON) → Dashboard v3 (layout JSON). `Number`, `Bar`,
  `Line`, `Row`, `Donut`, `Funnel`, `Table` cover every chart in the specs below —
  notably Funnel (quotation → order) and Table (ageing/action lists), which ERPNext's
  native dashboards can't do.
- `Insights Workbook.export()` / `import_workbook()` already round-trip a full workbook
  (queries with operations, charts, dashboards, folders) with name remapping
  (`insights/insights/doctype/insights_workbook/insights_workbook.py`). The gallery is
  thin glue; the week's real work is content.
- A template creates a plain user-owned workbook — no sync-on-update, no managed state,
  no new doctypes. Template updates only affect future copies. Right semantics for v1.
- Community research: nobody asks for "templates" by name, but everyone rebuilds the same
  three dashboards from scratch (sales performance, AR/cash, stock ageing/movement) in
  Metabase/Power BI because native ERPNext dashboards can't do cross-doctype charts or
  flexible date ranges. The templates also encode the metric-correctness traps everyone
  hits (see Cross-cutting rules).

## Mechanism

New `insights/api/templates.py` + `insights/workbook_templates/` directory.

- Each template is a folder: `manifest.json` (title, description, module,
  `required_apps: ["erpnext"]`, list of source doctypes) + `workbook.json` (the export
  payload) + `preview.png`.
- `get_workbook_templates()` — reads manifests, returns only templates whose
  `required_apps` are all installed (`frappe.get_installed_apps()`). Annotates each with
  a has-data flag (cheap EXISTS on the main source table) so the UI can warn about empty
  dashboards.
- `create_workbook_from_template(template_name)` — loads the JSON, delegates to
  `import_workbook()`, returns the new workbook name.
- Frontend: "Start with a template" section on the workbook list page
  (`frontend/src2/workbook/WorkbookList.vue`) — templates create workbooks, so the
  gallery sits where workbook creation lives (the old Home page is unrouted dead code;
  `/` redirects to `/dashboards`). Template cards (preview image, title, description,
  module badge), frappe-ui components and design tokens. Renders only when the endpoint returns templates, so non-ERPNext
  sites see zero change. Click → confirm → create → route to the new workbook.
- CI guard: a test that parses every committed manifest and imports every committed
  `workbook.json` — keeps templates from rotting silently.

## Demo data strategy

ERPNext's built-in demo (`erpnext/setup/demo.py`) is too thin to exercise these
dashboards: 3 customers, 10 items, 15 orders in one fiscal year, 6 invoices, no
quotations/returns/aged stock. We build our own.

**Key inversion:** demonstration is the demanding consumer (needs realistic
*distributions* — trends, ageing spread, dead stock — or correct dashboards look
broken); testing needs *known* data plus an oracle, not realistic data.

One artifact serves both: a **checked-in, deterministic, parameterized generator**
(`scripts/erpnext_demo/generate.py`, run via `bench execute`, seeded RNG). It seeds a
demo company with an engineered distribution mapped to the chart specs:

- 18 months of history, submitted chronologically oldest-first with `set_posting_time`
  and fiscal years pre-created — avoids backdated-entry repost storms (the #1 generator
  gotcha).
- ~20 customers with Pareto skew; each assigned a payment-behavior class
  (prompt / slow / delinquent) so AR ageing fills every bucket incl. 90+; partial
  payments; a few credit notes (`is_return`) to prove net-revenue logic.
- Quotations in Open/Ordered/Lost mix (with `order_lost_reason`) → funnel.
- Some SOs past `delivery_date` undelivered and POs past `schedule_date` unreceived →
  both action tables.
- ~50 items in ~6 item groups, 2 warehouses; a cluster with no movement in 90/180+ days
  (dead stock + stock ageing); a few items with reorder levels above current qty
  (reorder alerts); receipts with varied delay vs `schedule_date` (groundwork for the
  🟡 on-time-delivery metric).
- Volume ~3–5k documents (~30–45 min one-time ORM run). Run once, then `bench backup` —
  the `.sql.gz` is the instant-reset artifact for the week. Generator in git; backup
  stays local.

Explicitly rejected: anonymized production data (not repeatable/shippable, privacy risk).

**Testing tiers built on this:**

1. Mechanism tests (listing/import) — no ERPNext data; normal CI.
2. Query smoke tests — ERPNext installed, zero rows: every template query executes
   without error and renders an empty state. Catches schema drift.
3. Correctness — assert against ERPNext's own reports on the same site (AR card ==
   AR Summary total, stock value == Stock Balance, revenue trend == Sales Analytics).
   Works on any dataset. Scripted as `verify.py` (Day 7), not CI-integrated this week
   (ERPNext-in-CI plumbing is a follow-up).

## Design rules (from research consensus)

- 6–10 KPIs max per dashboard; most important top-left.
- Every number card shows a comparison (delta vs previous period) — a number without a
  comparison is decoration.
- Universal skeleton per dashboard: trend + top-N breakdown + one health/risk view.
- Action tables are first-class (who to call, what to reorder, what's overdue) — the
  dashboard is a prioritized worklist plus a handful of health numbers.
- Pair opposing metrics so nobody over-optimizes one side (receivables ↔ payables,
  stock value ↔ stockouts).
- Every dashboard gets date-range + company filters.

## Cross-cutting correctness rules (encode in every query)

These are the traps every ERPNext user hits when hand-rolling analytics — encoding them
is the core value of shipping templates:

- `docstatus = 1` on every transactional table.
- Returns/credit notes (`is_return`) ride along as negative rows — include them, don't
  filter them out; use *net* totals.
- `is_cancelled = 0` on GL Entry and Stock Ledger Entry.
- Base currency (`base_*` fields) only; label dashboards accordingly. Party-currency
  views are out of scope for v1.
- Intraday POS invoices don't hit ledgers until POS closing/consolidation — note in the
  Sales template description.
- Gross profit via `Sales Invoice Item.incoming_rate` is unreliable with product bundles
  and POS — ship only with a visible caveat (or hold, see spec).
- Document-based outstanding (`outstanding_amount`) for AR/AP in v1, not GL-reconstructed
  — matches the AR Summary users read. GL-based point-in-time AR and "ageing drift over
  time" are v2.
- Stock valuations are only as good as the site's repost state; backdated entries can
  skew `Bin.stock_value` — we display, not fix; label it.
- Cap every query with sensible limits — these run on the live site DB.

## Dashboard specs

Legend: 🟢 v1 ship, 🟡 v1 stretch / first fast-follow. All 🟡 items are pre-specced so
post-feedback iterations are query edits, not research.

### 1. Sales — "Sales Performance"

Sources: `Sales Invoice`, `Sales Invoice Item`, `Sales Order`, `Quotation`

| | Item | Type | Computation / source | Why it earns its spot |
|--|------|------|---------------------|----------------------|
| 🟢 | Revenue | Number | sum `base_net_total`, SI (returns net out) | The anchor; *net*, so credit notes don't flatter it |
| 🟢 | Invoice count & Avg invoice value | 2 Numbers | count / avg over same set | Splits "more deals vs bigger deals"; AOV catches silent discounting |
| 🟢 | Active customers | Number | distinct `customer` in period | Acquisition vs expansion signal |
| 🟢 | Revenue trend | Line | monthly net revenue, last 12 mo | Universal; seasonality + trajectory |
| 🟢 | Top 10 customers | Row | sum by `customer` | Concentration + account focus |
| 🟢 | Top 10 items | Row | SI Item, sum `base_net_amount` by `item_code` | What to double down on |
| 🟢 | Revenue by item group | Donut | SI Item by `item_group` | Mix shifts |
| 🟢 | Quotation funnel | Funnel | Quotation counts: total → Ordered (Lost beside) | Native dashboards can't; explicit community ask |
| 🟢 | Overdue deliveries | Table | SO: `per_delivered < 100`, `delivery_date < today`; customer, value, days late | Action list — fulfillment risk |
| 🟡 | New vs returning revenue | Stacked bar | first-invoice-date mutate per customer | High value; needs a windowed query |
| 🟡 | Gross margin % | Number + by item group | SI Item `base_net_amount − incoming_rate × stock_qty` | Essential per research, but bundles/POS/non-stock invoices make it lie — needs visible caveat |

### 2. Purchasing — "Purchasing Overview" (deliberately leaner — thinnest community demand)

Sources: `Purchase Invoice`, `Purchase Order`, `Purchase Order Item`, `Purchase Receipt Item`

| | Item | Type | Computation / source | Why |
|--|------|------|---------------------|-----|
| 🟢 | Spend | Number | sum `base_net_total`, PI | Anchor |
| 🟢 | PO count & Avg PO value | 2 Numbers | Purchase Order | Workload + order-size drift |
| 🟢 | Active suppliers | Number | distinct supplier | Fragmentation/dependency |
| 🟢 | Spend trend | Line | monthly, 12 mo | Budget control |
| 🟢 | Spend by item group | Row | PI Item | Heart of spend analysis — where to negotiate |
| 🟢 | Top 10 suppliers | Row | sum by supplier | Leverage + dependency check |
| 🟢 | PO status | Donut | PO `status` | Ops pipeline |
| 🟢 | Overdue POs | Table | `per_received < 100`, `schedule_date < today`; supplier, value, days late | Action list; feeds stockout prevention |
| 🟡 | Supplier on-time delivery % | Row by supplier | PR Item ⋈ PO Item on `purchase_order_item`, receipt date vs `schedule_date` | The one advanced metric worth the join — ranked above everything except spend |
| 🟡 | Price trend of top items | Table | avg `base_rate` this vs prior quarter, % change | Purchase-price-variance proxy; catches creeping increases |

### 3. Accounting — "Receivables, Payables & Cash"

Sources: `Sales Invoice`, `Purchase Invoice`, `Payment Entry`, (🟡 `GL Entry` ⋈ `Account`)

| | Item | Type | Computation / source | Why |
|--|------|------|---------------------|-----|
| 🟢 | Total AR / Total AP | 2 Numbers | sum `outstanding_amount > 0` | Headline pair |
| 🟢 | % AR overdue & % AR > 90d | Numbers | overdue = `due_date < today` | Bad-debt early warning (healthy < ~3% at 90+) |
| 🟢 | Net cash flow (period) | Number | Payment Entry: received − paid | "Breathing in or out" |
| 🟢 | AR ageing | Bar | buckets Not due / 1–30 / 31–60 / 61–90 / 90+ by `due_date` (mutate) | *The* universal finance chart; most-referenced ERPNext report |
| 🟢 | AP ageing | Bar | same on PI | Payment scheduling |
| 🟢 | Top overdue customers | Table | customer, outstanding, overdue amount, oldest invoice age | The collections call list — the point of the dashboard |
| 🟢 | Payments due next 30 days | Table | PI by `due_date`, supplier, amount | "Can we cover Thursday?" |
| 🟢 | Cash in vs out | Grouped bar | PE monthly, received vs paid | QuickBooks/Xero core view |
| 🟢 | Invoiced vs collected | Grouped bar | SI totals vs PE received, monthly | Shows debt accumulating before ageing does |
| 🟡 | DSO | Number | `sum(outstanding) / rolling-90d revenue × 90` — conditional-sum measures over SI | Trend matters more than level |
| 🟡 | Income vs expense trend | Line ×2 | GL Entry ⋈ Account on `root_type`, `is_cancelled = 0` | Consultant-standard "profitability" view; one clean join |

### 4. Stock — "Inventory Health"

Sources: `Bin`, `Stock Ledger Entry`, `Item`, `Item Reorder`

| | Item | Type | Computation / source | Why |
|--|------|------|---------------------|-----|
| 🟢 | Total stock value | Number | sum `Bin.stock_value` | Cash on shelves |
| 🟢 | Stock value change (period) | Number | sum SLE `stock_value_difference` in period | Accumulating or draining? |
| 🟢 | Items below reorder level | Number | Bin ⋈ Item Reorder, `projected_qty < warehouse_reorder_level` | The urgent number |
| 🟢 | Dead stock value (90d) | Number | Bin value for items whose max SLE `posting_date` > 90d ago | Clearance / stop-reorder decisions |
| 🟢 | Stock value by warehouse | Bar | Bin | Multi-location must-have |
| 🟢 | Stock value by item group | Bar | Bin ⋈ Item | Where the money sits |
| 🟢 | Stock ageing (by value) | Bar | value bucketed by days since last movement: 0–30/31–90/91–180/180+ | Explicit forum ask ("stock ageing *with valuation*"); last-movement proxy, not FIFO — labeled |
| 🟢 | In vs out | Grouped bar | SLE monthly, incoming vs outgoing value | Direction of stock |
| 🟢 | Reorder alert table | Table | item, warehouse, actual qty, reorder level, projected qty | Action list → today's POs |
| 🟢 | Top items by stock value | Table | qty, value, days since last movement | The drill-down everyone uses |
| 🟡 | Days of cover | Number / by group | stock value ÷ daily outgoing value (90d run-rate) | Forward-looking; better than turnover for reorder decisions |

## PR breakdown

| PR | Contents |
|----|----------|
| PR 1 | Template mechanism: registry, APIs, gallery UI, CI import test |
| PR 2 | Sales + Purchasing template workbooks |
| PR 3 | Accounting + Stock template workbooks |

Splitting mechanism from content means PR 1 reviews while content is authored, and a weak
dashboard never blocks the feature.

## Timeline (7 working days)

| Day | Work |
|-----|------|
| 1 | Dev site; demo-data generator (full day — see Demo data strategy) + `bench backup` artifact |
| 2 | Template registry backend + ERPNext detection; gallery UI on workbook list; CI import test; **merge PR 1** |
| 3 | Author Sales workbook (the flagship — establish patterns: period comparisons, funnel, action table) |
| 4 | Author Purchasing (clones Sales patterns) + start Accounting (ageing-bucket mutate is the one hard expression — decide builder-vs-native SQL fast) |
| 5 | Finish Accounting; **merge PR 2** |
| 6 | Author Stock (dead-stock + ageing need the SLE last-movement join — real half day) |
| 7 | Verification + hardening; **merge PR 3** |

## Verification bar (Day 7)

- Numbers match ERPNext's own reports on the demo site: AR Summary, Stock Balance,
  Sales Analytics.
- Import every template on a *clean* ERPNext site (no demo data) — dashboards degrade to
  empty states, not errors.
- SQL/perf pass on the heavy queries (SLE, ageing) against a realistically sized DB.
- Gallery visible only to users who can create workbooks; nothing leaks to viewer roles.

## Risks

- **Ageing buckets in the builder** — bucketing by `due_date` needs a case-like `mutate`
  expression; if the expression language fights back, use a native-SQL query in the
  template (`is_native_query`). Decide fast on Day 4.
- **Fiscal vs calendar year** — "YTD"-style comparisons use calendar periods in v1; note
  in template descriptions rather than modeling Fiscal Year.
- **Multi-company / multi-currency** — base-currency + company filter is correct for the
  minimum; consolidated multi-currency views out of scope.
- **Chart config drift** — exported `config` JSON is UI-generated; the CI import test is
  the guard.

## Out of scope (natural v2, keep in mind so v1 doesn't paint us in)

- Embedding Insights dashboards in ERPNext workspaces — the single loudest community ask
  (frappe/insights#725, frappe/erpnext#50254).
- ERPNext user-permission-aware chart data (frappe/insights#919).
- GL-based point-in-time AR, ageing drift over time, party-currency views, FIFO-true
  stock ageing.

## Decisions & refinements (post-plan)

Refinements made once the shared-copy model landed. These supersede the "plain
user-owned workbook" framing in *Why this shape* above.

- **Framing: a workbook library that installed apps seed, not an "ERPNext templates"
  feature.** The gallery is the catalog of what the site's installed apps offer;
  ERPNext just happens to be the only source today. Copy avoids treating ERPNext as an
  aside ("for your installed apps"); it *is* what the apps provide.
- **Naming (lexicon).** The collection is the **Workbook Library** (dialog title); the
  entry-point button is just **Library** (context beside *New Workbook* carries it). The
  action is **Import** — "import from the library" reads right and reinforces that these
  are available-not-owned until you act. "Template" is avoided in UI copy (clashes with
  "workbook"). Lock this so a future addon doesn't rename it. (No `docs/v4/lexicon.md`
  exists on this branch yet; promote this entry there when the v4 lexicon lands.)
- **Entry point.** One permanent labeled button next to *New Workbook*, shown whenever
  the catalog is non-empty. No prominence machinery (no `hasSeenGallery` flag, no
  self-dismissing button, no banner/callout) and no single-item ⋯ dropdown. The button
  also seeds the empty state so a fresh site points straight at the library.
- **Shared copy, admin-only (v1).** Import produces one Administrator-owned, org-view
  shared copy per site (see [shared-copy memory]); only admins trigger it, so only
  admins fetch/see the entry point for now.
- **Card attribution (design-ahead, not built).** Cards must leave room for a
  source-app attribution (a badge beside the module, or per-source grouped sections).
  Not rendered while ERPNext is the only source, but the card/grid layout must be able
  to take it without a redesign.
- **Update semantics — explicit punt.** When an app ships a newer version of an
  already-imported workbook there is **no sync/upgrade**; the story is
  delete-and-reimport (deletion re-enables the template via the derived `from_template`
  lookup). A managed/refresh path is deferred, not overlooked.

## Research provenance

Three inputs, July 2026:
1. ERPNext's own report catalog (stronger demand signal than its shallow module
   dashboards): AR/AP ageing, gross profit, sales analytics, stock ageing, lost
   quotations, inactive customers, procurement tracker.
2. Industry dashboard research (NetSuite, Odoo, Xero/QuickBooks, Klipfolio, Sievo,
   HighRadius, EazyStock et al.) — table-stakes KPIs, core charts, anti-patterns per
   domain.
3. ERPNext community signal (discuss.frappe.io, GitHub) — flexible date filters, stock
   ageing with valuation, quotation funnel, AR matching the standard report; plus the
   correctness traps encoded above. Schema feasibility of every 🟢/🟡 item verified
   against ERPNext doctypes (fields exist: `per_delivered`, `per_billed`,
   `schedule_date`, `incoming_rate`, `order_lost_reason`, `stock_value`,
   `stock_value_difference`, `is_cancelled`, …).
