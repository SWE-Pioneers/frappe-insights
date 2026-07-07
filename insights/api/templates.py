import base64
import json
import os

import frappe
from frappe import _

from insights.decorators import insights_whitelist

MANIFEST_REQUIRED_KEYS = ["title", "description", "required_apps", "source_doctypes"]


def get_templates_path() -> str:
    return frappe.get_app_path("insights", "workbook_templates")


def get_template_names() -> list[str]:
    base = get_templates_path()
    if not os.path.isdir(base):
        return []
    return sorted(
        name for name in os.listdir(base) if os.path.isfile(os.path.join(base, name, "manifest.json"))
    )


def get_template_manifest(template_name: str) -> dict:
    with open(os.path.join(get_templates_path(), template_name, "manifest.json")) as f:
        return json.load(f)


def get_template_workbook(template_name: str) -> dict:
    with open(os.path.join(get_templates_path(), template_name, "workbook.json")) as f:
        return json.load(f)


def get_template_preview(template_name: str) -> str | None:
    path = os.path.join(get_templates_path(), template_name, "preview.png")
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def has_required_apps(manifest: dict) -> bool:
    return set(manifest.get("required_apps") or []) <= set(frappe.get_installed_apps())


def has_source_data(manifest: dict) -> bool:
    """Cheap EXISTS on the template's main source table, so the UI can warn
    that the imported dashboards will be empty."""
    source_doctypes = manifest.get("source_doctypes") or []
    if not source_doctypes:
        return False

    doctype = source_doctypes[0]
    if not frappe.db.table_exists(doctype):
        return False

    table = frappe.qb.DocType(doctype)
    rows = frappe.qb.from_(table).select(table.name).limit(1).run()
    return bool(rows)


@insights_whitelist()
def get_workbook_templates() -> list[dict]:
    """Templates whose required_apps are all installed. Empty on sites
    without ERPNext, so the gallery renders nothing there."""
    templates = []
    for name in get_template_names():
        manifest = get_template_manifest(name)
        if not has_required_apps(manifest):
            continue
        templates.append(
            {
                "name": name,
                "title": manifest.get("title") or name,
                "description": manifest.get("description"),
                "module": manifest.get("module"),
                "has_data": has_source_data(manifest),
                "preview_image": get_template_preview(name),
            }
        )
    return templates


@insights_whitelist()
def create_workbook_from_template(template_name: str) -> int:
    from insights.insights.doctype.insights_workbook.insights_workbook import import_workbook

    frappe.has_permission("Insights Workbook", "create", throw=True)

    # names come from a directory listing, so this also blocks path traversal
    if template_name not in get_template_names():
        frappe.throw(_("Workbook template {0} does not exist").format(frappe.bold(template_name)))

    manifest = get_template_manifest(template_name)
    if not has_required_apps(manifest):
        frappe.throw(
            _("Workbook template {0} requires apps that are not installed: {1}").format(
                frappe.bold(manifest.get("title") or template_name),
                ", ".join(manifest.get("required_apps") or []),
            )
        )

    return import_workbook(get_template_workbook(template_name))
