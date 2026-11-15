import frappe
from frappe.utils import getdate
from frappe import _

def check_expiry(doc,method=None):
    for item in doc.items:
        batch_exp_date = frappe.db.get_value(
            "Batch",
            {"item":item.item_code},
            "expiry_date"
        )

        if getdate(item.delivery_date) >= getdate(batch_exp_date):
            frappe.throw(
                title="Expiry Warning",
                msg=_("Row {0} item {1} is expire when it will deliver to the customer").format(item.idx,item.item_code)
            )