function esc(s) {
    return frappe.utils.escape_html((s || "").toString());
}

function show_scenario_details(scenario_id) {
    const sid = (scenario_id || "").toString().trim().toUpperCase();
    if (!sid) return;
    const url = `/assets/fbr_integration/scenario_docs/${sid}.json`;
    fetch(url)
        .then(function (r) {
            if (!r.ok) throw new Error("Not found: " + sid);
            return r.json();
        })
        .then(function (data) {
            const sample_html = `<pre style="background:#f4f4f4;border:1px solid #ddd;border-radius:4px;padding:10px;font-size:11px;max-height:320px;overflow:auto;white-space:pre-wrap;word-break:break-all;">${esc(
                JSON.stringify(data.sample || {}, null, 2)
            )}</pre>`;
            const html = `
<div style="font-family:inherit;line-height:1.6;">
  <div style="margin-bottom:10px;">
    <span style="background:#e8f5e9;color:#2e7d32;font-weight:600;padding:3px 10px;border-radius:12px;font-size:13px;">${esc(
        data.id
    )}</span>
    <span style="font-size:16px;font-weight:600;margin-left:8px;">${esc(
        data.title
    )}</span>
  </div>
  <p style="color:#555;margin-bottom:12px;font-size:13px;">${esc(
      data.description
  )}</p>
  <div style="font-size:12px;font-weight:600;color:#333;margin-bottom:4px;">Sample Payload</div>
  ${sample_html}
</div>`;
            frappe.msgprint({
                title: __("Scenario Detail: {0}", [esc(data.id)]),
                indicator: "green",
                message: html,
                wide: true,
            });
        })
        .catch(function (err) {
            frappe.msgprint({
                title: __("Scenario Not Found"),
                indicator: "orange",
                message: __("Could not load details for scenario <b>{0}</b>.", [
                    esc(sid),
                ]),
            });
        });
}

let fbrScenarioIndexCache = null;
let fbrScenarioIndexError = null;

function clear_fbr_scenario_cache() {
    fbrScenarioIndexCache = null;
    fbrScenarioIndexError = null;
    console.log("[FBR] Scenario index cache cleared");
}

function load_scenario_index() {
    if (Array.isArray(fbrScenarioIndexCache)) {
        return Promise.resolve(fbrScenarioIndexCache);
    }

    if (fbrScenarioIndexError) {
        return Promise.reject(fbrScenarioIndexError);
    }

    console.log(
        "[FBR] Loading scenario index from /assets/fbr_integration/scenario_docs/index.json"
    );

    return fetch("/assets/fbr_integration/scenario_docs/index.json")
        .then(function (r) {
            if (!r.ok) {
                const err = new Error(
                    `Failed to load scenario index: HTTP ${r.status} ${r.statusText}`
                );
                console.error("[FBR]", err.message);
                fbrScenarioIndexError = err;
                throw err;
            }
            return r.json();
        })
        .then(function (rows) {
            if (!Array.isArray(rows)) {
                const err = new Error(
                    "Scenario index is not an array: " + typeof rows
                );
                console.error("[FBR]", err.message);
                fbrScenarioIndexError = err;
                throw err;
            }
            fbrScenarioIndexCache = rows;
            console.log(`[FBR] Loaded ${rows.length} scenarios from index`);
            return fbrScenarioIndexCache;
        })
        .catch(function (err) {
            fbrScenarioIndexError = err;
            console.error(
                "[FBR] Scenario index load failed:",
                err.message || err
            );
            throw err;
        });
}

function show_scenario_browser(frm) {
    load_scenario_index()
        .then(function (rows) {
            const dialog = new frappe.ui.Dialog({
                title: __("Scenario Index"),
                size: "large",
                fields: [
                    {
                        fieldtype: "Data",
                        fieldname: "search",
                        label: __("Search"),
                        default: "",
                    },
                    {
                        fieldtype: "HTML",
                        fieldname: "results",
                    },
                ],
            });

            const render_rows = function (query) {
                const q = (query || "").toString().toLowerCase().trim();
                const filtered = rows.filter(function (row) {
                    const hay = `${row.id || ""} ${row.title || ""} ${
                        row.description || ""
                    }`
                        .toLowerCase()
                        .trim();
                    return !q || hay.includes(q);
                });

                const html_rows = filtered
                    .map(function (row) {
                        return `
<div class="scenario-row" style="border:1px solid #ddd;border-radius:8px;padding:10px;margin-bottom:8px;">
  <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;">
    <div style="flex:1;min-width:0;">
      <div style="font-weight:700;font-size:14px;line-height:1.4;">${esc(
          row.id
      )} - ${esc(row.title)}</div>
      <div style="font-size:12px;color:#666;margin-top:4px;line-height:1.5;">${esc(
          row.description || ""
      )}</div>
    </div>
    <div style="display:flex;gap:6px;flex-shrink:0;">
      <button class="btn btn-default btn-sm btn-view" data-sid="${esc(
          row.id
      )}">${__("View")}</button>
      <button class="btn btn-primary btn-sm btn-use" data-sid="${esc(
          row.id
      )}">${__("Use")}</button>
    </div>
  </div>
</div>`;
                    })
                    .join("");

                const container = dialog.get_field("results").$wrapper;
                container.html(
                    filtered.length
                        ? `<div style="max-height:460px;overflow:auto;padding-right:4px;">${html_rows}</div>`
                        : `<div style="padding:12px;color:#777;">${__(
                              "No scenarios matched your search."
                          )}</div>`
                );

                container.find(".btn-view").on("click", function () {
                    const sid = ($(this).attr("data-sid") || "")
                        .toString()
                        .trim();
                    if (sid) show_scenario_details(sid);
                });

                container.find(".btn-use").on("click", function () {
                    const sid = ($(this).attr("data-sid") || "")
                        .toString()
                        .trim();
                    if (!sid) return;
                    frm.set_value("custom_scenario_id", sid);
                    frappe.show_alert({
                        message: __("Scenario selected: {0}", [sid]),
                        indicator: "green",
                    });
                    dialog.hide();
                });
            };

            dialog.show();
            render_rows("");

            dialog.get_field("search").$input.on("input", function () {
                render_rows($(this).val());
            });
        })
        .catch(function (err) {
            const errMsg = (err && err.message) || "Unknown error";
            console.error("[FBR] Scenario browser failed:", errMsg);
            frappe.msgprint({
                title: __("Scenario Index Not Available"),
                indicator: "red",
                message: `
<div style="font-size:13px;line-height:1.6;">
  <p><b>Could not load the FBR scenario catalog.</b></p>
  <p style="margin-top:8px;color:#666;font-size:12px;">${esc(errMsg)}</p>
  <p style="margin-top:12px;color:#333;">To resolve this issue:</p>
  <ol style="margin:8px 0;padding-left:20px;font-size:12px;">
    <li>Run: <code>fbr-build-scenarios</code></li>
    <li>Run: <code>bench build --app fbr_integration</code></li>
    <li>Run: <code>bench --site site1.local clear-cache</code></li>
    <li>Reload the page (Ctrl+Shift+R for hard refresh)</li>
  </ol>
  <p style="margin-top:8px;font-size:11px;color:#777;"><b>Debug:</b> Check browser console (F12) for logs with <code>[FBR]</code> prefix</p>
</div>`,
            });
        });
}

const FBR_PRINT_FORMAT = "FBR Sales Invoice";
const FBR_LOGO_URL = "/assets/fbr_integration/images/fbr/DI_invoicing.png";
const FBR_DEFAULT_SCENARIO = "Pakistan Tax";
const FBR_SCENARIO_OPTIONS = [
    "Manual Item-wise",
    "All Taxes",
    "Pakistan Tax",
    "Zero Rated",
    "Exempt",
    "Cement Per Qty",
];
const FBR_SCENARIO_APPLY_MODE_FILL = "Fill Empty Items";
const FBR_SCENARIO_APPLY_MODE_FORCE = "Update All Items";

const fbrScenarioTemplateCache = new Map();

function normalize_fbr_text(value) {
    return (value || "")
        .toString()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}

function get_effective_fbr_scenario(frm, row) {
    const rowScenario = (row && row.custom_fbr_item_scenario) || "";
    const invoiceScenario = frm.doc.custom_fbr_scenario || "";
    return (rowScenario || invoiceScenario).toString().trim();
}

function should_force_apply_scenario(frm, options = {}) {
    if (options.forceApply === true) return true;
    const mode = ((frm.doc && frm.doc.custom_fbr_scenario_apply_mode) || "")
        .toString()
        .trim();
    return mode === FBR_SCENARIO_APPLY_MODE_FORCE;
}

function should_auto_apply_scenario(frm, options = {}) {
    if (options.forceApply === true) return true;
    const mode = ((frm.doc && frm.doc.custom_fbr_scenario_apply_mode) || "")
        .toString()
        .trim();
    return (
        mode === FBR_SCENARIO_APPLY_MODE_FILL ||
        mode === FBR_SCENARIO_APPLY_MODE_FORCE
    );
}

function is_return_checked(doc) {
    return Number((doc && doc.is_return) || 0) === 1;
}

async function ensure_return_credit_note(frm, options = {}) {
    if (!frm || !frm.doc) return;

    if (!is_return_checked(frm.doc)) return;

    const currentType = (frm.doc.custom_invoice_type || "").toString().trim();
    if (currentType === "Credit Note") return;

    await frm.set_value("custom_invoice_type", "Credit Note");

    if (options.notify === true) {
        frappe.show_alert({
            message: __(
                "Invoice Type was set to Credit Note because this is a return invoice."
            ),
            indicator: "blue",
        });
    }
}

async function clear_fbr_response_fields(frm) {
    if (!frm || !frm.doc) return;

    // Clear FBR response fields for fresh return submission
    const fieldsToClean = [
        "custom_fbr_digital_invoice_response",
        "custom_fbr_invoice_no",
        "custom_fbr_responsed",
        "custom_fbr_qr_code",
        "custom_fbr_invoice_status",
        "custom_fbr_invoice_status_code",
        "custom_fbr_submission_time",
        "custom_fbr_invoice_statuses",
    ];

    for (const field of fieldsToClean) {
        if (field in frm.doc && frm.doc[field]) {
            await frm.set_value(field, "");
        }
    }
}

async function sync_return_source_invoice_no(frm) {
    if (!frm || !frm.doc) return;
    if (!is_return_checked(frm.doc)) return;

    const linkedInvoice = (frm.doc.return_against || "").toString().trim();
    if (!linkedInvoice) return;

    if ((frm.doc.custom_fbr_source_invoice_no || "").toString().trim()) return;

    const r = await frappe.db.get_value(
        "Sales Invoice",
        linkedInvoice,
        "custom_fbr_invoice_no"
    );

    const sourceFbrNo = (((r || {}).message || {}).custom_fbr_invoice_no || "")
        .toString()
        .trim();
    if (sourceFbrNo) {
        await frm.set_value("custom_fbr_source_invoice_no", sourceFbrNo);
    }
}

function build_missing_template_message(row, scenario) {
    const label = row.item_code || row.idx || __("row");
    return __(
        "No Item Tax Template found for {0} using scenario {1}. The Item Tax Template field was left empty.",
        [label, scenario]
    );
}

async function resolve_fbr_item_tax_template(scenario) {
    const key = normalize_fbr_text(scenario);

    if (!key) {
        return "";
    }

    if (!fbrScenarioTemplateCache.has(key)) {
        fbrScenarioTemplateCache.set(
            key,
            frappe
                .call({
                    method: "fbr_integration.api.resolve_item_tax_template_name",
                    args: { scenario },
                })
                .then((r) => (r.message || "").toString().trim())
        );
    }

    return await fbrScenarioTemplateCache.get(key);
}

async function apply_fbr_item_tax_template(frm, cdt, cdn, options = {}) {
    const localTable = (cdt && locals[cdt]) || {};
    const explicitRow = options.row || null;
    const row =
        explicitRow ||
        localTable[cdn] ||
        (frm.doc.items || []).find((d) => d.name === cdn);
    if (!row) return "";

    const notify = options.notify === true;
    const autoApply = should_auto_apply_scenario(frm, options);
    const forceApply = should_force_apply_scenario(frm, options);
    const scenario = get_effective_fbr_scenario(frm, row);
    const templateName = await resolve_fbr_item_tax_template(scenario);
    const currentTemplate = (row.item_tax_template || "").toString().trim();

    if (!autoApply) {
        return currentTemplate;
    }

    if (templateName) {
        if (forceApply || !currentTemplate) {
            await frappe.model.set_value(
                cdt,
                cdn,
                "item_tax_template",
                templateName
            );
            return templateName;
        }
        return currentTemplate;
    }

    // Keep manual template selection when no scenario mapping exists.
    if (currentTemplate) {
        return currentTemplate;
    }

    if (notify) {
        frappe.show_alert({
            message: build_missing_template_message(row, scenario),
            indicator: "orange",
        });
    }

    return "";
}

async function sync_fbr_item_tax_templates(frm, options = {}) {
    const targets = (frm.doc.items || [])
        .map((row) => ({
            cdt: row.doctype || "Sales Invoice Item",
            cdn: row.name,
            row,
        }))
        .filter((d) => d.cdn);

    const notify = options.notify === true;
    const autoApply = should_auto_apply_scenario(frm, options);
    const forceApply = should_force_apply_scenario(frm, options);
    const missing = [];
    const changedTargets = [];

    if (!autoApply) {
        return;
    }

    for (const target of targets) {
        const scenario = get_effective_fbr_scenario(frm, target.row);
        const templateName = await resolve_fbr_item_tax_template(scenario);

        const currentTemplate = (target.row.item_tax_template || "")
            .toString()
            .trim();
        const nextTemplate = (templateName || "").toString().trim();

        if (!nextTemplate) {
            if (!currentTemplate) {
                missing.push(
                    build_missing_template_message(target.row, scenario)
                );
            }
            continue;
        }

        if (forceApply || !currentTemplate) {
            target.row.item_tax_template = nextTemplate;
            changedTargets.push(target);
        }
    }

    if (changedTargets.length) {
        frm.dirty();
        frm.refresh_field("items");

        for (const target of changedTargets) {
            recalc_fbr_item_row(frm, target.cdt, target.cdn);
        }
    }

    if (notify && missing.length) {
        frappe.show_alert({
            message: missing.slice(0, 3).join("<br>"),
            indicator: "orange",
        });
    }
}

async function apply_invoice_scenario_to_all_items(frm, options = {}) {
    const notify = options.notify === true;
    const autoApply = should_auto_apply_scenario(frm, options);
    const forceApply = should_force_apply_scenario(frm, options);
    const rows = [...(frm.doc.items || [])];
    if (!rows.length) return;

    const scenario = (frm.doc.custom_fbr_scenario || "").toString().trim();
    const templateName = await resolve_fbr_item_tax_template(scenario);
    const targetTemplate = (templateName || "").toString().trim();
    const changedTargets = [];

    if (!autoApply) {
        return;
    }

    frm.__fbr_bulk_updating = true;
    try {
        for (const row of rows) {
            const cdt = row.doctype || "Sales Invoice Item";
            const cdn = row.name;
            const current = (row.item_tax_template || "").toString().trim();
            const currentItemScenario = (row.custom_fbr_item_scenario || "")
                .toString()
                .trim();
            const scenarioChanged = currentItemScenario !== scenario;

            if (scenarioChanged) {
                await frappe.model.set_value(
                    cdt,
                    cdn,
                    "custom_fbr_item_scenario",
                    scenario
                );
            }

            if (!targetTemplate) {
                if (scenarioChanged) {
                    changedTargets.push({ cdt, cdn });
                }
                continue;
            }

            if (forceApply ? current !== targetTemplate : !current) {
                await frappe.model.set_value(
                    cdt,
                    cdn,
                    "item_tax_template",
                    targetTemplate
                );
                changedTargets.push({ cdt, cdn });
            } else if (scenarioChanged) {
                changedTargets.push({ cdt, cdn });
            }
        }
    } finally {
        frm.__fbr_bulk_updating = false;
    }

    if (changedTargets.length) {
        frm.refresh_field("items");
        for (const target of changedTargets) {
            recalc_fbr_item_row(frm, target.cdt, target.cdn);
        }
    }

    if (notify && !targetTemplate) {
        frappe.show_alert({
            message: __(
                "No Item Tax Template found for scenario {0}. Existing manual Item Tax Template values were kept.",
                [scenario]
            ),
            indicator: "orange",
        });
    }
}

function setv(cdt, cdn, field, value) {
    frappe.model.set_value(cdt, cdn, field, value || 0);
}

function matches(tt, keys) {
    return keys.some((k) => tt.includes(k));
}

function recalc_fbr_item_row(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    const qty = parseFloat(row.qty) || 0;
    const rate = parseFloat(row.rate) || 0;
    const amount = qty * rate;

    setv(cdt, cdn, "amount", amount);

    setv(cdt, cdn, "custom_sales_tax_rate", 0);
    setv(cdt, cdn, "custom_further_tax_rate", 0);
    setv(cdt, cdn, "custom_extra_tax_rate", 0);

    setv(cdt, cdn, "custom_sales_tax", 0);
    setv(cdt, cdn, "custom_further_tax", 0);
    setv(cdt, cdn, "custom_extra_tax", 0);

    setv(cdt, cdn, "custom_total_tax_amount", 0);
    setv(cdt, cdn, "custom_tax_inclusive_amount", amount);

    if (!row.item_tax_template) {
        frm.refresh_field("items");
        return;
    }

    frappe.call({
        method: "fbr_integration.api.get_item_tax_template_rates",
        args: { template_name: row.item_tax_template },
        callback: function (r) {
            const res = r.message || [];
            if (!res.length) {
                frm.refresh_field("items");
                return;
            }

            let salesRate = 0,
                furtherRate = 0,
                extraRate = 0;

            res.forEach((tax) => {
                const tt = (tax.tax_type || "").toLowerCase();
                const rr = tax.tax_rate || 0;

                if (
                    matches(tt, [
                        "general sales tax",
                        "sales tax",
                        "gst",
                        "output tax",
                        "vat",
                    ])
                )
                    salesRate = rr;
                else if (matches(tt, ["further tax"])) furtherRate = rr;
                else if (matches(tt, ["extra tax"])) extraRate = rr;
            });

            if (res.length === 1 && salesRate === 0)
                salesRate = res[0].tax_rate || 0;

            const sales = (amount * salesRate) / 100;
            const further = (amount * furtherRate) / 100;
            const extra = (amount * extraRate) / 100;

            setv(cdt, cdn, "custom_sales_tax_rate", salesRate);
            setv(cdt, cdn, "custom_further_tax_rate", furtherRate);
            setv(cdt, cdn, "custom_extra_tax_rate", extraRate);

            setv(cdt, cdn, "custom_sales_tax", sales);
            setv(cdt, cdn, "custom_further_tax", further);
            setv(cdt, cdn, "custom_extra_tax", extra);

            const totalTax = sales + further + extra;
            setv(cdt, cdn, "custom_total_tax_amount", totalTax);
            setv(cdt, cdn, "custom_tax_inclusive_amount", amount + totalTax);

            frm.refresh_field("items");
        },
    });
}

function sync_qr_field_on_form(frm) {
    const fbrNo = (frm.doc.custom_fbr_invoice_no || "").trim();
    if (!fbrNo) return;

    // Only update in-memory for display; don't mark submitted forms as dirty
    if (
        "custom_fbr_qr_code" in frm.doc &&
        (frm.doc.custom_fbr_qr_code || "") !== fbrNo
    ) {
        frm.doc.custom_fbr_qr_code = fbrNo;
    }
    if (
        "custom_qr_code" in frm.doc &&
        (frm.doc.custom_qr_code || "") !== fbrNo
    ) {
        frm.doc.custom_qr_code = fbrNo;
    }
}

function render_qr_preview(frm) {
    if (!frm.fields_dict.custom_qr_code) return;
    const fbrNo = (frm.doc.custom_fbr_invoice_no || "").trim();
    if (!fbrNo) {
        frm.set_df_property(
            "custom_qr_code",
            "options",
            '<div class="text-muted">QR will appear after FBR Invoice No is generated.</div>'
        );
        return;
    }

    const showHtml = (src) => {
        frm.set_df_property(
            "custom_qr_code",
            "options",
            `<div style="padding:6px 0;"><img src="${src}" style="width:170px;height:170px;border:1px solid #e5e7eb;padding:6px;border-radius:8px;background:#fff;" /><div style="margin-top:6px;font-size:12px;color:#6b7280;">${esc(
                fbrNo
            )}</div></div>`
        );
    };

    if (frm.doc.name && !frm.is_new()) {
        frappe.call({
            method: "fbr_integration.handler.get_fbr_codes",
            args: { name: frm.doc.name },
            callback: function (r) {
                const msg = r.message || {};
                if (msg.ok && msg.qr_data_url) {
                    showHtml(msg.qr_data_url);
                    return;
                }
                const fallback = `https://api.qrserver.com/v1/create-qr-code/?size=170x170&data=${encodeURIComponent(
                    fbrNo
                )}`;
                showHtml(fallback);
            },
        });
    } else {
        const fallback = `https://api.qrserver.com/v1/create-qr-code/?size=170x170&data=${encodeURIComponent(
            fbrNo
        )}`;
        showHtml(fallback);
    }
}

function get_print_url(frm) {
    // FBR Sales Invoice print view
    return `/printview?doctype=Sales%20Invoice&name=${encodeURIComponent(
        frm.doc.name
    )}&trigger_print=1&format=${encodeURIComponent(
        FBR_PRINT_FORMAT
    )}&no_letterhead=0`;
}

function get_pdf_url(frm) {
    // FBR Sales Invoice PDF download
    return `/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Invoice&name=${encodeURIComponent(
        frm.doc.name
    )}&format=${encodeURIComponent(FBR_PRINT_FORMAT)}&no_letterhead=0`;
}

async function show_success_popup_with_qr_barcode(frm) {
    const r = await frappe.call({
        method: "fbr_integration.handler.get_fbr_codes",
        args: { name: frm.doc.name },
    });

    const data = r.message || {};
    const fbrNo = (frm.doc.custom_fbr_invoice_no || "").trim();
    const qrSrc =
        data.qr_data_url ||
        `https://api.qrserver.com/v1/create-qr-code/?size=170x170&data=${encodeURIComponent(
            fbrNo || frm.doc.name
        )}`;

    const print_url = get_print_url(frm);
    const pdf_url = get_pdf_url(frm);

    const stripHtml = (val) =>
        (val || "")
            .toString()
            .replace(/<[^>]*>/g, "")
            .replace(/\s+/g, " ")
            .trim();

    const asCurrencyText = (val) => {
        if (val == null) return "N/A";
        return stripHtml(frappe.format(val, { fieldtype: "Currency" }));
    };

    const taxAmount =
        frm.doc.total_taxes_and_charges != null
            ? asCurrencyText(frm.doc.total_taxes_and_charges)
            : "N/A";
    const totalAmount =
        frm.doc.total != null ? asCurrencyText(frm.doc.total) : "N/A";
    const grandTotal =
        frm.doc.grand_total != null
            ? asCurrencyText(frm.doc.grand_total)
            : "N/A";

    frappe.msgprint({
        title: __("Invoice Sent"),
        message: `
            <div style="font-size:13px; line-height:1.5; color:#1f2937; background:#edf7f2; padding:14px; border-radius:10px;">
                <div style="display:flex; align-items:center; gap:8px; color:#218653; font-weight:700; font-size:15px; margin-bottom:12px;">
                    <span style="display:inline-flex; width:20px; height:20px; border-radius:50%; background:#218653; color:#fff; align-items:center; justify-content:center; font-size:12px;">✓</span>
                    <span>Invoice Successfully Reported</span>
                </div>

                <div style="display:flex; justify-content:center; margin-bottom:12px;">
                    <div style="display:flex; gap:8px; padding:8px; border:2px solid #38a169; border-radius:10px; background:#fff; box-shadow:0 2px 8px rgba(0,0,0,.08);">
                        <div style="width:128px; height:128px; border:1px solid #e5e7eb; border-radius:6px; display:flex; align-items:center; justify-content:center; background:#f8fafc; overflow:hidden;">
                            <img src="${FBR_LOGO_URL}" alt="FBR Digital Invoicing" style="max-width:100%; max-height:100%; object-fit:contain;" onerror="this.style.display='none'" />
                        </div>
                        <div style="width:128px; height:128px; border:1px solid #e5e7eb; border-radius:6px; display:flex; align-items:center; justify-content:center; background:#fff; overflow:hidden;">
                            <img src="${qrSrc}" alt="FBR QR" style="width:120px; height:120px; object-fit:contain; display:block;" />
                        </div>
                    </div>
                </div>

                <div style="background:#2ea86d; color:#fff; border-radius:999px; padding:8px 14px; font-weight:700; text-align:center; letter-spacing:.2px; margin-bottom:8px;">
                    FBR INVOICE: ${esc(fbrNo || "N/A")}
                </div>

                <div style="background:#0f766e; color:#fff; border-radius:999px; padding:8px 14px; font-weight:700; text-align:center; letter-spacing:.2px; margin-bottom:10px;">
                    ERP INVOICE: ${esc(frm.doc.name || "N/A")}
                </div>

                <div style="background:#fff; border:1px solid #d1fae5; border-radius:8px; padding:8px 12px; margin-bottom:10px; font-size:12px;">
                    <table style="width:100%; border-collapse:collapse;">
                        <tr style="border-bottom:1px solid #e5e7eb;">
                            <td style="padding:4px 6px; color:#6b7280; width:48%;">📅 Date</td>
                            <td style="padding:4px 6px; font-weight:600; text-align:right;">${esc(
                                frm.doc.posting_date || ""
                            )}</td>
                        </tr>
                        <tr style="border-bottom:1px solid #e5e7eb;">
                            <td style="padding:4px 6px; color:#6b7280;">👤 Customer</td>
                            <td style="padding:4px 6px; font-weight:600; text-align:right;">${esc(
                                frm.doc.customer_name || frm.doc.customer || ""
                            )}</td>
                        </tr>
                        <tr style="border-bottom:1px solid #e5e7eb;">
                            <td style="padding:4px 6px; color:#6b7280;">💰 Total Amount</td>
                            <td style="padding:4px 6px; font-weight:600; text-align:right;">${esc(
                                totalAmount
                            )}</td>
                        </tr>
                        <tr style="border-bottom:1px solid #e5e7eb;">
                            <td style="padding:4px 6px; color:#6b7280;">🧾 Tax Amount</td>
                            <td style="padding:4px 6px; font-weight:600; text-align:right;">${esc(
                                taxAmount
                            )}</td>
                        </tr>
                        <tr>
                            <td style="padding:4px 6px; color:#166534; font-weight:700;">✅ Grand Total</td>
                            <td style="padding:4px 6px; font-weight:700; color:#166534; text-align:right;">${esc(
                                grandTotal
                            )}</td>
                        </tr>
                    </table>
                </div>

                <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:center; margin-bottom:10px;">
                    <a class="btn btn-sm" href="${print_url}" target="_blank" style="background:#166534; color:#fff; border:none; padding:7px 12px; border-radius:6px; text-decoration:none; font-weight:600;">
                        Print
                    </a>
                    <a class="btn btn-sm" href="${pdf_url}" target="_blank" style="background:#2563eb; color:#fff; border:none; padding:7px 12px; border-radius:6px; text-decoration:none; font-weight:600;">
                        Download PDF
                    </a>
                    <button class="btn btn-sm" id="btn_open_invoice" style="background:#475569; color:#fff; border:none; padding:7px 12px; border-radius:6px; font-weight:600;">
                        Open Invoice
                    </button>
                </div>

                ${
                    data.ok && data.barcode_data_url
                        ? `
                <div style="background:#fff; border:1px solid #d1fae5; border-radius:8px; padding:10px 10px 6px;">
                    <img src="${
                        data.barcode_data_url
                    }" style="width:100%; height:60px; display:block; object-fit:fill;" />
                    <div style="margin-top:4px; font-size:10px; letter-spacing:0.8px; color:#374151; text-align:center; word-break:break-all; font-weight:600;">
                        ${esc(data.value || fbrNo)}
                    </div>
                </div>
                `
                        : ""
                }
            </div>
        `,
        indicator: "green",
    });

    // attach open invoice action
    setTimeout(() => {
        const btn = document.getElementById("btn_open_invoice");
        if (btn) {
            btn.onclick = () =>
                frappe.set_route("Form", "Sales Invoice", frm.doc.name);
        }
    }, 200);
}

frappe.ui.form.on("Sales Invoice", {
    async setup(frm) {
        if (frm.is_new()) {
            await ensure_return_credit_note(frm);
            await sync_return_source_invoice_no(frm);
            await clear_fbr_response_fields(frm);
        }
    },

    async is_return(frm) {
        await ensure_return_credit_note(frm, { notify: true });
        await sync_return_source_invoice_no(frm);
        if (is_return_checked(frm.doc)) {
            await clear_fbr_response_fields(frm);
        }
    },

    async return_against(frm) {
        await sync_return_source_invoice_no(frm);
        if (is_return_checked(frm.doc)) {
            await clear_fbr_response_fields(frm);
        }
    },

    async custom_invoice_type(frm) {
        await ensure_return_credit_note(frm, { notify: true });
    },

    async validate(frm) {
        await ensure_return_credit_note(frm);

        if (
            is_return_checked(frm.doc) &&
            (frm.doc.custom_invoice_type || "").toString().trim() !==
                "Credit Note"
        ) {
            frappe.throw(
                __(
                    "When Is Return is checked, Invoice Type must be Credit Note."
                )
            );
        }
    },

    async custom_fbr_scenario(frm) {
        await apply_invoice_scenario_to_all_items(frm, { notify: true });
    },

    async custom_fbr_scenario_apply_mode(frm) {
        if (!(frm.doc.custom_fbr_scenario || "").toString().trim()) return;
        await apply_invoice_scenario_to_all_items(frm, { notify: true });
    },

    refresh(frm) {
        sync_qr_field_on_form(frm);
        render_qr_preview(frm);

        frm.add_custom_button(__("Scenario Index"), function () {
            show_scenario_browser(frm);
        });

        // View Scenario button — shown only when a Scenario ID is selected
        if ((frm.doc.custom_scenario_id || "").toString().trim()) {
            frm.add_custom_button(__("View Scenario"), function () {
                show_scenario_details(frm.doc.custom_scenario_id);
            });
        }

        frm.add_custom_button(__("FBR"), async function () {
            if ((frm.doc.custom_fbr_invoice_no || "").trim()) {
                await show_success_popup_with_qr_barcode(frm);
                return;
            }

            frappe.msgprint({
                title: __("FBR Status"),
                indicator: "orange",
                message: `<div style="font-size:14px;line-height:1.6;"><b>This invoice has not been submitted to FBR yet.</b></div>`,
            });
        });

        // Purple Send button
        const btn = frm.add_custom_button(__("Send to FBR"), async function () {
            // If already sent -> block
            if ((frm.doc.custom_fbr_invoice_no || "").trim()) {
                await show_success_popup_with_qr_barcode(frm);
                return;
            }

            frappe.call({
                method: "fbr_integration.handler.send_to_fbr_si",
                args: { name: frm.doc.name },
                freeze: true,
                callback: function (r) {
                    const resp = r.message || {};
                    if (resp.already_sent) {
                        frm.reload_doc();
                        return;
                    }

                    frm.reload_doc().then(() => {
                        setTimeout(async () => {
                            await show_success_popup_with_qr_barcode(frm);
                        }, 400);
                    });
                },
            });
        });

        try {
            btn.removeClass(
                "btn-default btn-primary btn-danger btn-success"
            ).addClass("btn-purple");
        } catch (e) {
            // ignore style application errors
        }
    },
});

frappe.ui.form.on("Sales Invoice Item", {
    qty(frm, cdt, cdn) {
        recalc_fbr_item_row(frm, cdt, cdn);
    },

    rate(frm, cdt, cdn) {
        recalc_fbr_item_row(frm, cdt, cdn);
    },

    item_tax_template(frm, cdt, cdn) {
        if (frm.__fbr_bulk_updating) return;
        recalc_fbr_item_row(frm, cdt, cdn);
    },

    custom_fbr_item_scenario(frm, cdt, cdn) {
        apply_fbr_item_tax_template(frm, cdt, cdn, { notify: true });
    },

    item_code(frm, cdt, cdn) {
        apply_fbr_item_tax_template(frm, cdt, cdn, { notify: false });
    },
});
