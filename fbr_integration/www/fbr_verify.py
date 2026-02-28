import frappe
from fbr_integration.fbr.signer import verify_signed, b64url_decode


def get_context(context):
    p = frappe.form_dict.get("p")
    s = frappe.form_dict.get("s")

    context.valid = False
    context.payload = None

    if not p or not s:
        return context

    settings = frappe.get_single("FBR Settings")
    secret = settings.qr_secret_key or ""
    if not secret:
        return context

    ok = verify_signed(p, s, secret)
    context.valid = ok

    if ok:
        import json
        context.payload = json.loads(b64url_decode(p).decode("utf-8"))

    return context