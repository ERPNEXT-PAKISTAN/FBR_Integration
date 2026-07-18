const FBR_MAPPING_TABLES = ["header_mappings", "item_mappings", "mappings"];

function get_allowed_doctypes() {
    return ["Sales Invoice", "Sales Invoice Item", "Address"];
}

function set_grid_queries(frm) {
    FBR_MAPPING_TABLES.forEach((table_field) => {
        if (!frm.fields_dict[table_field]) return;

        frm.set_query("source_doctype", table_field, () => ({
            filters: {
                name: ["in", get_allowed_doctypes()],
            },
        }));

        frm.set_query("source_field", table_field, (doc, cdt, cdn) => {
            const row = locals[cdt][cdn];
            return {
                filters: {
                    source_doctype: row.source_doctype || "",
                },
            };
        });
    });
}

function set_payload_section_from_table(cdt, cdn) {
    const row = locals[cdt][cdn];
    if (
        row.parentfield === "header_mappings" &&
        row.payload_section !== "Header"
    ) {
        frappe.model.set_value(cdt, cdn, "payload_section", "Header");
    }
    if (row.parentfield === "item_mappings" && row.payload_section !== "Item") {
        frappe.model.set_value(cdt, cdn, "payload_section", "Item");
    }
}

frappe.ui.form.on("FBR Payload Field Mapping", {
    setup(frm) {
        set_grid_queries(frm);
    },
    refresh(frm) {
        set_grid_queries(frm);
    },
});

frappe.ui.form.on("FBR Payload Field Mapping Detail", {
    form_render(frm, cdt, cdn) {
        set_payload_section_from_table(cdt, cdn);
        set_grid_queries(frm);
    },
    source_doctype(frm, cdt, cdn) {
        set_payload_section_from_table(cdt, cdn);
        frappe.model.set_value(cdt, cdn, "source_field", "");
        set_grid_queries(frm);
    },
});
