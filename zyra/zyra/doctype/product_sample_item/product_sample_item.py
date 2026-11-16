# Copyright (c) 2026, Santhiya and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ProductSampleItem(Document):
	def validate(self):
		self.validate_qty()
		self.validate_item()

	def validate_qty(self):
		"""Ensure that sample quantity is strictly greater than zero."""
		if not self.qty or self.qty <= 0:
			frappe.throw(
				_("Row #{0}: Quantity for item {1} must be greater than zero.").format(
					self.idx, frappe.bold(self.item or "")
				),
				title=_("Invalid Quantity"),
			)

	def validate_item(self):
		"""Ensure the selected item is active and not a template item."""
		if not self.item:
			frappe.throw(
				_("Row #{0}: Item is mandatory.").format(self.idx),
				title=_("Missing Item"),
			)

		item_info = frappe.db.get_value("Item", self.item, ["disabled", "has_variants"], as_dict=True)
		if not item_info:
			return

		if item_info.disabled:
			frappe.throw(
				_("Row #{0}: Item {1} is disabled and cannot be selected for sampling.").format(
					self.idx, frappe.bold(self.item)
				),
				title=_("Item Disabled"),
			)

		if item_info.has_variants:
			frappe.throw(
				_("Row #{0}: Item {1} is a template item with variants. Please select a specific variant for sampling.").format(
					self.idx, frappe.bold(self.item)
				),
				title=_("Template Item Not Allowed"),
			)
