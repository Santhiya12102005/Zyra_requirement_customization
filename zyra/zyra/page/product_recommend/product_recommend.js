// Copyright (c) 2026, Santhiya and contributors
// For license information, please see license.txt

frappe.pages["product-recommend"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Product Recommendation"),
		single_column: true,
	});

	frappe.require("product_recommend.css");

	const manager = new ProductRecommendationManager(page);
	manager.init();
};

class ProductRecommendationManager {
	constructor(page) {
		this.page = page;
		this.wrapper = $(page.body);
		this.all_products = [];
		this.visible_products = [];
		this.selected_customer = "";
		this.selected_products = new Map(); // item_code -> { item_code, item_name, qty, rate }
		this.currency = frappe.defaults.get_default("currency") || "INR";
	}

	init() {
		this.setup_header_actions();
		this.setup_layout();
		this.setup_filter_controls();
		this.load_products();
	}

	setup_header_actions() {
		const me = this;
		this.page.set_secondary_action(
			__("Refresh"),
			function () {
				me.load_products();
			},
			"octicon octicon-sync"
		);
	}

	setup_layout() {
		this.wrapper.html(`
			<div class="product-recommend-container">
				<div class="recommend-filter-bar">
					<div class="row align-items-end">
						<div class="col-lg-3 col-md-6 col-sm-12 mb-2 mb-lg-0">
							<div class="filter-field-group">
								<label class="filter-label">
									<i class="fa fa-user text-primary mr-1"></i> ${__("Customer")} <span class="text-danger">*</span>
								</label>
								<div class="customer-control-wrapper"></div>
							</div>
						</div>
						<div class="col-lg-3 col-md-6 col-sm-12 mb-2 mb-lg-0">
							<div class="filter-field-group">
								<label class="filter-label">
									<i class="fa fa-filter text-info mr-1"></i> ${__("Skin Type")}
								</label>
								<div class="skin-type-control-wrapper"></div>
							</div>
						</div>
						<div class="col-lg-3 col-md-6 col-sm-12 mb-2 mb-lg-0">
							<div class="filter-field-group">
								<label class="filter-label">
									<i class="fa fa-calendar text-success mr-1"></i> ${__("Expected Delivery Date")} <span class="text-danger">*</span>
								</label>
								<div class="delivery-date-control-wrapper"></div>
							</div>
						</div>
						<div class="col-lg-3 col-md-6 col-sm-12 text-lg-right mb-2 mb-lg-0">
							<div class="d-flex align-items-center justify-content-lg-end flex-wrap" style="gap: 6px;">
								<button class="btn btn-default btn-sm btn-select-all" style="height: 30px; font-weight: 500;" title="${__("Select/Deselect all visible products")}">
									<i class="fa fa-check-square-o mr-1"></i> <span class="select-all-label">${__("Select All")}</span>
								</button>
								<button class="btn btn-default btn-sm btn-reset-filters" style="height: 30px; font-weight: 500;" title="${__("Reset all filters")}">
									<i class="fa fa-refresh mr-1"></i> ${__("Reset")}
								</button>
								<button class="btn btn-primary btn-sm btn-place-bulk-order" style="height: 30px; font-weight: 600;">
									<i class="fa fa-shopping-bag mr-1"></i> <span class="bulk-btn-label">${__("Place Order (0)")}</span>
								</button>
							</div>
						</div>
					</div>
					<div class="bulk-order-summary-row mt-2 pt-2 border-top d-flex justify-content-between align-items-center" style="display: none !important;">
						<span class="bulk-summary-count text-muted small font-weight-bold"></span>
						<span class="bulk-summary-amount text-dark small font-weight-bold"></span>
					</div>
				</div>
				<div class="recommend-grid-wrapper">
					<div class="recommend-grid" id="recommend-products-grid"></div>
				</div>
			</div>
		`);

		this.grid_container = this.wrapper.find("#recommend-products-grid");
		this.$bulk_btn = this.wrapper.find(".btn-place-bulk-order");
		this.$select_all_btn = this.wrapper.find(".btn-select-all");
		this.$summary_row = this.wrapper.find(".bulk-order-summary-row");
		this.$summary_count = this.wrapper.find(".bulk-summary-count");
		this.$summary_amount = this.wrapper.find(".bulk-summary-amount");

		const me = this;
		this.wrapper.find(".btn-reset-filters").on("click", function () {
			me.reset_filters();
		});

		this.$select_all_btn.on("click", function () {
			me.toggle_select_all();
		});

		this.$bulk_btn.on("click", function () {
			me.place_bulk_order();
		});
	}

	setup_filter_controls() {
		const me = this;

		// 1. Searchable Customer Dropdown (Fetches active Customers from ERPNext)
		this.customer_control = frappe.ui.form.make_control({
			parent: this.wrapper.find(".customer-control-wrapper"),
			df: {
				fieldtype: "Link",
				fieldname: "customer",
				placeholder: __("Search & Select Customer..."),
				options: "Customer",
				only_select: false,
				get_query: function () {
					return {
						filters: {
							disabled: 0,
						},
					};
				},
				change: function () {
					const val = (me.customer_control.get_value() || "").trim();
					me.selected_customer = val;
					me.on_customer_change();
				},
			},
			render_input: true,
		});
		this.customer_control.refresh();

		if (this.customer_control.$input) {
			this.customer_control.$input.on("change input blur", function () {
				const val = (me.customer_control.get_value() || $(this).val() || "").trim();
				if (val !== me.selected_customer) {
					me.selected_customer = val;
					me.on_customer_change();
				}
			});
		}

		// 2. Skin Type Select Dropdown (Oily, Dry, Combination, Normal, Sensitive)
		this.skin_type_control = frappe.ui.form.make_control({
			parent: this.wrapper.find(".skin-type-control-wrapper"),
			df: {
				fieldtype: "Select",
				fieldname: "skin_type",
				placeholder: __("All Skin Types"),
				options: [
					{ label: __("All Skin Types"), value: "" },
					{ label: "Oily", value: "Oily" },
					{ label: "Dry", value: "Dry" },
					{ label: "Combination", value: "Combination" },
					{ label: "Normal", value: "Normal" },
					{ label: "Sensitive", value: "Sensitive" },
				],
				change: function () {
					me.filter_products_locally();
				},
			},
			render_input: true,
		});
		this.skin_type_control.refresh();

		// 3. User-Selectable Expected Delivery Date Field
		const default_delivery_date = frappe.datetime.add_days(frappe.datetime.nowdate(), 7);
		this.delivery_date_control = frappe.ui.form.make_control({
			parent: this.wrapper.find(".delivery-date-control-wrapper"),
			df: {
				fieldtype: "Date",
				fieldname: "delivery_date",
				default: default_delivery_date,
				placeholder: __("Expected Delivery Date"),
				change: function () {
					const val = me.delivery_date_control.get_value();
					if (val && frappe.datetime.str_to_obj(val) < frappe.datetime.str_to_obj(frappe.datetime.nowdate())) {
						frappe.show_alert({
							message: __("Delivery Date cannot be in the past."),
							indicator: "orange",
						});
					}
				},
			},
			render_input: true,
		});
		this.delivery_date_control.set_value(default_delivery_date);
		this.delivery_date_control.refresh();
	}

	on_customer_change() {
		const customer = this.selected_customer || (this.customer_control ? this.customer_control.get_value() : "");
		this.load_products(customer);
	}

	reset_filters() {
		this.selected_customer = "";
		this.selected_products.clear();
		if (this.customer_control) {
			this.customer_control.set_value("");
		}
		if (this.skin_type_control) {
			this.skin_type_control.set_value("");
		}
		if (this.delivery_date_control) {
			this.delivery_date_control.set_value(frappe.datetime.add_days(frappe.datetime.nowdate(), 7));
		}
		this.load_products("");
	}

	load_products(customer) {
		const me = this;
		const cust = customer !== undefined ? customer : (this.selected_customer || (this.customer_control ? this.customer_control.get_value() : "") || "");

		frappe.call({
			method: "zyra.zyra.page.product_recommend.product_recommend.get_recommended_products",
			args: {
				customer: cust,
			},
			freeze: true,
			freeze_message: __("Loading eligible products..."),
			callback: function (r) {
				if (r.message) {
					me.all_products = r.message.items || [];
					me.currency = r.message.currency || "INR";
					me.filter_products_locally();
				}
			},
		});
	}

	filter_products_locally() {
		const selected_skin = this.skin_type_control
			? (this.skin_type_control.get_value() || "").trim()
			: "";

		let filtered = this.all_products;
		if (selected_skin) {
			filtered = this.all_products.filter(function (item) {
				return (item.custom_skin_type || "").trim() === selected_skin;
			});
		}

		this.visible_products = filtered;
		this.render_cards(filtered, selected_skin);
		this.update_bulk_ui();
	}

	render_cards(products, current_skin_filter) {
		const me = this;
		this.grid_container.empty();

		if (!products || products.length === 0) {
			const filter_msg = current_skin_filter
				? __("No products found matching skin type '{0}'.", [frappe.bold(current_skin_filter)])
				: __("No eligible saleable products available.");

			this.grid_container.html(`
				<div class="col-12" style="grid-column: 1 / -1;">
					<div class="recommend-empty-state">
						<i class="fa fa-tag"></i>
						<h4>${__("No Products Found")}</h4>
						<p>${filter_msg}</p>
					</div>
				</div>
			`);
			return;
		}

		products.forEach(function (product) {
			const card_html = me.get_card_html(product);
			const $card = $(card_html);

			const $checkbox = $card.find(".recommend-card-checkbox");
			const $qty_input = $card.find(".recommend-qty-input");
			const $btn_order = $card.find(".recommend-btn-order");

			// Checkbox change handler
			$checkbox.on("change", function () {
				const is_checked = $(this).is(":checked");
				const qty = parseFloat($qty_input.val()) || 1;
				me.toggle_product_selection(product, qty, is_checked, $card);
			});

			// Quantity input change handler
			$qty_input.on("change input", function () {
				const qty = parseFloat($(this).val()) || 1;
				if (me.selected_products.has(product.item_code)) {
					const item_data = me.selected_products.get(product.item_code);
					item_data.qty = qty;
					me.selected_products.set(product.item_code, item_data);
					me.update_bulk_ui();
				}
			});

			// Single product order button handler
			$btn_order.on("click", function () {
				const qty = parseFloat($qty_input.val()) || 1;
				me.place_single_order(product, qty, $btn_order);
			});

			me.grid_container.append($card);
		});
	}

	get_card_html(product) {
		const is_selected = this.selected_products.has(product.item_code);
		const selected_data = this.selected_products.get(product.item_code);
		const qty = selected_data ? selected_data.qty : 1;

		const skin_type = product.custom_skin_type || __("General");
		const badge_class = product.custom_skin_type
			? `badge-${product.custom_skin_type.toLowerCase()}`
			: "badge-all";

		const formatted_price = format_currency(product.selling_rate, product.currency || this.currency);
		const desc = product.description || __("No description provided.");

		return `
			<div class="recommend-card ${is_selected ? "selected" : ""}" data-item-code="${frappe.utils.escape_html(product.item_code)}">
				<div class="recommend-card-header">
					<div class="d-flex justify-content-between align-items-start">
						<div class="d-flex align-items-center" style="gap: 8px;">
							<input type="checkbox" 
								class="recommend-card-checkbox" 
								${is_selected ? "checked" : ""}
								title="${__("Select for bulk order")}">
							<h3 class="recommend-item-title mb-0">${frappe.utils.escape_html(product.item_name)}</h3>
						</div>
						<span class="recommend-badge ${badge_class}">${frappe.utils.escape_html(skin_type)}</span>
					</div>
					<div class="recommend-item-code" style="margin-left: 25px;">${frappe.utils.escape_html(product.item_code)}</div>
				</div>
				<div class="recommend-card-body">
					<p class="recommend-item-desc" title="${frappe.utils.escape_html(desc)}">
						${frappe.utils.escape_html(desc)}
					</p>
				</div>
				<div class="recommend-card-footer">
					<div class="recommend-price-row">
						<span class="recommend-price-label">${__("Selling Price")}</span>
						<span class="recommend-price-val">${formatted_price}</span>
					</div>
					<div class="recommend-action-row">
						<div class="input-group input-group-sm" style="width: 80px;">
							<input type="number" 
								class="form-control form-control-sm recommend-qty-input" 
								min="1" 
								step="1" 
								value="${qty}"
								title="${__("Quantity")}">
						</div>
						<button class="btn btn-outline-primary btn-sm recommend-btn-order" title="${__("Order this product individually")}">
							<i class="fa fa-shopping-cart"></i> ${__("Place Order")}
						</button>
					</div>
				</div>
			</div>
		`;
	}

	toggle_product_selection(product, qty, is_selected, $card) {
		if (is_selected) {
			this.selected_products.set(product.item_code, {
				item_code: product.item_code,
				item_name: product.item_name,
				qty: qty,
				rate: product.selling_rate,
			});
			$card.addClass("selected");
		} else {
			this.selected_products.delete(product.item_code);
			$card.removeClass("selected");
		}
		this.update_bulk_ui();
	}

	toggle_select_all() {
		const me = this;
		if (!this.visible_products || this.visible_products.length === 0) return;

		const all_selected = this.visible_products.every(function (p) {
			return me.selected_products.has(p.item_code);
		});

		this.visible_products.forEach(function (product) {
			const $card = me.grid_container.find(`.recommend-card[data-item-code="${product.item_code}"]`);
			const $checkbox = $card.find(".recommend-card-checkbox");
			const $qty_input = $card.find(".recommend-qty-input");
			const qty = parseFloat($qty_input.val()) || 1;

			if (all_selected) {
				me.selected_products.delete(product.item_code);
				$checkbox.prop("checked", false);
				$card.removeClass("selected");
			} else {
				me.selected_products.set(product.item_code, {
					item_code: product.item_code,
					item_name: product.item_name,
					qty: qty,
					rate: product.selling_rate,
				});
				$checkbox.prop("checked", true);
				$card.addClass("selected");
			}
		});

		this.update_bulk_ui();
	}

	update_bulk_ui() {
		const count = this.selected_products.size;
		this.wrapper.find(".bulk-btn-label").text(__("Place Order ({0})", [count]));

		if (count > 0) {
			let total_amount = 0;
			this.selected_products.forEach(function (item) {
				total_amount += (item.qty * (item.rate || 0));
			});

			this.$summary_count.html(`<i class="fa fa-check-circle text-success mr-1"></i> ${__("{0} products selected for order", [count])}`);
			this.$summary_amount.html(`${__("Total Estimated:")} <span class="text-primary">${format_currency(total_amount, this.currency)}</span>`);
			this.$summary_row.show();
			this.$bulk_btn.removeClass("btn-primary btn-default").addClass("btn-primary");
		} else {
			this.$summary_row.hide();
		}

		const all_visible_selected = this.visible_products.length > 0 && this.visible_products.every(p => this.selected_products.has(p.item_code));
		this.wrapper.find(".select-all-label").text(all_visible_selected ? __("Deselect All") : __("Select All"));
	}

	clear_selections() {
		this.selected_products.clear();
		this.grid_container.find(".recommend-card-checkbox").prop("checked", false);
		this.grid_container.find(".recommend-card").removeClass("selected");
		this.update_bulk_ui();
	}

	place_bulk_order() {
		const me = this;
		const customer = (this.selected_customer || (this.customer_control ? this.customer_control.get_value() : "") || "").trim();
		const delivery_date = this.delivery_date_control ? this.delivery_date_control.get_value() : "";

		// 1. Validation: Customer must be selected
		if (!customer) {
			frappe.msgprint({
				title: __("Customer Required"),
				indicator: "orange",
				message: __("Please select a Customer in the Customer dropdown above before placing an order."),
			});
			if (this.customer_control && this.customer_control.$input) {
				this.customer_control.$input.addClass("is-invalid").focus();
				setTimeout(function () {
					if (me.customer_control && me.customer_control.$input) {
						me.customer_control.$input.removeClass("is-invalid");
					}
				}, 4000);
			}
			return;
		}

		// 2. Validation: Delivery date must not be in past
		if (delivery_date && frappe.datetime.str_to_obj(delivery_date) < frappe.datetime.str_to_obj(frappe.datetime.nowdate())) {
			frappe.msgprint({
				title: __("Invalid Delivery Date"),
				indicator: "red",
				message: __("Expected Delivery Date cannot be in the past."),
			});
			if (this.delivery_date_control && this.delivery_date_control.$input) {
				this.delivery_date_control.$input.focus();
			}
			return;
		}

		// 3. Validation: At least one product must be selected
		if (this.selected_products.size === 0) {
			frappe.msgprint({
				title: __("No Products Selected"),
				indicator: "orange",
				message: __("Please select at least one product using the checkboxes before clicking Place Order."),
			});
			return;
		}

		// 4. Validation: All selected quantities must be > 0
		const items_payload = [];
		let invalid_item_name = null;

		this.selected_products.forEach(function (item) {
			if (!item.qty || isNaN(item.qty) || item.qty <= 0) {
				invalid_item_name = item.item_name;
			}
			items_payload.push({
				item_code: item.item_code,
				qty: item.qty,
			});
		});

		if (invalid_item_name) {
			frappe.msgprint({
				title: __("Invalid Quantity"),
				indicator: "red",
				message: __("Please enter a valid quantity greater than zero for {0}.", [
					frappe.bold(invalid_item_name),
				]),
			});
			return;
		}

		// 5. Anti-double submission lock
		const $btn = this.$bulk_btn;
		$btn.prop("disabled", true).html(`<i class="fa fa-spinner fa-spin mr-1"></i> ${__("Placing Order...")}`);

		frappe.call({
			method: "zyra.zyra.page.product_recommend.product_recommend.place_bulk_product_order",
			args: {
				customer: customer,
				items: items_payload,
				delivery_date: delivery_date,
			},
			callback: function (r) {
				$btn.prop("disabled", false);

				if (r.message && r.message.status === "success") {
					frappe.msgprint({
						title: __("Order Placed"),
						indicator: "green",
						message: __("Order placed successfully!<br><br>Draft Sales Order: <a href='/app/sales-order/{0}'><b>{0}</b></a><br>Products Included: <b>{1}</b> | Total: <b>{2}</b>", [
							r.message.sales_order,
							r.message.total_items,
							format_currency(r.message.total_amount, me.currency),
						]),
					});

					frappe.show_alert({
						message: __("Order placed successfully! ({0})", [r.message.sales_order]),
						indicator: "green",
					});

					me.clear_selections();
				} else {
					me.update_bulk_ui();
				}
			},
			error: function () {
				$btn.prop("disabled", false);
				me.update_bulk_ui();
			},
		});
	}

	place_single_order(product, qty, $button) {
		const me = this;
		const customer = (this.selected_customer || (this.customer_control ? this.customer_control.get_value() : "") || "").trim();
		const delivery_date = this.delivery_date_control ? this.delivery_date_control.get_value() : "";

		if (!customer) {
			frappe.msgprint({
				title: __("Customer Required"),
				indicator: "orange",
				message: __("Please select a Customer in the Customer dropdown above before placing an order."),
			});
			if (this.customer_control && this.customer_control.$input) {
				this.customer_control.$input.addClass("is-invalid").focus();
				setTimeout(function () {
					if (me.customer_control && me.customer_control.$input) {
						me.customer_control.$input.removeClass("is-invalid");
					}
				}, 4000);
			}
			return;
		}

		if (delivery_date && frappe.datetime.str_to_obj(delivery_date) < frappe.datetime.str_to_obj(frappe.datetime.nowdate())) {
			frappe.msgprint({
				title: __("Invalid Delivery Date"),
				indicator: "red",
				message: __("Expected Delivery Date cannot be in the past."),
			});
			if (this.delivery_date_control && this.delivery_date_control.$input) {
				this.delivery_date_control.$input.focus();
			}
			return;
		}

		if (!qty || isNaN(qty) || qty <= 0) {
			frappe.msgprint({
				title: __("Invalid Quantity"),
				indicator: "red",
				message: __("Please enter a valid quantity greater than zero for {0}.", [
					frappe.bold(product.item_name),
				]),
			});
			return;
		}

		$button.prop("disabled", true).html(`<i class="fa fa-spinner fa-spin"></i> ${__("Placing...")}`);

		frappe.call({
			method: "zyra.zyra.page.product_recommend.product_recommend.place_bulk_product_order",
			args: {
				customer: customer,
				items: [{ item_code: product.item_code, qty: qty }],
				delivery_date: delivery_date,
			},
			callback: function (r) {
				$button.prop("disabled", false).html(`<i class="fa fa-shopping-cart"></i> ${__("Place Order")}`);

				if (r.message && r.message.status === "success") {
					frappe.msgprint({
						title: __("Order Placed"),
						indicator: "green",
						message: __("Order placed successfully!<br><br>Draft Sales Order: <a href='/app/sales-order/{0}'><b>{0}</b></a>", [
							r.message.sales_order,
						]),
					});

					frappe.show_alert({
						message: __("Order placed successfully! ({0})", [r.message.sales_order]),
						indicator: "green",
					});

					if (me.selected_products.has(product.item_code)) {
						me.selected_products.delete(product.item_code);
						const $card = me.grid_container.find(`.recommend-card[data-item-code="${product.item_code}"]`);
						$card.find(".recommend-card-checkbox").prop("checked", false);
						$card.removeClass("selected");
						me.update_bulk_ui();
					}
				}
			},
			error: function () {
				$button.prop("disabled", false).html(`<i class="fa fa-shopping-cart"></i> ${__("Place Order")}`);
			},
		});
	}
}
