# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# GNU GPLv3 License. See license.txt

from __future__ import unicode_literals

import frappe
from frappe.translate import get_user_lang
from frappe.utils.jinja_globals import is_rtl

no_cache = 1


def get_context(context):
    csrf_token = frappe.sessions.get_csrf_token()
    frappe.db.commit()
    context.csrf_token = csrf_token
    context.site_name = frappe.local.site
    context.lang = get_user_lang()
    context.text_direction = "rtl" if is_rtl() else "ltr"
