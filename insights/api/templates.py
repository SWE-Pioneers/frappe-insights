import base64
import json
import os

import frappe
from frappe import _
from frappe.utils.synchronization import filelock

from insights.decorators import insights_whitelist
from insights.utils import DocShare

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


def get_installed_apps() -> set[str]:
    # narrow seam over frappe.get_installed_apps so tests can fake the app set
    # without patching the global that frappe's own insert hooks rely on
    return set(frappe.get_installed_apps())


def has_required_apps(manifest: dict) -> bool:
    return set(manifest.get("required_apps") or []) <= get_installed_apps()


def has_source_data(manifest: dict) -> bool:
    """Cheap EXISTS across the template's source tables — True if any of them
    holds a row, so the UI can warn that the imported dashboards will be empty.
    Checking only the first table would miss data living in the others."""
    for doctype in manifest.get("source_doctypes") or []:
        if not frappe.db.table_exists(doctype):
            continue
        table = frappe.qb.DocType(doctype)
        if frappe.qb.from_(table).select(table.name).limit(1).run():
            return True
    return False


def get_imported_templates() -> dict[str, str]:
    """Map of template name -> the workbook the site already created from it.
    One shared copy per site (not per user), and derived from a live query (not a
    stored flag), so deleting the workbook re-enables its template on its own."""
    rows = frappe.get_all(
        "Insights Workbook",
        filters={"from_template": ["!=", ""]},
        fields=["from_template", "name"],
        order_by="creation asc",
    )
    # if a duplicate ever slips past the import lock, the oldest copy wins
    imported: dict[str, str] = {}
    for row in rows:
        imported.setdefault(row["from_template"], row["name"])
    return imported


@insights_whitelist()
def get_workbook_templates() -> list[dict]:
    """Templates whose required_apps are all installed. Empty on sites
    without ERPNext, so the gallery renders nothing there."""
    imported = get_imported_templates()
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
                "notes": manifest.get("notes"),
                "module": manifest.get("module"),
                "has_data": has_source_data(manifest),
                "preview_image": get_template_preview(name),
                # workbook the site already imported from the template, else None
                "imported_workbook": imported.get(name),
            }
        )
    return templates


def _find_imported_workbook(template_name: str) -> str | None:
    """The site's existing workbook for this template, if any (oldest wins)."""
    return frappe.db.get_value(
        "Insights Workbook",
        {"from_template": template_name},
        "name",
        order_by="creation asc",
    )


# child doctypes an imported workbook owns; kept in sync with InsightsWorkbook.on_trash
_WORKBOOK_CHILD_DOCTYPES = (
    "Insights Query v3",
    "Insights Chart v3",
    "Insights Dashboard v3",
    "Insights Folder",
)


def _reassign_to_administrator(workbook_name: str) -> None:
    """Own the imported workbook (and its children) as Administrator, so it's a
    shared org resource rather than tied to the admin who happened to click Import
    (and so only real admins can edit/delete it — everyone else reads via the share)."""
    frappe.db.set_value("Insights Workbook", workbook_name, "owner", "Administrator")
    for doctype in _WORKBOOK_CHILD_DOCTYPES:
        frappe.db.set_value(doctype, {"workbook": workbook_name}, "owner", "Administrator")


def _share_with_organization(workbook_name: str) -> None:
    """Implicit organization: view share — same shape update_share_permissions
    produces, so everyone with Insights access can read the shared copy."""
    share = DocShare.get_or_create_doc(
        share_doctype="Insights Workbook",
        share_name=workbook_name,
        everyone=1,
    )
    share.read = 1
    share.write = 0
    share.notify_by_email = 0
    share.save(ignore_permissions=True)


def _template_import_result(workbook_name: str) -> dict:
    """Workbook + its first dashboard, so the client can land on the dashboard."""
    first_dashboard = frappe.db.get_value(
        "Insights Dashboard v3",
        {"workbook": workbook_name},
        "name",
        order_by="creation asc",
    )
    return {"workbook": workbook_name, "dashboard": first_dashboard}


@insights_whitelist(role="Insights Admin")
def create_workbook_from_template(template_name: str) -> dict:
    from insights.insights.doctype.insights_workbook.insights_workbook import import_workbook

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

    # One shared copy per site. Serialize the check-then-insert so two admins
    # clicking simultaneously on a fresh site can't both create a copy.
    with filelock(f"insights_template_import_{template_name}", timeout=60):
        existing = _find_imported_workbook(template_name)
        if existing:
            return _template_import_result(existing)

        # Import as the caller (don't frappe.set_user mid-request — it rewrites the
        # session sid and logs the user out), then hand the copy to Administrator so
        # it becomes a shared org resource that everyone else reads via the share.
        workbook_name = import_workbook(get_template_workbook(template_name))
        # tag the origin so the gallery can mark this template as imported
        frappe.db.set_value("Insights Workbook", workbook_name, "from_template", template_name)
        _reassign_to_administrator(workbook_name)
        _share_with_organization(workbook_name)

    return _template_import_result(workbook_name)
