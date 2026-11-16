# Copyright (c) 2026, Santhiya and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""Create custom fields on standard ERPNext DocTypes for Zyra Product Sample integration."""
	custom_fields = {
		"Sales Order": [
			{
				"fieldname": "custom_product_sample",
				"label": "Product Sample Reference",
				"fieldtype": "Link",
				"options": "Product Sample",
				"insert_after": "customer_name",
				"read_only": 0,
				"description": "Linked Product Sample that led to this Sales Order.",
			}
		],
		"Delivery Note": [
			{
				"fieldname": "custom_product_sample",
				"label": "Product Sample Reference",
				"fieldtype": "Link",
				"options": "Product Sample",
				"insert_after": "customer_name",
				"read_only": 0,
				"description": "Linked Product Sample for which free sample stock was dispatched.",
			}
		],
	}

	create_custom_fields(custom_fields, update=True)
