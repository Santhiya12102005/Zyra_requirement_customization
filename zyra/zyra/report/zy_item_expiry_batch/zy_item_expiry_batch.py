# Copyright (c) 2026, Santhiya and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, today, date_diff

def execute(filters = None):
	columns = [
		{
			"label":"Batch",
			"fieldname":"name",
			"fieldtype":"Link",
			"options":"Batch",
		},
		{
			"label":"Item",
			"fieldname":"item",
			"fieldtype":"Link",
			"options":"Item",
		},
		{
			"label":"Expiry date",
			"fieldname":"expiry_date",
			"fieldtype":"Date"
		},
		{
			"label":"Batch Quantity",
			"fieldname":"batch_qty",
			"fieldtype":"Int"
		},
		{
			"label":"Remaining Days",
			"fieldname":"rem_days",
			"fieldtype":"Int"
		},
		{
			"label":"Status",
			"fieldname":"status",
			"fieldtype":"Data"
		},	
	]

	batches = frappe.get_all(
		"Batch",
		filters={
			"expiry_date":["is","set"],
			"disabled":0,
		},
		fields=["name","item","expiry_date","batch_qty"],
		order_by="expiry_date"
	)

	counts = {"Expired":0,"Expiring Soon":0,"Good":0}

	for b in batches:
		b["rem_days"] = date_diff(b.expiry_date,today())

		if b["rem_days"] < 0:
			b["status"] = "Expired"
		elif b["rem_days"] <= 30:
			b["status"] = "Expiring Soon"
		else:
			b["status"] = "Good"
		counts[b["status"]] += 1

	chart = {
		"data":{
			"labels":list(counts.keys()),
			"datasets":[{"name":"Batch","values":list(counts.values())}]
		},
		"type":"bar"
	}

	return columns,batches,None,chart