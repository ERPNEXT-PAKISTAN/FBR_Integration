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

    const print_url = get_print_url(frm);
    const pdf_url = get_pdf_url(frm);

    frappe.msgprint({
        title: __("Invoice Sent"),
        message: `
      <div style="font-size:13px; line-height:1.7; color:#333;">
        <div style="display:flex; align-items:center; gap:12px; margin-bottom:16px; padding-bottom:12px; border-bottom:2px solid #0f5132;">
          <img
            src="${FBR_LOGO_URL}"
            alt="FBR Digital Invoicing"
            style="height:42px; width:auto; display:block; object-fit:contain;"
            onerror="this.style.display='none'"
          />
          <div style="font-weight:700; color:#0f5132; font-size:15px;">FBR Digital Invoicing</div>
        </div>

        <div style="background:#f8f9fa; padding:12px; border-radius:6px; margin-bottom:14px;">
          <p style="margin:0 0 6px 0; font-weight:600; color:#0f5132; font-size:14px;">✓ Successfully Submitted to FBR</p>
          <p style="margin:0; font-size:13px; color:#555;">
          Your Sales Invoice <b>${esc(
              frm.doc.name
          )}</b> has been successfully transmitted to the IRIS Portal - FBR.
          </p>
        </div>

        <div style="background:#e8f5e9; padding:10px; border-radius:6px; border-left:4px solid #0f5132; margin-bottom:14px;">
          <p style="margin:0; font-size:12px; color:#1b5e20;"><strong>FBR Invoice No:</strong> ${esc(
              fbrNo
          )}</p>
        </div>

        <div style="background:#fff3cd; padding:10px; border-radius:6px; margin-bottom:14px; border-left:4px solid #ff9800;">
          <p style="margin:0; font-size:12px; color:#654321;">Thank you for staying compliant and digital with Tech Craft Pvt Ltd ERP-Pakistan!</p>
        </div>

        <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px;">
          <a class="btn btn-sm" href="${print_url}" target="_blank" style="background:#0f5132; color:#fff; border:none; padding:8px 14px; border-radius:4px; text-decoration:none; font-weight:500; cursor:pointer;">
            🖨️ Print
          </a>
          <a class="btn btn-sm" href="${pdf_url}" target="_blank" style="background:#2196F3; color:#fff; border:none; padding:8px 14px; border-radius:4px; text-decoration:none; font-weight:500; cursor:pointer;">
            📥 Download PDF
          </a>
          <button class="btn btn-sm" id="btn_open_invoice" style="background:#607D8B; color:#fff; border:none; padding:8px 14px; border-radius:4px; font-weight:500; cursor:pointer;">
            📋 View Invoice
          </button>
        </div>

        <hr style="border:none; border-top:1px solid #ddd; margin:14px 0;"/>

        <div style="display:flex; gap:20px; margin-top:14px; font-size:12px; color:#666;">
          <div><span style="font-weight:600; color:#333;">Sales Invoice:</span> ${esc(
              frm.doc.name
          )}</div>
          <div><span style="font-weight:600; color:#333;">FBR Invoice No:</span> ${esc(
              fbrNo
          )}</div>
        </div>

        ${
            data.ok
                ? `
        <div style="display:flex; gap:20px; align-items:flex-start; margin-top:16px; padding-top:16px; border-top:1px solid #ddd;">
          <div style="min-width:160px;">
            <div style="font-weight:700; margin-bottom:8px; color:#333; font-size:13px;">QR Code</div>
            <div style="border:2px solid #0f5132; padding:8px; border-radius:6px; background:#f9f9f9; display:inline-block;">
            <img src="${
                data.qr_data_url
            }" style="width:140px;height:140px; display:block;" />
            </div>
          </div>

          <div style="flex:1;">
            <div style="font-weight:700; margin-bottom:8px; color:#333; font-size:13px;">Barcode</div>
            <div style="border:2px solid #0f5132; padding:10px; border-radius:6px; background:#f9f9f9;">
              <img src="${
                  data.barcode_data_url
              }" style="max-width:100%; width:100%; height:60px; object-fit:contain; object-position:center; display:block; background:#fff; margin-bottom:6px;" />
              <div style="margin-top:6px; font-size:10px; letter-spacing:1px; color:#333; text-align:center; word-break:break-all; font-weight:600;">
                ${esc(data.value)}
              </div>
            </div>
          </div>
        </div>
        `
                : `<div style="margin-top:14px; padding:12px; background:#ffebee; border-radius:6px; color:#c62828; font-size:12px; border-left:4px solid #c62828;">⚠️ QR/Barcode could not be generated.</div>`
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
