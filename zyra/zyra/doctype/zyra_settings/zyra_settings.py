# Copyright (c) 2026, Santhiya and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ZyraSettings(Document):
	def validate(self):
		if self.max_active_samples_per_customer and self.max_active_samples_per_customer < 1:
			frappe.throw(_("Max Pending Samples per Customer must be at least 1."))

		if self.max_sample_items_per_request and self.max_sample_items_per_request < 1:
			frappe.throw(_("Max Products per Sample Request must be at least 1."))
