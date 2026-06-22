function esc(s) {
    return frappe.utils.escape_html((s || "").toString());
}

function json_to_html(obj, indent) {
    indent = indent || 0;
    const pad = "  ".repeat(indent);
    const pad1 = "  ".repeat(indent + 1);
    if (obj === null)
        return `<span style="color:#f87171;font-weight:600;">null</span>`;
    if (typeof obj === "boolean")
        return `<span style="color:#c084fc;font-weight:600;">${obj}</span>`;
    if (typeof obj === "number")
        return `<span style="color:#fb923c;font-weight:600;">${obj}</span>`;
    if (typeof obj === "string")
        return `<span style="color:#4ade80;">"${frappe.utils.escape_html(
            obj
        )}"</span>`;
    if (Array.isArray(obj)) {
        if (obj.length === 0) return `<span style="color:#94a3b8;">[]</span>`;
        const items = obj
            .map(
                (v, i) =>
                    `${pad1}${json_to_html(v, indent + 1)}${
                        i < obj.length - 1
                            ? '<span style="color:#94a3b8;">,</span>'
                            : ""
                    }`
            )
            .join("\n");
        return `<span style="color:#94a3b8;">[</span>\n${items}\n${pad}<span style="color:#94a3b8;">]</span>`;
    }
    if (typeof obj === "object") {
        const keys = Object.keys(obj);
        if (keys.length === 0) return `<span style="color:#94a3b8;">{}</span>`;
        const rows = keys
            .map(
                (k, i) =>
                    `${pad1}<span style="color:#7dd3fc;font-weight:600;">"${frappe.utils.escape_html(
                        k
                    )}"</span><span style="color:#94a3b8;">: </span>${json_to_html(
                        obj[k],
                        indent + 1
                    )}${
                        i < keys.length - 1
                            ? '<span style="color:#94a3b8;">,</span>'
                            : ""
                    }`
            )
            .join("\n");
        return `<span style="color:#94a3b8;">{</span>\n${rows}\n${pad}<span style="color:#94a3b8;">}</span>`;
    }
    return frappe.utils.escape_html(String(obj));
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
            const json_html = json_to_html(data, 0);
            const copy_id = "json-copy-" + sid;
            const raw_json = JSON.stringify(data, null, 2);
            const html = `
<div style="font-family:inherit;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;padding:10px 14px;
    background:linear-gradient(135deg,#0f172a,#1e3a5f);border-radius:10px;">
    <span style="background:#38bdf8;color:#0f172a;font-weight:700;padding:3px 10px;
      border-radius:999px;font-size:13px;">${esc(data.id || sid)}</span>
    <span style="font-size:15px;font-weight:700;color:#f1f5f9;">${esc(
        data.title || ""
    )}</span>
    <button id="${copy_id}" style="margin-left:auto;padding:4px 12px;background:#334155;color:#e2e8f0;
      border:1px solid #475569;border-radius:6px;cursor:pointer;font-size:12px;">Copy JSON</button>
  </div>
  <p style="color:#475569;margin-bottom:10px;font-size:13px;">${esc(
      data.description || ""
  )}</p>
  <div style="background:#0d1117;border:1px solid #30363d;border-radius:10px;
    padding:16px 18px;overflow-x:auto;max-height:55vh;overflow-y:auto;">
    <pre style="margin:0;font-family:'Fira Code','Cascadia Code','Consolas',monospace;
      font-size:12.5px;line-height:1.7;white-space:pre;">${json_html}</pre>
  </div>
</div>`;
            frappe.msgprint({
                title: __("{0} — {1}", [
                    esc(data.id || sid),
                    esc(data.title || ""),
                ]),
                indicator: "blue",
                message: html,
                wide: true,
            });
            // Attach copy handler after DOM render (onclick is stripped by Frappe sanitizer)
            setTimeout(function () {
                const btn = document.getElementById(copy_id);
                if (btn) {
                    btn.addEventListener("click", function () {
                        navigator.clipboard
                            .writeText(raw_json)
                            .then(function () {
                                btn.textContent = "Copied!";
                                setTimeout(function () {
                                    btn.textContent = "Copy JSON";
                                }, 1500);
                            });
                    });
                }
            }, 100);
        })
        .catch(function () {
            frappe.msgprint({
                title: __("Scenario Not Found"),
                indicator: "orange",
                message: __("Could not load details for scenario <b>{0}</b>.", [
                    esc(sid),
                ]),
            });
        });
}

function show_scenario_tree(scenario_id) {
    const sid = (scenario_id || "").toString().trim().toUpperCase();
    if (!sid) return;

    fetch_scenario_doc(sid)
        .then(function (data) {
            frappe.msgprint({
                title: __("Scenario Tree: {0}", [esc(sid)]),
                indicator: "blue",
                message: render_scenario_tree_html(data, sid),
                wide: true,
            });
        })
        .catch(function (err) {
            frappe.msgprint({
                title: __("Scenario Tree Not Available"),
                indicator: "orange",
                message: __("Could not load tree for scenario <b>{0}</b>.", [
                    esc(sid),
                ]),
            });
        });
}

function fetch_scenario_doc(scenario_id) {
    const sid = (scenario_id || "").toString().trim().toUpperCase();
    const url = `/assets/fbr_integration/scenario_docs/${sid}.json`;
    return fetch(url).then(function (r) {
        if (!r.ok) throw new Error("Not found: " + sid);
        return r.json();
    });
}

function build_scenario_table_rows(data, sid) {
    const sample = data.sample || {};
    const items = Array.isArray(sample.items) ? sample.items : [];
    const scenarioId = sample.scenarioId || data.id || sid;
    const invoiceType = sample.invoiceType || "";

    return items.length
        ? items
              .map(
                  (item) => `
<tr>
    <td style="padding:8px 10px;border:1px solid #dbeafe;white-space:nowrap;">${esc(
        scenarioId
    )}</td>
    <td style="padding:8px 10px;border:1px solid #dbeafe;white-space:nowrap;">${esc(
        data.title || "-"
    )}</td>
    <td style="padding:8px 10px;border:1px solid #dbeafe;white-space:nowrap;">${esc(
        invoiceType || "-"
    )}</td>
    <td style="padding:8px 10px;border:1px solid #dbeafe;white-space:nowrap;">${esc(
        item.hsCode || "-"
    )}</td>
    <td style="padding:8px 10px;border:1px solid #dbeafe;white-space:nowrap;">${esc(
        item.rate || "-"
    )}</td>
    <td style="padding:8px 10px;border:1px solid #dbeafe;white-space:nowrap;">${esc(
        item.uoM || "-"
    )}</td>
    <td style="padding:8px 10px;border:1px solid #dbeafe;white-space:nowrap;">${esc(
        item.saleType || "-"
    )}</td>
    <td style="padding:8px 10px;border:1px solid #dbeafe;white-space:nowrap;">${esc(
        item.sroScheduleNo || "-"
    )}</td>
    <td style="padding:8px 10px;border:1px solid #dbeafe;white-space:nowrap;">${esc(
        item.sroItemSerialNo || "-"
    )}</td>
</tr>`
              )
              .join("")
        : `<tr><td colspan="9" style="padding:12px;border:1px dashed #cbd5e1;color:#64748b;text-align:center;">No item data found in sample payload.</td></tr>`;
}

function render_scenario_tree_html(data, sid) {
    const rows = build_scenario_table_rows(data, sid);
    return `
<div style="font-family:inherit;line-height:1.5;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;padding:10px 14px;background:linear-gradient(135deg,#1f4e79,#2b6da8);border-radius:10px;">
        <span style="background:#fff;color:#1f4e79;font-weight:700;padding:3px 10px;border-radius:999px;font-size:13px;">${esc(
            data.id
        )}</span>
        <span style="font-size:14px;font-weight:700;color:#fff;">${esc(
            data.title || ""
        )}</span>
    </div>

    <div style="border:1px solid #c7d2fe;border-radius:10px;overflow:hidden;">
        <div style="padding:10px 14px;background:#eef2ff;font-size:12px;font-weight:700;color:#312e81;">Scenario Table</div>
        <div style="overflow:auto;">
            <table style="width:100%;border-collapse:collapse;min-width:1200px;font-size:12px;color:#0f172a;">
                <thead style="background:#e0e7ff;color:#312e81;">
                    <tr>
                        <th style="padding:8px 10px;border:1px solid #c7d2fe;">Scenario ID</th>
                        <th style="padding:8px 10px;border:1px solid #c7d2fe;">Title</th>
                        <th style="padding:8px 10px;border:1px solid #c7d2fe;">Invoice Type</th>
                        <th style="padding:8px 10px;border:1px solid #c7d2fe;">HS Code</th>
                        <th style="padding:8px 10px;border:1px solid #c7d2fe;">Rate</th>
                        <th style="padding:8px 10px;border:1px solid #c7d2fe;">UoM</th>
                        <th style="padding:8px 10px;border:1px solid #c7d2fe;">Sale Type</th>
                        <th style="padding:8px 10px;border:1px solid #c7d2fe;">SRO Schedule No</th>
                        <th style="padding:8px 10px;border:1px solid #c7d2fe;">SRO Item Serial No</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        </div>
    </div>
</div>`;
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

            dialog.$wrapper.find(".modal-dialog").css({
                width: "96vw",
                "max-width": "96vw",
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

                const container = dialog.get_field("results").$wrapper;
                container.html(
                    `<div style="padding:14px;border:1px solid #bfdbfe;border-radius:10px;background:#eff6ff;color:#1d4ed8;font-size:12px;">
                        ${__("Loading scenario table...")}
                    </div>`
                );

                Promise.all(
                    filtered.map(function (row) {
                        return fetch_scenario_doc(row.id)
                            .then(function (data) {
                                return build_scenario_table_rows(data, row.id);
                            })
                            .catch(function () {
                                return "";
                            });
                    })
                ).then(function (tableRows) {
                    const htmlRows = tableRows.join("");
                    container.html(
                        filtered.length
                            ? `<div style="max-height:72vh;overflow:auto;padding-right:4px;">
<div style="padding:10px 14px;background:#eef2ff;font-size:12px;font-weight:700;color:#312e81;border:1px solid #c7d2fe;border-bottom:none;border-radius:10px 10px 0 0;">${__(
    "Scenario Table"
)}</div>
<table style="width:max-content;border-collapse:collapse;min-width:1550px;font-size:12px;color:#0f172a;">
  <thead style="position:sticky;top:0;background:#e0e7ff;z-index:1;color:#312e81;">
    <tr>
      <th style="padding:8px 10px;border:1px solid #c7d2fe;min-width:120px;">Scenario ID</th>
      <th style="padding:8px 10px;border:1px solid #c7d2fe;min-width:320px;">Title</th>
      <th style="padding:8px 10px;border:1px solid #c7d2fe;min-width:130px;">Invoice Type</th>
      <th style="padding:8px 10px;border:1px solid #c7d2fe;min-width:140px;">HS Code</th>
      <th style="padding:8px 10px;border:1px solid #c7d2fe;min-width:90px;">Rate</th>
      <th style="padding:8px 10px;border:1px solid #c7d2fe;min-width:210px;">UoM</th>
      <th style="padding:8px 10px;border:1px solid #c7d2fe;min-width:220px;">Sale Type</th>
      <th style="padding:8px 10px;border:1px solid #c7d2fe;min-width:220px;">SRO Schedule No</th>
      <th style="padding:8px 10px;border:1px solid #c7d2fe;min-width:180px;">SRO Item Serial No</th>
    </tr>
  </thead>
  <tbody>${htmlRows || `<tr><td colspan="9" style="padding:12px;border:1px dashed #cbd5e1;color:#64748b;text-align:center;">${__(
      "No scenario rows available."
  )}</td></tr>`}</tbody>
</table>
</div>`
                            : `<div style="padding:12px;color:#777;">${__(
                                  "No scenarios matched your search."
                              )}</div>`
                    );
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
const LEGACY_FBR_SCENARIO_OPTIONS = [
    "Manual Item-wise",
    "All Taxes",
    "Pakistan Tax",
    "Zero Rated",
    "Exempt",
    "Cement Per Qty",
];
const FULL_FBR_SCENARIO_OPTIONS = [
    "Manual Item-wise",
    "All Taxes",
    "Pakistan Tax",
    "Zero Rated",
    "Exempt",
    "Cement Per Qty",
    "SN001 - Goods at Standard Rate (Registered Buyer)",
    "SN002 - Goods at Standard Rate (Unregistered Buyer)",
    "SN003 - Steel Melting and Re-rolling",
    "SN004 - Ship Breaking",
    "SN005 - Goods at Reduced Rate (Eighth Schedule)",
    "SN006 - Exempt Goods (Sixth Schedule)",
    "SN007 - Zero-Rated Goods",
    "SN008 - Third Schedule Goods (Retail Price Based)",
    "SN009 - Cotton Ginners",
    "SN010 - Telecommunication Services",
    "SN011 - Toll Manufacturing",
    "SN012 - Petroleum Products",
    "SN013 - Electricity Supply to Retailers",
    "SN014 - Gas to CNG Stations",
    "SN015 - Mobile Phones",
    "SN016 - Processing/Conversion of Goods",
    "SN017 - Goods (FED in ST Mode)",
    "SN018 - Services (FED in ST Mode)",
    "SN019 - ICT Services",
    "SN020 - Electric Vehicles",
    "SN021 - Cement/Concrete Block",
    "SN022 - Potassium Chlorate",
    "SN023 - CNG Sales",
    "SN024 - Goods as per SRO.297(I)/2023",
    "SN025 - Non-Adjustable Supplies (Pharmaceuticals)",
    "SN026 - Retailer - Standard Rate Goods",
    "SN027 - Retailer - Third Schedule Goods",
    "SN028 - Retailer - Reduced Rate Goods",
];
const FBR_SCENARIO_LEGACY_MAP = {
    SN006: "Exempt",
    SN007: "Zero Rated",
};

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
    const invoiceScenario = get_effective_invoice_fbr_scenario(frm);
    return (rowScenario || invoiceScenario).toString().trim();
}

function extract_fbr_scenario_id(value) {
    const text = (value || "").toString().trim().toUpperCase();
    const match = text.match(/^(SN\d{3})\b/);
    return match ? match[1] : "";
}

function map_to_legacy_fbr_scenario(value) {
    const text = (value || "").toString().trim();
    if (!text) return "";
    if (LEGACY_FBR_SCENARIO_OPTIONS.includes(text)) return text;

    const scenarioId = extract_fbr_scenario_id(text);
    return FBR_SCENARIO_LEGACY_MAP[scenarioId] || "Manual Item-wise";
}

function get_effective_invoice_fbr_scenario(frm) {
    const helperScenario = (frm.doc.custom_fbr_scenario || "").toString().trim();
    if (helperScenario && helperScenario !== "Manual Item-wise") {
        return helperScenario;
    }

    return (frm.doc.custom_scenario_id || "").toString().trim() || helperScenario;
}

function dedupe_fbr_options(options) {
    const seen = new Set();
    const rows = [];

    for (const option of options) {
        const value = (option || "").toString().trim();
        if (!value) continue;
        const key = normalize_fbr_text(value);
        if (!key || seen.has(key)) continue;
        seen.add(key);
        rows.push(value);
    }

    return rows;
}

function build_dynamic_fbr_scenario_options(rows) {
    const scenarioOptions = (rows || []).map((row) => {
        const sid = (row.id || "").toString().trim().toUpperCase();
        const title = (row.title || "").toString().trim();
        if (!sid) return "";
        return title ? `${sid} - ${title}` : sid;
    });

    return dedupe_fbr_options([
        ...FULL_FBR_SCENARIO_OPTIONS,
        ...scenarioOptions,
    ]);
}

function apply_fbr_scenario_options_to_form(frm, options) {
    const optionString = dedupe_fbr_options(options).join("\n");
    if (!optionString) return;

    frm.set_df_property("custom_fbr_scenario", "options", optionString);

    if (frm.fields_dict.items && frm.fields_dict.items.grid) {
        frm.fields_dict.items.grid.update_docfield_property(
            "custom_fbr_item_scenario",
            "options",
            optionString
        );
    }
}

function sync_fbr_scenario_select_options(frm) {
    apply_fbr_scenario_options_to_form(frm, FULL_FBR_SCENARIO_OPTIONS);
    return load_scenario_index()
        .then((rows) => {
            apply_fbr_scenario_options_to_form(
                frm,
                build_dynamic_fbr_scenario_options(rows)
            );
        })
        .catch(() => {
            // Keep built-in options when scenario catalog is unavailable.
        });
}

async function set_invoice_scenario_detail_by_id(frm, scenarioId) {
    const sid = (scenarioId || "").toString().trim().toUpperCase();
    if (!sid) return;

    const response = await frappe.db.get_value(
        "Scenario ID",
        { scenario_id: sid },
        "name"
    );
    const name = (((response || {}).message || {}).name || "").toString().trim();

    if (name) {
        await frm.set_value("custom_scenario_detail", name);
    } else {
        await frm.set_value("custom_scenario_id", sid);
    }
}

async function sync_legacy_helper_scenario(frm, options = {}) {
    const explicitScenario = (frm.doc.custom_fbr_scenario || "").toString().trim();
    const scenarioId = (frm.doc.custom_scenario_id || "").toString().trim();
    let nextHelperScenario = explicitScenario;
    if (!nextHelperScenario && scenarioId && Array.isArray(fbrScenarioIndexCache)) {
        const row = fbrScenarioIndexCache.find((entry) => {
            return ((entry.id || "").toString().trim().toUpperCase() === scenarioId.toUpperCase());
        });
        if (row) {
            nextHelperScenario = `${row.id} - ${row.title}`;
        }
    }
    if (!nextHelperScenario) {
        nextHelperScenario = map_to_legacy_fbr_scenario(scenarioId);
    }

    if (
        nextHelperScenario &&
        (frm.doc.custom_fbr_scenario || "").toString().trim() !== nextHelperScenario
    ) {
        await frm.set_value("custom_fbr_scenario", nextHelperScenario);
    }

    if (options.applyItems === true) {
        await apply_invoice_scenario_to_all_items(frm, {
            notify: options.notify === true,
        });
    }
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
        "No Item Tax Template mapping was found for {0} using scenario {1}. Set the Item Tax Template manually for this row.",
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

    const helperScenario = map_to_legacy_fbr_scenario(frm.doc.custom_fbr_scenario);
    const scenario = get_effective_invoice_fbr_scenario(frm);
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
            const scenarioChanged = currentItemScenario !== helperScenario;

            if (scenarioChanged) {
                await frappe.model.set_value(
                    cdt,
                    cdn,
                    "custom_fbr_item_scenario",
                    helperScenario
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
                "No Item Tax Template mapping was found for scenario {0}. Existing manual Item Tax Template values were kept.",
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
        const scenarioId = extract_fbr_scenario_id(frm.doc.custom_fbr_scenario);
        if (scenarioId) {
            await set_invoice_scenario_detail_by_id(frm, scenarioId);
        }
        await apply_invoice_scenario_to_all_items(frm, { notify: true });
    },

    async custom_scenario_detail(frm) {
        const scenarioName = (frm.doc.custom_scenario_detail || "").toString().trim();
        const scenarioId = extract_fbr_scenario_id(scenarioName);
        if (
            scenarioId &&
            (frm.doc.custom_scenario_id || "").toString().trim() !== scenarioId
        ) {
            await frm.set_value("custom_scenario_id", scenarioId);
        }
        await sync_legacy_helper_scenario(frm, { applyItems: true, notify: true });
    },

    async custom_scenario_id(frm) {
        await sync_legacy_helper_scenario(frm, { applyItems: true, notify: true });
    },

    async custom_fbr_scenario_apply_mode(frm) {
        if (!get_effective_invoice_fbr_scenario(frm)) return;
        await apply_invoice_scenario_to_all_items(frm, { notify: true });
    },

    refresh(frm) {
        sync_fbr_scenario_select_options(frm);
        sync_qr_field_on_form(frm);
        render_qr_preview(frm);

        frm.add_custom_button(__("Scenario Index"), function () {
            show_scenario_browser(frm);
        });

        // Determine if invoice is already submitted to FBR
        const is_sent_to_fbr = (frm.doc.custom_fbr_invoice_no || "").trim();

        // Fetch integration type to decide when to show the Send button
        frappe.call({
            method: "frappe.client.get_value",
            args: {
                doctype: "FBR Invoice Settings",
                fieldname: "integration_type",
            },
            callback: function (r) {
                const integration_type = (
                    (r.message || {}).integration_type || ""
                ).trim();
                const is_sandbox = integration_type === "Sandbox";
                const is_submitted = frm.doc.docstatus === 1;

                // Sandbox: show on Draft + Submitted; Production: Submitted only
                if (!is_sandbox && !is_submitted) return;

                // Single "Send to FBR" button with dynamic styling
                const button_text = is_sent_to_fbr
                    ? __("✓ Sent to FBR")
                    : is_sandbox && !is_submitted
                    ? __("Send to FBR (Sandbox Test)")
                    : __("Send to FBR");

                const btn = frm.add_custom_button(
                    button_text,
                    async function () {
                        // If already sent -> show success popup with QR/barcode
                        if (is_sent_to_fbr) {
                            await show_success_popup_with_qr_barcode(frm);
                            return;
                        }

                        // If not sent -> send to FBR
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
                                        await show_success_popup_with_qr_barcode(
                                            frm
                                        );
                                    }, 400);
                                });
                            },
                        });
                    }
                );

                try {
                    if (is_sent_to_fbr) {
                        // Green styling for submitted invoices
                        btn.removeClass(
                            "btn-default btn-primary btn-danger btn-purple"
                        ).addClass("btn-success");
                    } else {
                        // Purple styling for pending invoices
                        btn.removeClass(
                            "btn-default btn-primary btn-danger btn-success"
                        ).addClass("btn-purple");
                    }
                } catch (e) {
                    // ignore style application errors
                }
            },
        });
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
