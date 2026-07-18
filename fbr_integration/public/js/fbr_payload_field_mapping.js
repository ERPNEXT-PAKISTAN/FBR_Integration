function set_source_field_options(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    const grid_field = frm.fields_dict.mappings.grid.get_field("source_field");

    if (!row.source_doctype) {
        grid_field.df.options = "";
        frm.refresh_field("mappings");
        return;
    }

    frappe.call({
        method: "fbr_integration.fbr_payload_mapping.get_doctype_field_options",
        args: { doctype: row.source_doctype },
        callback(r) {
            const options = (r.message || [])
                .map((field) => field.value)
                .join("\n");
            grid_field.df.options = options;
            frm.refresh_field("mappings");
        },
    });
}

frappe.ui.form.on("FBR Payload Field Mapping", {
    refresh(frm) {
        frm.set_query("source_doctype", "mappings", () => ({
            filters: {
                name: [
                    "in",
                    ["Sales Invoice", "Sales Invoice Item", "Address"],
                ],
            },
        }));
    },
});

frappe.ui.form.on("FBR Payload Field Mapping Detail", {
    form_render(frm, cdt, cdn) {
        set_source_field_options(frm, cdt, cdn);
    },
    source_doctype(frm, cdt, cdn) {
        frappe.model.set_value(cdt, cdn, "source_field", "");
        set_source_field_options(frm, cdt, cdn);
    },
});
