# Copyright (c) 2026, Santhiya and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, getdate, today


class ProductSample(Document):
	def validate(self):
		self.validate_customer()
		self.validate_sample_date()
		self.validate_customer_limits()
		self.validate_items()
		self.validate_status_transition()

	def on_update(self):
		"""When status transitions to Sample Sent, ensure Draft Delivery Note is created."""
		if self.status == "Sample Sent" and not self.delivery_note:
			dn_name = create_draft_delivery_note(self)
			if dn_name and self.delivery_note != dn_name:
				frappe.db.set_value("Product Sample", self.name, "delivery_note", dn_name)
				self.delivery_note = dn_name
				self.add_comment(
					"Info",
					_("Draft Delivery Note {0} automatically created for sample dispatch. Stock will be deducted upon submission.").format(
						frappe.bold(dn_name)
					),
				)

	def validate_customer(self):
		"""Ensure customer is active and not disabled."""
		if not self.customer:
			frappe.throw(_("Customer is mandatory."), title=_("Missing Customer"))

		is_disabled = frappe.db.get_value("Customer", self.customer, "disabled")
		if is_disabled:
			frappe.throw(
				_("Customer {0} is disabled and cannot receive product samples.").format(
					frappe.bold(self.customer)
				),
				title=_("Customer Disabled"),
			)

	def validate_sample_date(self):
		"""Ensure sample date is not unreasonably in the future."""
		if self.sample_date and getdate(self.sample_date) > getdate(add_days(today(), 30)):
			frappe.throw(
				_("Sample Date cannot be more than 30 days in the future."),
				title=_("Invalid Sample Date"),
			)

	def validate_customer_limits(self):
		"""Enforce sample limits and policies defined in Zyra Settings."""
		if not self.is_new() or not self.customer:
			return

		# 0. Check whether multiple samples per customer are permitted
		allow_multiple = frappe.db.get_single_value(
			"Zyra Settings", "allow_multiple_samples_per_customer"
		)
		if not allow_multiple:
			existing_sample_count = frappe.db.count(
				"Product Sample",
				{"customer": self.customer, "name": ["!=", self.name or ""]},
			)
			if existing_sample_count > 0:
				frappe.throw(
					_("Customer {0} already has a Product Sample record. Multiple samples per customer are disabled in Zyra Settings.").format(
						frappe.bold(self.customer_name or self.customer)
					),
					title=_("Multiple Samples Disabled"),
				)

		# 1. Require feedback before issuing new sample check
		require_feedback = frappe.db.get_single_value(
			"Zyra Settings", "require_feedback_before_new_sample"
		)
		if require_feedback:
			pending_count = frappe.db.count(
				"Product Sample",
				{"customer": self.customer, "status": "Sample Sent"},
			)
			if pending_count > 0:
				frappe.throw(
					_("Customer {0} has {1} sample(s) awaiting customer feedback. Company policy requires feedback before dispatching new samples.").format(
						frappe.bold(self.customer_name or self.customer), pending_count
					),
					title=_("Pending Feedback Required"),
				)

		# 2. Max active samples limit
		max_active = (
			frappe.db.get_single_value("Zyra Settings", "max_active_samples_per_customer") or 3
		)
		active_count = frappe.db.count(
			"Product Sample",
			{"customer": self.customer, "status": ["in", ["Draft", "Sample Sent"]]},
		)
		if active_count >= max_active:
			frappe.throw(
				_("Customer {0} has reached the maximum permitted active/pending samples ({1}).").format(
					frappe.bold(self.customer_name or self.customer), max_active
				),
				title=_("Sample Quota Exceeded"),
			)

	def validate_items(self):
		"""Ensure items are valid, active, non-template, non-duplicate, and within limits."""
		if not self.sample_items or len(self.sample_items) == 0:
			frappe.throw(
				_("Please add at least one item to the Sample Items table."),
				title=_("Missing Sample Items"),
			)

		max_items = (
			frappe.db.get_single_value("Zyra Settings", "max_sample_items_per_request") or 5
		)
		if len(self.sample_items) > max_items:
			frappe.throw(
				_("Sample request cannot exceed {0} items (currently {1} items).").format(
					max_items, len(self.sample_items)
				),
				title=_("Sample Items Limit Exceeded"),
			)

		seen_items = set()
		for row in self.sample_items:
			if not row.item:
				frappe.throw(
					_("Row #{0}: Item cannot be empty.").format(row.idx),
					title=_("Missing Item"),
				)

			# Duplicate item check in same request
			if row.item in seen_items:
				frappe.throw(
					_("Row #{0}: Item {1} is already added in another row. Duplicate items in the same sample request are not allowed.").format(
						row.idx, frappe.bold(row.item)
					),
					title=_("Duplicate Item"),
				)
			seen_items.add(row.item)

			# Quantity check
			if not row.qty or row.qty <= 0:
				frappe.throw(
					_("Row #{0}: Quantity for item {1} must be greater than zero.").format(
						row.idx, frappe.bold(row.item)
					),
					title=_("Invalid Quantity"),
				)

			# Check if item is disabled
			is_disabled = frappe.db.get_value("Item", row.item, "disabled")
			if is_disabled:
				frappe.throw(
					_("Row #{0}: Item {1} is disabled and cannot be sampled.").format(
						row.idx, frappe.bold(row.item)
					),
					title=_("Item Disabled"),
				)

			# Check if item is a template item (has variants)
			has_variants = frappe.db.get_value("Item", row.item, "has_variants")
			if has_variants:
				frappe.throw(
					_("Row #{0}: Item {1} is a template item. Please select a specific variant item for sampling.").format(
						row.idx, frappe.bold(row.item)
					),
					title=_("Template Item Not Allowed"),
				)

	def validate_status_transition(self):
		"""Guard against illegal status changes and status tampering."""
		if self.is_new():
			if self.status not in ["Draft", "Sample Sent"]:
				frappe.throw(
					_("New Product Sample must start in 'Draft' or 'Sample Sent' status."),
					title=_("Invalid Initial Status"),
				)
			return

		old_status = frappe.db.get_value("Product Sample", self.name, "status")
		if not old_status:
			return

		# Protect terminal states: Accepted / Rejected cannot be modified unless by System/Sample Manager
		if old_status in ["Accepted", "Rejected"]:
			user_roles = frappe.get_roles(frappe.session.user)
			if "System Manager" not in user_roles and "Sample Manager" not in user_roles:
				frappe.throw(
					_("Product Sample {0} is in final status '{1}' and cannot be modified.").format(
						frappe.bold(self.name), frappe.bold(old_status)
					),
					title=_("Document Locked"),
				)

		# Cannot manually bypass from Draft or Sample Sent directly to Accepted/Rejected without feedback
		if old_status in ["Draft", "Sample Sent"] and self.status in ["Accepted", "Rejected"]:
			is_from_feedback = getattr(self.flags, "from_feedback", False)
			if not is_from_feedback:
				feedback_exists = frappe.db.exists(
					"Product Sample Feedback", {"product_sample": self.name}
				)
				if not feedback_exists:
					frappe.throw(
						_("Product Sample cannot be set to '{0}' directly without an official Customer Feedback record.").format(
							self.status
						),
						title=_("Feedback Required"),
					)


def create_draft_delivery_note(sample_doc):
	"""Create an ERPNext Delivery Note in Draft status with rate = 0 (Free Sample)."""
	company = (
		frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.db.get_value("Company", {}, "name")
	)

	default_warehouse = frappe.db.get_single_value("Zyra Settings", "default_sample_warehouse")

	dn = frappe.new_doc("Delivery Note")
	dn.customer = sample_doc.customer
	dn.customer_name = sample_doc.customer_name
	dn.company = company
	dn.posting_date = today()
	dn.custom_product_sample = sample_doc.name

	for row in sample_doc.sample_items:
		item_wh = (
			default_warehouse
			or frappe.db.get_value("Item Default", {"parent": row.item, "company": company}, "default_warehouse")
			or frappe.db.get_value("Item", row.item, "default_warehouse")
			or frappe.db.get_value("Stock Settings", None, "default_warehouse")
		)
		dn.append(
			"items",
			{
				"item_code": row.item,
				"item_name": row.item_name,
				"qty": row.qty,
				"uom": row.uom,
				"stock_uom": row.uom,
				"rate": 0.0,
				"amount": 0.0,
				"is_free_item": 1,
				"discount_percentage": 100.0,
				"warehouse": item_wh,
				"allow_zero_valuation_rate": 1,
			},
		)

	dn.insert(ignore_permissions=True)
	return dn.name


@frappe.whitelist()
def make_delivery_note(source_name):
	"""Generate a new Draft Delivery Note pre-filled from Product Sample."""
	sample = frappe.get_doc("Product Sample", source_name)
	dn_name = create_draft_delivery_note(sample)
	return dn_name


@frappe.whitelist()
def mark_sample_sent(sample_name):
	"""Mark Product Sample as Sample Sent and automatically create a Draft Delivery Note."""
	doc = frappe.get_doc("Product Sample", sample_name)

	# Permission check
	if not frappe.has_permission("Product Sample", "write", doc):
		frappe.throw(_("Not permitted to update this Product Sample."), frappe.PermissionError)

	if doc.status != "Draft":
		frappe.throw(
			_("Only samples in 'Draft' status can be marked as 'Sample Sent'. Current status is {0}.").format(
				doc.status
			)
		)

	doc.status = "Sample Sent"

	# Automatically create Draft Delivery Note if not already existing
	dn_name = create_draft_delivery_note(doc)
	if dn_name:
		doc.delivery_note = dn_name

	doc.save()
	doc.add_comment(
		"Info",
		_("Sample marked as Sent by {0}. Draft Delivery Note {1} created (Rate = 0). Stock will be deducted upon submission.").format(
			frappe.session.user, frappe.bold(doc.delivery_note or "")
		),
	)
	return {"status": doc.status, "delivery_note": doc.delivery_note}


@frappe.whitelist()
def make_sales_order(source_name):
	"""Generate an in-memory standard ERPNext Sales Order pre-filled from an Accepted Product Sample.

	Fetches the commercial price from the applicable Price List while leaving quantities editable.
	"""
	sample = frappe.get_doc("Product Sample", source_name)

	if sample.status != "Accepted":
		frappe.throw(
			_("Sales Order can only be generated for Accepted Product Samples. Current status is {0}.").format(
				sample.status
			),
			title=_("Sample Not Accepted"),
		)

	# Determine applicable Selling Price List
	company = (
		frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.db.get_value("Company", {}, "name")
	)

	price_list = (
		frappe.db.get_value("Customer", sample.customer, "default_price_list")
		or frappe.db.get_single_value("Selling Settings", "selling_price_list")
		or "Standard Selling"
	)

	# Create a standard Sales Order document in memory
	target = frappe.new_doc("Sales Order")
	target.customer = sample.customer
	target.customer_name = sample.customer_name
	target.company = company
	target.delivery_date = add_days(today(), 7)
	target.selling_price_list = price_list

	# Link custom field reference back to the Product Sample
	if hasattr(target, "custom_product_sample"):
		target.custom_product_sample = sample.name

	for row in sample.sample_items:
		# Fetch rate from ERPNext Item Price List
		price_list_rate = frappe.db.get_value(
			"Item Price",
			{
				"item_code": row.item,
				"price_list": price_list,
				"selling": 1,
			},
			"price_list_rate",
		)

		if not price_list_rate:
			# Fallback to standard_rate on Item master if not found in specific price list
			price_list_rate = frappe.db.get_value("Item", row.item, "standard_rate") or 0.0

		rate = float(price_list_rate)
		qty = float(row.qty)
		amount = qty * rate

		target.append(
			"items",
			{
				"item_code": row.item,
				"item_name": row.item_name,
				"qty": qty,
				"uom": row.uom,
				"stock_uom": row.uom,
				"price_list_rate": rate,
				"rate": rate,
				"amount": amount,
			},
		)

	return target.as_dict()
