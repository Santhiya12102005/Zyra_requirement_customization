import frappe
from frappe.utils import getdate, today, add_days

def expiry_alert():
    today_date = today()
    expiry_date = add_days(today_date,30)

    batches = frappe.get_all(
        "Batch",
        filters={"expiry_date":["between",[today_date,expiry_date]]},
        fields=["name","item","expiry_date","batch_qty"]
    )

    users = frappe.get_all(
        "User",
        filters={"enabled":1},
        fields=["name","email"]
    )

    rec = []

    for u in users:
        role = frappe.get_roles(u.name)
        if "Stock Manager" in role:
            rec.append(u.email)
    
    for b in batches:

        message = f"""
        <h2>Batch Expires soon</h2>
        <p>Batch: {b.name}<br>
        Item: {b.item}<br>
        Expiry Date: {b.expiry_date}<br>
        Batch Quantity: {b.batch_qty}
        </p>
        """

        frappe.sendmail(
            recipients=rec,
            subject=f"""Batch Expiry Alert for batch {b.name}""",
            message=message
        )

def reorder_alert():

    reorder_items = frappe.get_all(
        "Item Reorder",
        fields=["parent","warehouse","warehouse_reorder_level","warehouse_reorder_qty"]
    )

    users = frappe.get_all(
        "User",
        filters={"enabled":1},
        fields=["name","email"]
    )

    rec = []

    for u in users:
        role = frappe.get_roles(u.name)
        if "Stock Manager" in role:
            rec.append(u.email)

    for item in reorder_items:
        actual_qty = frappe.db.get_value(
            "Bin",
            {
                "item_code":item.parent,
                "warehouse":item.warehouse
            },
            "actual_qty"
        )

        if actual_qty <= item.warehouse_reorder_level:
            message = f"""
            <p>Reorder the stock for {item.parent} in the warehouse {item.warehouse}.<br>
            Reorder Level: {item.warehouse_reorder_level}<br>
            Quantity to reorder: {item.warehouse_reorder_qty}<br>
            Actual Quantity in {item.warehouse} is {actual_qty}
            <p>
            """

            frappe.sendmail(
                recipients=rec,
                subject=f"""Reorder Alert for {item.parent}""",
                message=message
            )