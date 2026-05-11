function esc(s) {
    return frappe.utils.escape_html((s || "").toString());
}

const FBR_PRINT_FORMAT = "FBR Sales Invoice";
const FBR_LOGO_URL = "/assets/fbr_integration/images/fbr/DI_invoicing.png";

function sync_qr_field_on_form(frm) {
    const fbrNo = (frm.doc.custom_fbr_invoice_no || "").trim();
    if (!fbrNo) return;

    const updates = {};
    if (
        "custom_fbr_qr_code" in frm.doc &&
        (frm.doc.custom_fbr_qr_code || "") !== fbrNo
    ) {
        updates.custom_fbr_qr_code = fbrNo;
    }
    if (
        "custom_qr_code" in frm.doc &&
        (frm.doc.custom_qr_code || "") !== fbrNo
    ) {
        updates.custom_qr_code = fbrNo;
    }
    if (Object.keys(updates).length) {
        frm.set_value(updates);
    }
}

function render_qr_preview(frm) {
    if (!frm.fields_dict.custom_qr_code) return;
    const fbrNo = (frm.doc.custom_fbr_invoice_no || "").trim();
    if (!fbrNo) {
        frm.set_df_property(
            "custom_qr_code",
            "options",
            "<div class='text-muted'>QR will appear after FBR Invoice No is generated.</div>"
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
    refresh(frm) {
        sync_qr_field_on_form(frm);
        render_qr_preview(frm);

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
