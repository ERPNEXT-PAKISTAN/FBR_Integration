import frappe
from frappe.utils import today


@frappe.whitelist()
def kpis(from_date=None, to_date=None):
    if not from_date:
        from_date = today()
    if not to_date:
        to_date = today()

    total = frappe.db.count("Sales Invoice", {"docstatus": 1, "posting_date": ["between", [from_date, to_date]]})
    success = frappe.db.count("FBR Sync Log", {"status": "Success"})
    failed = frappe.db.count("FBR Sync Log", {"status": "Failed"})
    pending = frappe.db.count("FBR Sync Log", {"status": "Pending"})

    return {
        "total_invoices": total,
        "success": success,
        "failed": failed,
        "pending": pending,
    }