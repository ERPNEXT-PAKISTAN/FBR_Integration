frappe.ui.form.on("FBR Invoice Settings", {
	refresh(frm) {
		if (!frappe.user.has_role("System Manager")) return;
		frm.add_custom_button(__("Import from POS Profiles"), () => {
			frappe.call({
				method: "fbr_integration.fbr_api.import_pos_credentials_from_profiles",
				freeze: true,
				freeze_message: __("Importing POS credentials..."),
				callback(r) {
					const msg = r.message || {};
					frappe.show_alert({
						indicator: "green",
						message: __("Added {0} POS credential row(s).", [msg.added || 0]),
					});
					frm.reload_doc();
				},
			});
		});
	},
});
