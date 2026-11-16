# Copyright (c) 2026, Santhiya and contributors
# For license information, please see license.txt

import re
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class ProductSampleFeedback(Document):
	def validate(self):
		self.validate_customer_link()
		self.validate_sample_status()
		self.validate_feedback_dates()
		self.validate_duplicate_feedback()
		self.validate_feedback_content()
		self.validate_satisfaction()

	def validate_customer_link(self):
		"""Ensure customer matches the customer from the linked Product Sample."""
		if not self.product_sample:
			frappe.throw(_("Please select a Product Sample."), title=_("Missing Reference"))

		sample_customer = frappe.db.get_value("Product Sample", self.product_sample, "customer")
		if not sample_customer:
			frappe.throw(
				_("Referenced Product Sample {0} has no valid customer linked.").format(
					self.product_sample
				),
				title=_("Invalid Sample Reference"),
			)

		self.customer = sample_customer

	def validate_sample_status(self):
		"""Only allow feedback submission for a sample with status 'Sample Sent'."""
		sample_status = frappe.db.get_value("Product Sample", self.product_sample, "status")
		if not sample_status:
			frappe.throw(
				_("Referenced Product Sample {0} does not exist.").format(self.product_sample),
				title=_("Sample Not Found"),
			)

		# When creating new feedback, sample must be in 'Sample Sent'
		if self.is_new():
			if sample_status != "Sample Sent":
				frappe.throw(
					_("Feedback can only be recorded for samples with status 'Sample Sent'. Current status of {0} is '{1}'.").format(
						frappe.bold(self.product_sample), frappe.bold(sample_status)
					),
					title=_("Invalid Sample Status"),
				)

	def validate_feedback_dates(self):
		"""Ensure feedback date is realistic (not in the future, not before sample date)."""
		if not self.feedback_date:
			self.feedback_date = today()

		# 1. Not in the future
		if getdate(self.feedback_date) > getdate(today()):
			frappe.throw(
				_("Feedback Date cannot be in the future."),
				title=_("Invalid Feedback Date"),
			)

		# 2. Not before sample date
		sample_date = frappe.db.get_value("Product Sample", self.product_sample, "sample_date")
		if sample_date and getdate(self.feedback_date) < getdate(sample_date):
			frappe.throw(
				_("Feedback Date ({0}) cannot be earlier than the Sample Date ({1}). Customer cannot test a product before it was sent.").format(
					self.feedback_date, sample_date
				),
				title=_("Invalid Feedback Date"),
			)

	def validate_duplicate_feedback(self):
		"""Prevent duplicate feedback for the same Product Sample."""
		filters = {
			"product_sample": self.product_sample,
		}
		if not self.is_new():
			filters["name"] = ["!=", self.name]

		existing = frappe.db.get_value("Product Sample Feedback", filters, "name")
		if existing:
			frappe.throw(
				_("Feedback {0} already exists for Product Sample {1}. Duplicate feedback is not permitted.").format(
					frappe.bold(existing), frappe.bold(self.product_sample)
				),
				title=_("Duplicate Feedback Detected"),
			)

	def validate_feedback_content(self):
		"""Ensure feedback details are mandatory and not empty or whitespace."""
		clean_text = re.sub(r"<[^>]*>", "", self.feedback_details or "").strip()
		if not clean_text or len(clean_text) < 3:
			frappe.throw(
				_("Feedback Details is mandatory. Please provide a meaningful customer evaluation."),
				title=_("Mandatory Feedback"),
			)

	def validate_satisfaction(self):
		"""Ensure satisfaction decision is strictly 'Satisfied' or 'Not Satisfied'."""
		if self.satisfaction not in ["Satisfied", "Not Satisfied"]:
			frappe.throw(
				_("Satisfaction must be either 'Satisfied' or 'Not Satisfied'."),
				title=_("Invalid Satisfaction Value"),
			)

	def on_update(self):
		"""Automatically update the linked Product Sample status upon satisfaction decision."""
		self.update_product_sample_status()

	def update_product_sample_status(self):
		if self.satisfaction == "Satisfied":
			target_status = "Accepted"
		elif self.satisfaction == "Not Satisfied":
			target_status = "Rejected"
		else:
			return

		sample_doc = frappe.get_doc("Product Sample", self.product_sample)
		if sample_doc.status != target_status:
			sample_doc.flags.from_feedback = True
			sample_doc.status = target_status
			sample_doc.save(ignore_permissions=True)
			sample_doc.add_comment(
				"Info",
				_("Status automatically updated to '{0}' via Customer Feedback {1} (Satisfaction: {2})").format(
					frappe.bold(target_status), frappe.bold(self.name), frappe.bold(self.satisfaction)
				),
			)

	def on_trash(self):
		"""Revert sample status to 'Sample Sent' if the feedback record is deleted."""
		if not self.product_sample:
			return

		sample_status = frappe.db.get_value("Product Sample", self.product_sample, "status")
		if sample_status in ["Accepted", "Rejected"]:
			sample_doc = frappe.get_doc("Product Sample", self.product_sample)
			sample_doc.flags.from_feedback = True
			sample_doc.status = "Sample Sent"
			sample_doc.save(ignore_permissions=True)
			sample_doc.add_comment(
				"Info",
				_("Feedback {0} was removed. Status reverted back to 'Sample Sent'.").format(self.name),
			)
