# Copyright (c) 2026, Santhiya and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, today


@frappe.whitelist()
def get_recommended_products(customer=None, skin_type=None):
	"""Fetch eligible saleable products with their applicable selling rates.

	Filters by skin type if specified without reloading the page.
	"""
	# Determine applicable Selling Price List
	price_list = None
	if customer:
		price_list = frappe.db.get_value("Customer", customer, "default_price_list")
	if not price_list:
		price_list = (
			frappe.db.get_single_value("Selling Settings", "selling_price_list")
			or "Standard Selling"
		)

	# Determine default currency
	company = (
		frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.db.get_value("Company", {}, "name")
	)
	currency = frappe.get_cached_value("Company", company, "default_currency") or "INR"

	# Build filters for eligible products
	filters = {
		"disabled": 0,
		"is_sales_item": 1,
		"has_variants": 0,
	}

	valid_skin_types = ["Oily", "Dry", "Combination", "Normal", "Sensitive"]
	if skin_type and skin_type in valid_skin_types:
		filters["custom_skin_type"] = skin_type

	items = frappe.get_all(
		"Item",
		filters=filters,
		fields=[
			"name as item_code",
			"item_name",
			"description",
			"custom_skin_type",
			"stock_uom",
			"standard_rate",
		],
		order_by="item_name asc",
	)

	# Fetch prices for all matching items
	for item in items:
		item_price = frappe.db.get_value(
			"Item Price",
			{
				"item_code": item.item_code,
				"price_list": price_list,
				"selling": 1,
			},
			"price_list_rate",
		)

		if item_price is not None and item_price != "":
			item["selling_rate"] = flt(item_price)
		else:
			item["selling_rate"] = flt(item.standard_rate or 0.0)

		item["currency"] = currency
		item["price_list"] = price_list
		# Clean description for display (strip raw HTML if any)
		if item.get("description"):
			item["description"] = frappe.utils.strip_html(item["description"])
		else:
			item["description"] = ""

	return {
		"items": items,
		"currency": currency,
		"price_list": price_list,
	}


@frappe.whitelist()
def place_product_order(customer, item_code, qty, delivery_date=None):
	"""Create a standalone Draft Sales Order for the selected customer and product."""
	# 1. Authorization check
	if not frappe.has_permission("Sales Order", "create"):
		frappe.throw(
			_("You do not have permission to create Sales Orders."),
			frappe.PermissionError,
		)

	# 2. Server-side Customer validation
	if not customer:
		frappe.throw(_("Please select a Customer before placing an order."), title=_("Missing Customer"))

	cust = frappe.db.get_value(
		"Customer",
		customer,
		["name", "disabled", "customer_name", "default_price_list", "default_currency"],
		as_dict=True,
	)
	if not cust:
		frappe.throw(
			_("Customer {0} does not exist in the system.").format(frappe.bold(customer)),
			title=_("Invalid Customer"),
		)
	if cust.disabled:
		frappe.throw(
			_("Customer {0} is disabled and cannot place orders.").format(frappe.bold(customer)),
			title=_("Customer Disabled"),
		)

	# 3. Server-side Item validation
	if not item_code:
		frappe.throw(_("Item code is required."), title=_("Missing Item"))

	item = frappe.db.get_value(
		"Item",
		item_code,
		["name", "disabled", "is_sales_item", "item_name", "stock_uom", "standard_rate"],
		as_dict=True,
	)
	if not item:
		frappe.throw(
			_("Item {0} does not exist.").format(frappe.bold(item_code)),
			title=_("Invalid Item"),
		)
	if item.disabled:
		frappe.throw(
			_("Item {0} is disabled and cannot be ordered.").format(frappe.bold(item_code)),
			title=_("Item Disabled"),
		)
	if not item.is_sales_item:
		frappe.throw(
			_("Item {0} is not marked as a sales item.").format(frappe.bold(item_code)),
			title=_("Item Not Saleable"),
		)

	# 4. Server-side Quantity validation
	quantity = flt(qty)
	if quantity <= 0:
		frappe.throw(
			_("Quantity must be greater than zero. Received: {0}").format(qty),
			title=_("Invalid Quantity"),
		)

	# 5. Price list and rate resolution
	price_list = (
		cust.default_price_list
		or frappe.db.get_single_value("Selling Settings", "selling_price_list")
		or "Standard Selling"
	)

	price_list_rate = frappe.db.get_value(
		"Item Price",
		{
			"item_code": item_code,
			"price_list": price_list,
			"selling": 1,
		},
		"price_list_rate",
	)

	if price_list_rate is not None and price_list_rate != "":
		rate = flt(price_list_rate)
	else:
		rate = flt(item.standard_rate or 0.0)

	if rate <= 0:
		frappe.throw(
			_("No valid selling rate found for Item {0} under Price List '{1}'. Please maintain an Item Price.").format(
				frappe.bold(item_code), frappe.bold(price_list)
			),
			title=_("Missing Item Price"),
		)

	# 6. Company and currency resolution
	company = (
		frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.db.get_value("Company", {}, "name")
	)
	currency = (
		cust.default_currency
		or frappe.get_cached_value("Company", company, "default_currency")
		or "INR"
	)

	# 7. Create Draft Sales Order document
	so = frappe.new_doc("Sales Order")
	so.customer = customer
	so.customer_name = cust.customer_name
	so.company = company
	so.currency = currency
	so.selling_price_list = price_list
	# Delivery date validation
	if delivery_date:
		if getdate(delivery_date) < getdate(today()):
			frappe.throw(_("Delivery Date cannot be in the past."), title=_("Invalid Delivery Date"))
		target_delivery_date = getdate(delivery_date)
	else:
		target_delivery_date = add_days(today(), 7)

	so.transaction_date = today()
	so.delivery_date = target_delivery_date

	so.append(
		"items",
		{
			"item_code": item_code,
			"item_name": item.item_name,
			"qty": quantity,
			"uom": item.stock_uom or "Nos",
			"stock_uom": item.stock_uom or "Nos",
			"price_list_rate": rate,
			"rate": rate,
			"amount": quantity * rate,
			"delivery_date": so.delivery_date,
		},
	)

	# Save in Draft status (docstatus = 0)
	so.insert(ignore_permissions=False)

	return {
		"status": "success",
		"sales_order": so.name,
		"message": _("Order placed successfully!"),
		"customer": customer,
		"item_code": item_code,
		"qty": quantity,
		"rate": rate,
		"total_amount": quantity * rate,
	}


@frappe.whitelist()
def place_bulk_product_order(customer, items, delivery_date=None):
	"""Create a single Draft Sales Order containing all selected products and their respective quantities."""
	# 1. Authorization check
	if not frappe.has_permission("Sales Order", "create"):
		frappe.throw(
			_("You do not have permission to create Sales Orders."),
			frappe.PermissionError,
		)

	# 2. Server-side Customer validation
	if not customer:
		frappe.throw(_("Please select a Customer before placing an order."), title=_("Missing Customer"))

	cust = frappe.db.get_value(
		"Customer",
		customer,
		["name", "disabled", "customer_name", "default_price_list", "default_currency"],
		as_dict=True,
	)
	if not cust:
		frappe.throw(
			_("Customer {0} does not exist in the system.").format(frappe.bold(customer)),
			title=_("Invalid Customer"),
		)
	if cust.disabled:
		frappe.throw(
			_("Customer {0} is disabled and cannot place orders.").format(frappe.bold(customer)),
			title=_("Customer Disabled"),
		)

	# 3. Parse and validate items list
	if isinstance(items, str):
		items = frappe.parse_json(items)

	if not items or len(items) == 0:
		frappe.throw(
			_("Please select at least one product to place an order."),
			title=_("No Products Selected"),
		)

	# 4. Resolve Selling Price List, Company & Currency
	price_list = (
		cust.default_price_list
		or frappe.db.get_single_value("Selling Settings", "selling_price_list")
		or "Standard Selling"
	)

	company = (
		frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.db.get_value("Company", {}, "name")
	)
	currency = (
		cust.default_currency
		or frappe.get_cached_value("Company", company, "default_currency")
		or "INR"
	)

	# 5. Build and validate Sales Order items
	so_items = []
	seen_items = set()

	for entry in items:
		item_code = entry.get("item_code")
		qty = flt(entry.get("qty", 1))

		if not item_code or item_code in seen_items:
			continue
		seen_items.add(item_code)

		item = frappe.db.get_value(
			"Item",
			item_code,
			["name", "disabled", "is_sales_item", "item_name", "stock_uom", "standard_rate"],
			as_dict=True,
		)
		if not item:
			frappe.throw(_("Item {0} does not exist.").format(frappe.bold(item_code)), title=_("Invalid Item"))
		if item.disabled:
			frappe.throw(_("Item {0} is disabled and cannot be ordered.").format(frappe.bold(item_code)), title=_("Item Disabled"))
		if not item.is_sales_item:
			frappe.throw(_("Item {0} is not a saleable product.").format(frappe.bold(item_code)), title=_("Item Not Saleable"))

		if qty <= 0:
			frappe.throw(
				_("Quantity for item {0} must be greater than zero. Received: {1}").format(
					frappe.bold(item.item_name or item_code), qty
				),
				title=_("Invalid Quantity"),
			)

		# Fetch rate from ERPNext Item Price
		price_list_rate = frappe.db.get_value(
			"Item Price",
			{
				"item_code": item_code,
				"price_list": price_list,
				"selling": 1,
			},
			"price_list_rate",
		)
		if price_list_rate is not None and price_list_rate != "":
			rate = flt(price_list_rate)
		else:
			rate = flt(item.standard_rate or 0.0)

		if rate <= 0:
			frappe.throw(
				_("No valid selling rate found for Item {0} under Price List '{1}'.").format(
					frappe.bold(item_code), frappe.bold(price_list)
				),
				title=_("Missing Item Price"),
			)

		so_items.append({
			"item_code": item_code,
			"item_name": item.item_name,
			"qty": qty,
			"uom": item.stock_uom or "Nos",
			"stock_uom": item.stock_uom or "Nos",
			"price_list_rate": rate,
			"rate": rate,
			"amount": qty * rate,
		})

	if not so_items:
		frappe.throw(_("No valid products found to order."), title=_("Empty Order"))

	# 6. Create one single Draft Sales Order
	so = frappe.new_doc("Sales Order")
	so.customer = customer
	so.customer_name = cust.customer_name
	so.company = company
	so.currency = currency
	so.selling_price_list = price_list
	# Delivery date validation
	if delivery_date:
		if getdate(delivery_date) < getdate(today()):
			frappe.throw(_("Delivery Date cannot be in the past."), title=_("Invalid Delivery Date"))
		target_delivery_date = getdate(delivery_date)
	else:
		target_delivery_date = add_days(today(), 7)

	so.transaction_date = today()
	so.delivery_date = target_delivery_date

	for row in so_items:
		row["delivery_date"] = so.delivery_date
		so.append("items", row)

	# Save in Draft status (docstatus = 0)
	so.insert(ignore_permissions=False)

	total_amount = sum(row["amount"] for row in so_items)

	return {
		"status": "success",
		"sales_order": so.name,
		"message": _("Order placed successfully!"),
		"customer": customer,
		"total_items": len(so_items),
		"total_amount": total_amount,
	}
