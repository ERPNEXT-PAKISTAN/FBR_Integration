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

function get_source_field_control(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    const grid = get_mapping_grid(frm, row.parentfield);
    const grid_row = grid && grid.grid_rows_by_docname[cdn];

    return (
        grid_row?.grid_form?.fields_dict?.source_field ||
        grid_row?.columns?.source_field?.field ||
        null
    );
}

function apply_source_field_options(frm, cdt, cdn, options) {
    const row = locals[cdt][cdn];
    const option_values = (options || []).map((field) => field.value);
    const option_text = option_values.join("\n");

    const grid = get_mapping_grid(frm, row.parentfield);
    const grid_field = grid && grid.get_field("source_field");
    if (grid_field) {
        grid_field.df.options = option_text;
    }

    const source_field = get_source_field_control(frm, cdt, cdn);
    if (!source_field) {
        frm.refresh_field(row.parentfield);
        return;
    }

    source_field.df.options = option_values;
    source_field.set_data(options || []);
    source_field.refresh();
}

function load_source_field_options(frm, cdt, cdn) {
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
        set_grid_queries(frm);
    },
});

frappe.ui.form.on("FBR Payload Field Mapping Detail", {
    form_render(frm, cdt, cdn) {
        set_payload_section_from_table(cdt, cdn);
        load_source_field_options(frm, cdt, cdn);
    },
    source_doctype(frm, cdt, cdn) {
        set_payload_section_from_table(cdt, cdn);
        frappe.model.set_value(cdt, cdn, "source_field", "");
        load_source_field_options(frm, cdt, cdn);
    },
});
