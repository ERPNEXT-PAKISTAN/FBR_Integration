/**
 * POS → FBR UI (ERPNext desk Point of Sale)
 * Works for Sales Invoice and POS Invoice (POS Settings → Invoice Type).
 * XPOS uses the same server hooks; this file only patches the desk POS page.
 */
frappe.provide("fbr_integration.pos");

fbr_integration.pos.INVOICE_DOCTYPES = ["Sales Invoice", "POS Invoice"];
fbr_integration.pos.DEFAULT_INVOICE_TYPE = "Sale Invoice";
fbr_integration.pos.DEFAULT_SCENARIO_DETAIL =
	"SN001 - Goods at Standard Rate (Registered Buyer)";
fbr_integration.pos._template_cache = {};

fbr_integration.pos.is_invoice_doc = function (doc) {
	return !!(doc && fbr_integration.pos.INVOICE_DOCTYPES.includes(doc.doctype));
};

fbr_integration.pos.esc = function (s) {
	return frappe.utils.escape_html((s || "").toString());
};

fbr_integration.pos.apply_invoice_defaults = function (frm) {
	if (!frm || !frm.doc || cint(frm.doc.docstatus) !== 0) return;
	if (!fbr_integration.pos.is_invoice_doc(frm.doc)) return;

	if (!cint(frm.doc.is_return) && !(cstr(frm.doc.custom_invoice_type) || "").trim()) {
		frm.doc.custom_invoice_type = fbr_integration.pos.DEFAULT_INVOICE_TYPE;
	}
	if (!(cstr(frm.doc.custom_scenario_detail) || "").trim()) {
		frm.doc.custom_scenario_detail = fbr_integration.pos.DEFAULT_SCENARIO_DETAIL;
		if (!(cstr(frm.doc.custom_scenario_id) || "").trim()) {
			frm.doc.custom_scenario_id = "SN001";
		}
	}
};

fbr_integration.pos.apply_item_defaults = function (frm) {
	if (!frm || !frm.doc || cint(frm.doc.docstatus) !== 0) return Promise.resolve();
	if (!fbr_integration.pos.is_invoice_doc(frm.doc)) return Promise.resolve();

	fbr_integration.pos.apply_invoice_defaults(frm);
	const rows = (frm.doc.items || []).filter((row) => row && row.item_code);
	if (!rows.length) return Promise.resolve();

	const scenario =
		(cstr(frm.doc.custom_scenario_detail) || "").trim() ||
		fbr_integration.pos.DEFAULT_SCENARIO_DETAIL;
	const cacheKey = `${cstr(frm.doc.company)}::${scenario}`;
	const apply_template = (templateName) => {
		if (!templateName) return;
		rows.forEach((row) => {
			if (!(cstr(row.custom_scenario_detail) || "").trim()) {
				row.custom_scenario_detail = scenario;
			}
			if (!(cstr(row.item_tax_template) || "").trim()) {
				row.item_tax_template = templateName;
			}
		});
	};

	if (fbr_integration.pos._template_cache[cacheKey]) {
		apply_template(fbr_integration.pos._template_cache[cacheKey]);
		return Promise.resolve();
	}

	return frappe
		.call({
			method: "fbr_integration.api.resolve_item_tax_template_name",
			args: { scenario: scenario, company: frm.doc.company },
		})
		.then((r) => {
			const templateName = (r && r.message) || "";
			if (templateName) {
				fbr_integration.pos._template_cache[cacheKey] = templateName;
			}
			apply_template(templateName);
		})
		.catch(() => {});
};

fbr_integration.pos.show_status_dialog = function (invoice_name, opts) {
	opts = opts || {};
	return frappe
		.call({
			method: "fbr_integration.handler.get_pos_fbr_status",
			args: { name: invoice_name },
			freeze: !!opts.freeze,
			freeze_message: __("Loading FBR status..."),
		})
		.then((r) => {
			const d = r.message || {};
			const fbrNo = (d.fbr_invoice_no || "").trim();
			const qrSrc =
				d.qr_data_url ||
				(fbrNo
					? `https://api.qrserver.com/v1/create-qr-code/?size=170x170&data=${encodeURIComponent(
							fbrNo
					  )}`
					: "");

			const ok = !!d.ok;
			const title = ok ? __("Sent to FBR") : __("FBR not sent yet");
			const statusLine = ok
				? __("Invoice successfully reported to FBR.")
				: d.fbr_error
				? d.fbr_error
				: __(
						"Invoice is saved. Use Send to FBR if auto-send is off or failed."
				  );

			const dialog = new frappe.ui.Dialog({
				title: title,
				size: "small",
				fields: [{ fieldtype: "HTML", fieldname: "body" }],
				primary_action_label: ok ? __("Close") : __("Send to FBR"),
				primary_action: () => {
					if (ok) {
						dialog.hide();
						return;
					}
					frappe.call({
						method: "fbr_integration.handler.send_to_fbr_si",
						args: { name: invoice_name },
						freeze: true,
						freeze_message: __("Sending to FBR..."),
						callback: () => {
							dialog.hide();
							fbr_integration.pos.show_status_dialog(invoice_name, {
								freeze: true,
							});
							if (typeof opts.on_refresh === "function") {
								opts.on_refresh();
							}
						},
					});
				},
			});

			const html = `
				<div style="font-size:13px;line-height:1.45;color:#1f2937;">
					<div style="padding:10px 12px;border-radius:10px;margin-bottom:12px;background:${
						ok ? "#edf7f2" : "#fff7ed"
					};border:1px solid ${ok ? "#86efac" : "#fdba74"};">
						<b>${fbr_integration.pos.esc(statusLine)}</b>
					</div>
					${
						qrSrc
							? `<div style="display:flex;justify-content:center;margin-bottom:12px;">
						<img src="${qrSrc}" alt="FBR QR" style="width:140px;height:140px;object-fit:contain;border:1px solid #e5e7eb;border-radius:8px;background:#fff;padding:6px;" />
					</div>`
							: ""
					}
					<table style="width:100%;border-collapse:collapse;">
						<tr><td style="padding:6px 0;color:#6b7280;">ERP Invoice</td><td style="padding:6px 0;text-align:right;font-weight:600;">${fbr_integration.pos.esc(
							d.sales_invoice || invoice_name
						)}</td></tr>
						<tr><td style="padding:6px 0;color:#6b7280;">FBR Invoice No</td><td style="padding:6px 0;text-align:right;font-weight:700;color:#0f766e;">${fbr_integration.pos.esc(
							fbrNo || "—"
						)}</td></tr>
						<tr><td style="padding:6px 0;color:#6b7280;">FBR Status</td><td style="padding:6px 0;text-align:right;">${fbr_integration.pos.esc(
							d.fbr_status || "—"
						)}${
				d.fbr_status_code
					? ` (${fbr_integration.pos.esc(d.fbr_status_code)})`
					: ""
			}</td></tr>
						<tr><td style="padding:6px 0;color:#6b7280;">Customer</td><td style="padding:6px 0;text-align:right;">${fbr_integration.pos.esc(
							d.customer_name || d.customer || ""
						)}</td></tr>
					</table>
				</div>`;

			dialog.fields_dict.body.$wrapper.html(html);
			dialog.show();
			return d;
		});
};

fbr_integration.pos.inject_summary_card = function (summary, doc) {
	if (!summary || !summary.$summary_container || !fbr_integration.pos.is_invoice_doc(doc)) {
		return;
	}

	summary.$summary_container.find(".fbr-pos-summary-card").remove();

	const mount = $(`
		<div class="fbr-pos-summary-card" style="margin:10px 0 4px;padding:10px 12px;border-radius:10px;border:1px solid #c7d2fe;background:#eef2ff;">
			<div style="font-size:12px;font-weight:700;color:#312e81;margin-bottom:6px;">FBR Digital Invoice</div>
			<div class="fbr-pos-summary-body" style="font-size:12px;color:#3730a3;">${__(
				"Loading…"
			)}</div>
			<div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;">
				<button type="button" class="btn btn-xs btn-primary fbr-pos-view-btn">${__(
					"FBR Details"
				)}</button>
				<button type="button" class="btn btn-xs btn-default fbr-pos-send-btn" style="display:none;">${__(
					"Send to FBR"
				)}</button>
			</div>
		</div>
	`);

	const $btns = summary.$summary_container.find(".summary-btns");
	if ($btns.length) {
		mount.insertBefore($btns);
	} else {
		summary.$summary_container.append(mount);
	}

	const refresh_card = () => {
		frappe
			.call({
				method: "fbr_integration.handler.get_pos_fbr_status",
				args: { name: doc.name },
			})
			.then((r) => {
				const d = r.message || {};
				const fbrNo = (d.fbr_invoice_no || "").trim();
				const body = fbrNo
					? `${__("FBR Invoice")}: <b>${fbr_integration.pos.esc(
							fbrNo
					  )}</b><br>${__("Status")}: ${fbr_integration.pos.esc(
							d.fbr_status || "Valid"
					  )}`
					: `<span style="color:#9a3412;">${__(
							"Not sent to FBR yet"
					  )}</span>`;
				mount.find(".fbr-pos-summary-body").html(body);
				mount.find(".fbr-pos-send-btn").toggle(!fbrNo && cint(doc.docstatus) === 1);
			});
	};

	mount.find(".fbr-pos-view-btn").on("click", () => {
		fbr_integration.pos.show_status_dialog(doc.name, { on_refresh: refresh_card });
	});
	mount.find(".fbr-pos-send-btn").on("click", () => {
		frappe.call({
			method: "fbr_integration.handler.send_to_fbr_si",
			args: { name: doc.name },
			freeze: true,
			freeze_message: __("Sending to FBR..."),
			callback: () => {
				refresh_card();
				fbr_integration.pos.show_status_dialog(doc.name);
			},
		});
	});

	refresh_card();
};

fbr_integration.pos.patch = function () {
	if (!window.erpnext || !erpnext.PointOfSale) return false;

	const Ctrl = erpnext.PointOfSale.Controller;
	const Summary = erpnext.PointOfSale.PastOrderSummary;
	if (!Ctrl || !Summary) return false;
	if (Ctrl.__fbr_pos_patched) return true;
	Ctrl.__fbr_pos_patched = true;

	const _make_new = Ctrl.prototype.make_new_invoice;
	Ctrl.prototype.make_new_invoice = function () {
		return Promise.resolve(_make_new.call(this)).then(() => {
			fbr_integration.pos.apply_invoice_defaults(this.frm);
		});
	};

	const _on_cart = Ctrl.prototype.on_cart_update;
	Ctrl.prototype.on_cart_update = function (args) {
		return Promise.resolve(_on_cart.call(this, args)).then((res) => {
			return fbr_integration.pos.apply_item_defaults(this.frm).then(() => res);
		});
	};

	const _init_payments = Ctrl.prototype.init_payments;
	Ctrl.prototype.init_payments = function () {
		_init_payments.call(this);
		const payment = this.payment;
		if (!payment || !payment.events || payment.events.__fbr_submit_wrapped) return;

		payment.events.__fbr_submit_wrapped = true;
		payment.events.submit_invoice = () => {
			fbr_integration.pos.apply_invoice_defaults(this.frm);
			this.frm.savesubmit().then((r) => {
				this.toggle_components(false);
				this.toggle_submitted_invoice_summary(true);
				const name = (r && r.doc && r.doc.name) || (this.frm && this.frm.docname);
				frappe.show_alert({
					indicator: "green",
					message: __("POS invoice {0} created successfully", [name]),
				});
				setTimeout(() => {
					if (name) {
						fbr_integration.pos.show_status_dialog(name, { freeze: false });
					}
				}, 700);
			});
		};
	};

	const _load_summary = Summary.prototype.load_summary_of;
	Summary.prototype.load_summary_of = function (doc, after_submission = false) {
		_load_summary.call(this, doc, after_submission);
		fbr_integration.pos.inject_summary_card(this, doc);
		if (after_submission && fbr_integration.pos.is_invoice_doc(doc)) {
			setTimeout(() => {
				fbr_integration.pos.show_status_dialog(doc.name);
			}, 500);
		}
	};

	return true;
};

// Desk pages do not provide frappe.ready (website-only). Page JS is evaluated
// on load; retry until the POS bundle defines erpnext.PointOfSale.
(function () {
	const try_patch = () => {
		if (fbr_integration.pos.patch()) return;
		setTimeout(try_patch, 300);
	};
	try_patch();
})();
