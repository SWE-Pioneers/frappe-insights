# Workbook templates: the public contract

Any installed app can contribute workbook templates to a site's Insights
Library. The whole contract is three steps:

1. Put a folder in your app with `manifest.json` + `workbook.json` (and an
   optional `preview.png`) — one folder per workbook.
2. Point one hook at the directory that holds those folders.
3. Your dashboards appear in the site's Insights Library for an admin to import.

Insights is its own first consumer: the bundled ERPNext templates
(`insights/workbook_templates/`) are discovered through this same hook, so the
public API is the reference implementation, not a parallel path.

## The hook

```python
# in your app's hooks.py
insights_workbook_templates = "my_workbooks"   # path relative to your app
```

Insights resolves this hook across every installed app on each read. So the
library is derived live from installed apps — installing an app adds its
workbooks, uninstalling removes them. No migrate step, no registry doctype, no
sync job. (Workbooks already imported before an uninstall survive as ordinary
workbooks; their queries may now error, which is expected and honest.)

## Layout

```
my_workbooks/
  sales/
    manifest.json
    workbook.json
    preview.png        # optional
  purchasing/
    manifest.json
    workbook.json
```

## manifest.json

| key              | required | meaning                                                        |
| ---------------- | -------- | -------------------------------------------------------------- |
| `title`          | yes      | Card title.                                                    |
| `description`    | yes      | One-line pitch shown on the card.                              |
| `required_apps`  | yes      | *Additional* apps the workbook needs beyond the shipping app.  |
| `source_doctypes`| yes      | Doctypes the queries read — drives the "no data on this site" hint. |
| `module`         | no       | Grouping badge (e.g. "Selling").                               |
| `notes`          | no       | Technical caveats, split out of the description.               |
| `version`        | no       | Integer, defaults to `1`. Reserved for future "update available". |

The shipping app is trivially installed (the template was found via *its* hook),
so it need not appear in `required_apps` — but a workbook can still declare that
it also needs, say, `erpnext`.

A manifest that is missing a required key or has the wrong shape is skipped with
a log line. One app shipping a broken manifest never takes down the library.

## Identity

The canonical id of a template is `"{app}/{folder}"` (e.g. `insights/sales`,
`hrms/attendance`). This namespaces two apps that both ship a `sales` folder, and
gives imported-state a stable key. It is stored on the imported workbook's
`from_template` field.

## Constraints (v1)

- **Site database source only.** `workbook.json` must target the site database
  data source. There is no remapping to arbitrary data sources — the import
  assumes it, and app authors should not discover that the hard way.
- **Admin-curated import.** Importing produces one Administrator-owned,
  org-shared copy per site, and only an Insights Admin can trigger it from the
  Library. There is no auto-import on migrate and no `auto_import` manifest flag
  — that decision belongs to the site admin, deliberately.

## Explicitly out of scope for v1

Update/reconcile semantics (upstream vs. an admin's edits), per-workbook
data-source remapping, and any per-user import model. The `version` field and
qualified ids are the only forward provisions bought now — `version` makes
update *detection* possible later (`manifest.version > imported.version`)
without a manifest migration; update *semantics* are punted, not detection.
