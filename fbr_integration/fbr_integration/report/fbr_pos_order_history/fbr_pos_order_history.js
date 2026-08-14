// Copyright (c) 2026, Taimoor and contributors
// For license information, please see license.txt

frappe.query_reports["FBR POS Order History"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "pos_profile",
			label: __("POS Profile"),
			fieldtype: "Link",
			options: "POS Profile",
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "fbr_status",
			label: __("FBR Status"),
			fieldtype: "Select",
			options: "All\nSent\nNot Sent",
			default: "All",
		},
	],
	formatter: function (value, row, column, data, default_formatter) {
		if (column.fieldname === "fbr_qr") {
			const fbrNo = data && (data.fbr_invoice_no || "").trim();
			if (!fbrNo) {
				return `<span style="color:#9a3412;font-size:11px;">${__("Not sent")}</span>`;
			}
			const src = `https://api.qrserver.com/v1/create-qr-code/?size=72x72&data=${encodeURIComponent(
				fbrNo
			)}`;
			return `<img src="${frappe.utils.escape_html(
				src
			)}" alt="FBR QR" style="width:48px;height:48px;object-fit:contain;background:#fff;border:1px solid #e5e7eb;border-radius:4px;padding:2px;">`;
		}
		if (column.fieldname === "fbr_invoice_no" && (!value || !String(value).trim())) {
			return `<span style="color:#9a3412;">${__("Not sent")}</span>`;
		}
		return default_formatter(value, row, column, data);
	},
};
