function show_fbr_payload_json() {
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
}

function add_fbr_payload_json_button(frm) {
    frm.add_custom_button(__("View Payload JSON"), show_fbr_payload_json);
}

[
    "FBR Payload Field Mapping",
    "FBR Payload Field",
    "FBR Payload Source Field",
].forEach((doctype) => {
    frappe.ui.form.on(doctype, {
        refresh(frm) {
            add_fbr_payload_json_button(frm);
        },
    });
});
