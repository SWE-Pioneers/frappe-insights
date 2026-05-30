from contextlib import contextmanager

import frappe


class CircularQueryReferenceError(frappe.ValidationError):
    """Raised when a circular query reference is detected during query building."""

    pass


@contextmanager
def building(query_name: str, query_title: str | None = None):
    if not hasattr(frappe.local, "_insights_building_queries"):
        frappe.local._insights_building_queries = set()

    if query_name in frappe.local._insights_building_queries:
        title = query_title or query_name
        raise CircularQueryReferenceError(
            frappe._('Circular query reference detected while building "{0}"').format(title)
        )

    frappe.local._insights_building_queries.add(query_name)
    try:
        yield
    finally:
        frappe.local._insights_building_queries.discard(query_name)
