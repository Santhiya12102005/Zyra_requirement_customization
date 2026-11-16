import frappe
from frappe import _
from frappe.utils import getdate


def check_expiry(doc, method=None):
	for item in doc.items:
		batch_exp_date = frappe.db.get_value("Batch", {"item": item.item_code}, "expiry_date")

		if batch_exp_date and getdate(item.delivery_date) >= getdate(batch_exp_date):
			frappe.throw(
				title="Expiry Warning",
				msg=_("Row {0} item {1} is expire when it will deliver to the customer").format(
					item.idx, item.item_code
				),
			)


def validate_sample_link(doc, method=None):
	"""Ensure that linked Product Sample matches the customer and is Accepted."""
	if not getattr(doc, "custom_product_sample", None):
		return

	sample = frappe.db.get_value(
		"Product Sample", doc.custom_product_sample, ["customer", "status"], as_dict=True
	)
	if not sample:
		frappe.throw(
			_("Referenced Product Sample {0} does not exist.").format(doc.custom_product_sample),
			title=_("Invalid Sample Reference"),
		)

	# Validate customer match
	if sample.customer != doc.customer:
		frappe.throw(
			_("Product Sample {0} was issued to Customer {1}, but this Sales Order is for Customer {2}.").format(
				frappe.bold(doc.custom_product_sample),
				frappe.bold(sample.customer),
				frappe.bold(doc.customer),
			),
			title=_("Customer Mismatch"),
		)

	# Enforce Accepted status according to Zyra Settings
	restrict_to_accepted = frappe.db.get_single_value(
		"Zyra Settings", "restrict_sales_order_to_accepted_samples"
	)
	if restrict_to_accepted and sample.status != "Accepted":
		frappe.throw(
			_("Sales Order cannot be processed for Product Sample {0} because its status is '{1}'. Only 'Accepted' samples can proceed to Sales Order.").format(
				frappe.bold(doc.custom_product_sample), frappe.bold(sample.status)
			),
			title=_("Sample Not Accepted"),
		)


def validate_delivery_note_sample(doc, method=None):
	"""Ensure that sample Delivery Note matches customer."""
	if not getattr(doc, "custom_product_sample", None):
		return

	sample = frappe.db.get_value(
		"Product Sample", doc.custom_product_sample, ["customer", "status"], as_dict=True
	)
	if not sample:
		frappe.throw(
			_("Referenced Product Sample {0} does not exist.").format(doc.custom_product_sample),
			title=_("Invalid Sample Reference"),
		)

	# Validate customer match
	if sample.customer != doc.customer:
		frappe.throw(
			_("Product Sample {0} was issued to Customer {1}, but this Delivery Note is for Customer {2}.").format(
				frappe.bold(doc.custom_product_sample),
				frappe.bold(sample.customer),
				frappe.bold(doc.customer),
			),
			title=_("Customer Mismatch"),
		)



def on_delivery_note_submit(doc, method=None):
	"""When sample Delivery Note is submitted, deduct stock and update Product Sample status."""
	if not getattr(doc, "custom_product_sample", None):
		return

	sample_doc = frappe.get_doc("Product Sample", doc.custom_product_sample)
	sample_doc.delivery_note = doc.name

	# If still in Draft, advance status to Sample Sent because stock was physically dispatched
	if sample_doc.status == "Draft":
		sample_doc.status = "Sample Sent"

	sample_doc.save(ignore_permissions=True)
	sample_doc.add_comment(
		"Info",
		_("Stock deducted from inventory via submitted Delivery Note {0} (Free of charge sample dispatch).").format(
			frappe.bold(doc.name)
		),
	)


def on_delivery_note_cancel(doc, method=None):
	"""If sample Delivery Note is cancelled, log note on Product Sample."""
	if not getattr(doc, "custom_product_sample", None):
		return

	sample_doc = frappe.get_doc("Product Sample", doc.custom_product_sample)
	if sample_doc.delivery_note == doc.name:
		sample_doc.delivery_note = None
		sample_doc.save(ignore_permissions=True)
		sample_doc.add_comment(
			"Info",
			_("Delivery Note {0} was cancelled. Sample stock deduction was reversed in inventory.").format(
				frappe.bold(doc.name)
			),
		)
