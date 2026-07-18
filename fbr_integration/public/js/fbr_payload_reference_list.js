function add_fbr_payload_list_button(listview) {
    listview.page.add_inner_button(
        __("View Payload JSON"),
        window.fbr_integration.payload_reference.show_payload_json
    );
}

[
    "FBR Payload Field Mapping",
    "FBR Payload Field",
    "FBR Payload Source Field",
].forEach((doctype) => {
    frappe.listview_settings[doctype] = frappe.listview_settings[doctype] || {};
    frappe.listview_settings[doctype].onload = add_fbr_payload_list_button;
});
