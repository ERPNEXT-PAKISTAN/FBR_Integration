const FBR_MAPPING_TABLES = ["header_mappings", "item_mappings", "mappings"];

function get_mapping_grid(frm, parentfield) {
    const table = frm.fields_dict[parentfield];
    return table && table.grid;
}

function set_grid_source_doctype_query(frm) {
    FBR_MAPPING_TABLES.forEach((table_field) => {
        if (!frm.fields_dict[table_field]) return;
        frm.set_query("source_doctype", table_field, () => ({
            filters: {
                name: [
                    "in",
                    ["Sales Invoice", "Sales Invoice Item", "Address"],
                ],
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

function apply_source_field_options(frm, cdt, cdn, options) {
    const row = locals[cdt][cdn];
    const option_text = (options || []).map((field) => field.value).join("\n");

    FBR_MAPPING_TABLES.forEach((table_field) => {
        const grid = get_mapping_grid(frm, table_field);
        if (!grid) return;
        const grid_field = grid.get_field("source_field");
        if (grid_field) {
            grid_field.df.options = option_text;
        }
    });

    const grid = get_mapping_grid(frm, row.parentfield);
    const grid_row = grid && grid.grid_rows_by_docname[cdn];
    const source_field = grid_row?.grid_form?.fields_dict?.source_field;
    if (source_field) {
        source_field.df.options = option_text;
        source_field.refresh();
    }

    frm.refresh_field(row.parentfield);
}

function set_source_field_options(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.source_doctype) {
        apply_source_field_options(frm, cdt, cdn, []);
        return;
    }

    frappe.call({
        method: "fbr_integration.fbr_payload_mapping.get_doctype_field_options",
        args: { doctype: row.source_doctype },
        callback(r) {
            apply_source_field_options(frm, cdt, cdn, r.message || []);
        },
    });
}

frappe.ui.form.on("FBR Payload Field Mapping", {
    refresh(frm) {
        set_grid_source_doctype_query(frm);
    },
});

frappe.ui.form.on("FBR Payload Field Mapping Detail", {
    form_render(frm, cdt, cdn) {
        set_payload_section_from_table(cdt, cdn);
        set_source_field_options(frm, cdt, cdn);
    },
    source_doctype(frm, cdt, cdn) {
        set_payload_section_from_table(cdt, cdn);
        frappe.model.set_value(cdt, cdn, "source_field", "");
        set_source_field_options(frm, cdt, cdn);
    },
});
