/*!
 * Dual v15/v16 desk route helper for FBR Integration.
 * Use data-fbr-route="financial-dashboard" on anchors; href is rewritten at runtime.
 */
frappe.provide("frappe.fbr");

frappe.fbr.desk_prefix = function () {
	if (frappe.boot && frappe.boot.fbr_desk_prefix) {
		return frappe.boot.fbr_desk_prefix;
	}
	return window.location.pathname.indexOf("/desk") === 0 ? "/desk" : "/app";
};

frappe.fbr.desk_path = function (route) {
	route = String(route || "")
		.replace(/^\/+/, "")
		.replace(/^(app|desk)\//, "");
	return `${frappe.fbr.desk_prefix()}/${route}`;
};

frappe.fbr.rewrite_links = function (root) {
	const $root = root ? $(root) : $(document);
	$root.find("[data-fbr-route]").each(function () {
		const route = this.getAttribute("data-fbr-route");
		if (route) {
			this.setAttribute("href", frappe.fbr.desk_path(route));
		}
	});
};

$(document).on("app_ready", () => frappe.fbr.rewrite_links());
$(document).on("page-change", () => frappe.fbr.rewrite_links());
