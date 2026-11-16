// Copyright (c) 2026, Santhiya and contributors
// For license information, please see license.txt

frappe.ui.form.on("Product Sample", {
	setup: function (frm) {
		// Filter item field in child table to only show active items
		frm.set_query("item", "sample_items", function () {
			return {
				filters: {
					disabled: 0,
				},
			};
		});

		// Filter customer field to only active customers
		frm.set_query("customer", function () {
			return {
				filters: {
					disabled: 0,
				},
			};
		});
	},

	refresh: function (frm) {
		frm.trigger("handle_status_display");
		frm.trigger("add_custom_buttons");
	},

	handle_status_display: function (frm) {
		// Set visual status indicator badge
		const color_map = {
			"Draft": "gray",
			"Sample Sent": "orange",
			"Feedback Received": "blue",
			"Accepted": "green",
			"Rejected": "red",
		};

		if (frm.doc.status && color_map[frm.doc.status]) {
			frm.page.set_indicator(frm.doc.status, color_map[frm.doc.status]);
		}

		// If Accepted or Rejected, make form read-only for regular users
		if (["Accepted", "Rejected"].includes(frm.doc.status)) {
			if (!frappe.user.has_role(["System Manager", "Sample Manager"])) {
				frm.disable_save();
			}
		}
	},

	add_custom_buttons: function (frm) {
		if (frm.is_new()) return;

		// 1. Action: Mark as Sample Sent (auto-creates Draft Delivery Note)
		if (frm.doc.status === "Draft") {
			frm.add_custom_button(__("Mark as Sample Sent"), function () {
				frappe.confirm(
					__("Are you sure you want to mark this sample as Sent to the customer? A Draft Delivery Note will be automatically created."),
					function () {
						frappe.call({
							method: "zyra.zyra.doctype.product_sample.product_sample.mark_sample_sent",
							args: {
								sample_name: frm.doc.name,
							},
							freeze: true,
							freeze_message: __("Updating status and generating Draft Delivery Note..."),
							callback: function (r) {
								if (!r.exc) {
									frm.reload_doc();
									const dn_msg = r.message && r.message.delivery_note
										? __(" and Draft Delivery Note {0} was created.", [r.message.delivery_note])
										: ".";
									frappe.show_alert({
										message: __("Product Sample status updated to 'Sample Sent'{0}", [dn_msg]),
										indicator: "green",
									});
								}
							},
						});
					}
				);
			}).addClass("btn-primary");
		}

		// 2. Action: Create or View Delivery Note
		if (frm.doc.status !== "Draft") {
			frm.add_custom_button(__("Create Delivery Note"), function () {
				frappe.confirm(
					__("Create a new Draft Delivery Note for this Product Sample?"),
					function () {
						frappe.call({
							method: "zyra.zyra.doctype.product_sample.product_sample.make_delivery_note",
							args: {
								source_name: frm.doc.name,
							},
							freeze: true,
							freeze_message: __("Creating Draft Delivery Note..."),
							callback: function (r) {
								if (r.message) {
									frm.reload_doc();
									frappe.show_alert({
										message: __("Draft Delivery Note {0} created.", [r.message]),
										indicator: "green",
									});
									frappe.set_route("Form", "Delivery Note", r.message);
								}
							},
						});
					}
				);
			}, __("Fulfillment"));
		}

		if (frm.doc.delivery_note) {
			frm.add_custom_button(__("View Delivery Note"), function () {
				frappe.set_route("Form", "Delivery Note", frm.doc.delivery_note);
			}, __("Fulfillment"));
		}

		// 3. Action: Record Customer Feedback
		if (frm.doc.status === "Sample Sent") {
			frm.add_custom_button(__("Record Feedback"), function () {
				frappe.new_doc("Product Sample Feedback", {
					product_sample: frm.doc.name,
					customer: frm.doc.customer,
				});
			}).addClass("btn-primary");
		}

		// 4. Action: Create Sales Order when Accepted
		if (frm.doc.status === "Accepted") {
			frm.add_custom_button(__("Create Sales Order"), function () {
				frappe.call({
					method: "zyra.zyra.doctype.product_sample.product_sample.make_sales_order",
					args: {
						source_name: frm.doc.name,
					},
					freeze: true,
					freeze_message: __("Preparing Sales Order..."),
					callback: function (r) {
						if (r.message) {
							const doc = frappe.model.sync(r.message);
							frappe.set_route("Form", doc[0].doctype, doc[0].name);
						}
					},
				});
			}, __("Actions")).addClass("btn-primary");
		}
	},
});
