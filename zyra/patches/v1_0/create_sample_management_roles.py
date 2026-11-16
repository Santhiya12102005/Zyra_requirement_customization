# Copyright (c) 2026, Santhiya and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Create custom roles for Product Sample Management."""
	roles = [
		{"role_name": "Sample User", "desk_access": 1},
		{"role_name": "Sample Manager", "desk_access": 1},
		{"role_name": "Feedback User", "desk_access": 1},
	]

	for r in roles:
		if not frappe.db.exists("Role", r["role_name"]):
			role_doc = frappe.get_doc(
				{
					"doctype": "Role",
					"role_name": r["role_name"],
					"desk_access": r["desk_access"],
				}
			)
			role_doc.insert(ignore_permissions=True)
