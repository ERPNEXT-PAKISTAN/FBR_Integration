const FBR_MAPPING_TABLES = ["header_mappings", "item_mappings", "mappings"];

function get_mapping_grid(frm, parentfield) {
    const table = frm.fields_dict[parentfield];
    return table && table.grid;
}

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

function get_field_query(row) {
    return {
        query: "fbr_integration.fbr_payload_mapping.search_doctype_fields",
        params: {
            source_doctype: row.source_doctype || "",
        },
        translate_values: false,
    };
}

function source_field_query(doc, cdt, cdn) {
    const row = (cdt && cdn && locals[cdt] && locals[cdt][cdn]) || doc || {};
    return get_field_query(row);
}

function set_source_field_query(frm, cdt, cdn) {
    const row = locals[cdt][cdn];

    FBR_MAPPING_TABLES.forEach((table_field) => {
        const grid = get_mapping_grid(frm, table_field);
        if (!grid) return;

        const grid_field = grid.get_field("source_field");
        if (grid_field) {
            grid_field.df.get_query = source_field_query;
        }
    });

    const grid = get_mapping_grid(frm, row.parentfield);
    const grid_row = grid && grid.grid_rows_by_docname[cdn];
    const source_field = grid_row?.grid_form?.fields_dict?.source_field;
    if (source_field) {
        source_field.get_query = source_field_query;
        source_field.df.get_query = source_field.get_query;
        source_field.set_data([]);
        source_field.refresh();
    }
}

frappe.ui.form.on("FBR Payload Field Mapping", {
    refresh(frm) {
        set_grid_queries(frm);
    },
});

frappe.ui.form.on("FBR Payload Field Mapping Detail", {
    form_render(frm, cdt, cdn) {
        set_payload_section_from_table(cdt, cdn);
        set_source_field_query(frm, cdt, cdn);
    },
    source_doctype(frm, cdt, cdn) {
        set_payload_section_from_table(cdt, cdn);
        frappe.model.set_value(cdt, cdn, "source_field", "");
        set_source_field_query(frm, cdt, cdn);
    },
});
