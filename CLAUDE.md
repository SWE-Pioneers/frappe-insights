# CLAUDE.md — frappe-insights (SWE-Pioneers fork)

Changes on top of upstream `frappe/insights` (main).

## Arabic i18n
- `insights/locale/ar.po` completed to **100% of app-owned strings** (Libyan-appropriate MSA), tagged
  `ai-translated; needs-native-review`. Built/filled via the parent repo's `scripts/i18n` pipeline
  (`generate-pot-file` sync for full doctype/field coverage). See the parent `SWE-Pioneers/frappe`
  `CLAUDE.md` for the pipeline + the runtime `.mo` compile mechanics.
- **Full i18n retrofit** (app had none): added a whitelisted `get_translations` endpoint (modeled on `crm/crm/api/__init__.py`), a `translation.js`/`.ts` plugin registered in `main.*`, RTL boot, and `__()`-wrapped ~100–230 components.

## Deploy
Built from `~/build/insights-custom` on the VPS (Containerfile repointed to this fork + per-app
`compile-po-to-mo`). Rebuild with `--no-cache`; see the parent `CLAUDE.md` for the `.mo` compile +
persist gotchas.
