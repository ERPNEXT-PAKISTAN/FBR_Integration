frappe.provide("fbr_integration.payload_reference");

window.fbr_integration.payload_reference.show_payload_json = function () {
    frappe.call({
        method: "fbr_integration.fbr_payload_mapping.get_current_payload_sample",
        args: { scenario_id: "SN002" },
        callback(r) {
            const payload = r.message || {};
            const json = JSON.stringify(payload, null, 2);
            frappe.msgprint({
                title: __("Current FBR Payload JSON"),
                indicator: "blue",
                wide: true,
                message: `<pre style="background:#1f2937;color:#e5e7eb;padding:12px;border-radius:6px;font-size:12px;max-height:560px;overflow:auto;white-space:pre-wrap;word-break:break-word;font-family:monospace;">${frappe.utils.escape_html(
                    json
                )}</pre>`,
            });
        },
    });
};

window.fbr_integration.payload_reference.add_form_button = function (frm) {
    if (frm.__fbr_payload_json_button_added) return;
    frm.__fbr_payload_json_button_added = true;
    frm.add_custom_button(
        __("View Payload JSON"),
        window.fbr_integration.payload_reference.show_payload_json
    );
};

[
    "FBR Payload Field Mapping",
    "FBR Payload Field",
    "FBR Payload Source Field",
].forEach((doctype) => {
    frappe.ui.form.on(doctype, {
        refresh(frm) {
            window.fbr_integration.payload_reference.add_form_button(frm);
        },
    });
});
