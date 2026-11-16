// Copyright (c) 2026, Santhiya and contributors
// For license information, please see license.txt

frappe.ui.form.on("Product Sample Feedback", {
	setup: function (frm) {
		// Only display Product Samples that have status 'Sample Sent'
		frm.set_query("product_sample", function () {
			return {
				filters: {
					status: "Sample Sent",
				},
			};
		});
	},

	refresh: function (frm) {
		// If linked to a product sample, show a link button to view it
		if (frm.doc.product_sample) {
			frm.add_custom_button(
				__("View Product Sample"),
				function () {
					frappe.set_route("Form", "Product Sample", frm.doc.product_sample);
				},
				__("Links")
			);
		}
	},

	product_sample: function (frm) {
		if (!frm.doc.product_sample) {
			frm.set_value("customer", "");
			return;
		}

		// Fetch customer and check status from the selected sample
		frappe.db.get_value(
			"Product Sample",
			frm.doc.product_sample,
			["customer", "status"],
			function (value) {
				if (value) {
					frm.set_value("customer", value.customer);
					if (value.status !== "Sample Sent") {
						frappe.msgprint({
							title: __("Invalid Sample Status"),
							indicator: "orange",
							message: __(
								"Note: Selected Product Sample status is '{0}'. Feedback should only be submitted for samples marked as 'Sample Sent'.",
								[value.status]
							),
						});
					}
				}
			}
		);
	},
});
