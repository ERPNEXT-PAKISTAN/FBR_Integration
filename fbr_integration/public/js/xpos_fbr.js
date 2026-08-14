/**
 * FBR overlay for stock XPOS (any vendor build).
 * Injected into /xpos by fbr_integration.xpos_bridge.inject_xpos_bridge.
 * Skips UI when a native XPOS FBR screen is already present (__XPOS_FBR_NATIVE__).
 */
(function () {
	if (window.__FBR_XPOS_BRIDGE__) return;
	window.__FBR_XPOS_BRIDGE__ = true;

	var STATUS_MAP = {};

	function nativeVue() {
		return !!window.__XPOS_FBR_NATIVE__;
	}

	function isOverlayNode(el) {
		return !!(el && el.closest && el.closest("#fbr-xpos-overlay, [data-fbr-history], [data-fbr-preview]"));
	}

	function hasNativeFbrDialog() {
		if (nativeVue()) return true;
		var dialogs = document.querySelectorAll('[role="dialog"]');
		for (var i = 0; i < dialogs.length; i++) {
			if (isOverlayNode(dialogs[i])) continue;
			var text = dialogs[i].textContent || "";
			if (text.indexOf("FBR Invoice No") >= 0 || dialogs[i].querySelector('img[alt="FBR QR"]')) {
				return true;
			}
		}
		return false;
	}

	function hasNativeFbrHistory() {
		if (nativeVue()) return true;
		var imgs = document.querySelectorAll('img[alt="FBR QR"]');
		for (var i = 0; i < imgs.length; i++) {
			if (!isOverlayNode(imgs[i])) return true;
		}
		return false;
	}

	function csrf() {
		return (window.xpos && window.xpos.csrf_token) || "";
	}

	function esc(value) {
		return String(value == null ? "" : value)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;")
			.replace(/'/g, "&#39;");
	}

	function qrUrl(fbrNo, size) {
		var value = String(fbrNo || "").trim();
		if (!value) return "";
		size = size || 140;
		return (
			"https://api.qrserver.com/v1/create-qr-code/?size=" +
			size +
			"x" +
			size +
			"&data=" +
			encodeURIComponent(value)
		);
	}

	function api(method, args) {
		return fetch("/api/method/" + method, {
			method: "POST",
			credentials: "same-origin",
			headers: {
				"Content-Type": "application/json",
				Accept: "application/json",
				"X-Frappe-CSRF-Token": csrf(),
			},
			body: JSON.stringify(args || {}),
		}).then(function (res) {
			return res.json().then(function (data) {
				if (!res.ok || data.exc) {
					throw new Error((data && data._server_messages) || "FBR request failed");
				}
				return data.message;
			});
		});
	}

	function methodFromUrl(url) {
		var marker = "/api/method/";
		var idx = String(url || "").indexOf(marker);
		if (idx < 0) return "";
		return decodeURIComponent(String(url).slice(idx + marker.length).split("?")[0]);
	}

	function parseBody(init) {
		if (!init || !init.body) return {};
		if (typeof init.body === "string") {
			try {
				return JSON.parse(init.body);
			} catch (e) {
				return {};
			}
		}
		return {};
	}

	function cssEscape(name) {
		if (window.CSS && typeof CSS.escape === "function") {
			return CSS.escape(name);
		}
		return String(name).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
	}

	function wrapFetch() {
		if (!window.fetch) return;
		var orig = window.fetch;
		window.fetch = function (input, init) {
			var url = typeof input === "string" ? input : (input && input.url) || "";
			return orig.apply(this, arguments).then(function (res) {
				try {
					onFetch(url, init, res.clone());
				} catch (e) {}
				return res;
			});
		};
	}

	function onFetch(url, init, res) {
		if (!url || url.indexOf("/api/method/") < 0 || !res || !res.ok) return;
		var method = methodFromUrl(url);
		var body = parseBody(init);
		res.json()
			.then(function (data) {
				var msg = data && data.message;
				if (method === "xpos.api.invoices.create_invoice" && msg && msg.name) {
					setTimeout(function () {
						if (hasNativeFbrDialog()) return;
						showDialog(msg.name);
					}, 700);
				}
				if (method === "frappe.client.get_list") {
					var dt = body.doctype;
					if (dt === "Sales Invoice" || dt === "POS Invoice") {
						var rows = Array.isArray(msg) ? msg : [];
						var names = rows.map(function (row) { return row && row.name; }).filter(Boolean);
						if (names.length) enrichHistory(names);
					}
				}
				if (method === "xpos.api.invoices.get_invoice_details" && msg && msg.name) {
					setTimeout(function () {
						if (hasNativeFbrDialog() || hasNativeFbrHistory()) return;
						injectPreview(msg.name);
					}, 350);
				}
			})
			.catch(function () {});
	}

	function showDialog(invoiceName) {
		closeDialog();
		api("fbr_integration.handler.get_pos_fbr_status", { name: invoiceName })
			.then(function (d) {
				renderDialog(invoiceName, d || {});
			})
			.catch(function () {
				renderDialog(invoiceName, { ok: false, fbr_error: "Could not load FBR status." });
			});
	}

	function closeDialog() {
		var existing = document.getElementById("fbr-xpos-overlay");
		if (existing) existing.remove();
	}

	function renderDialog(invoiceName, d) {
		closeDialog();
		var fbrNo = String((d && d.fbr_invoice_no) || "").trim();
		var ok = !!(d && d.ok && fbrNo);
		var qrSrc = (d && d.qr_data_url) || qrUrl(fbrNo, 170);
		var statusLine = ok
			? "Invoice successfully reported to FBR."
			: (d && d.fbr_error) || "Invoice is saved. Use Send to FBR if auto-send is off or failed.";

		var overlay = document.createElement("div");
		overlay.id = "fbr-xpos-overlay";
		overlay.className = "fbr-xpos-overlay";
		overlay.innerHTML =
			'<div class="fbr-xpos-card" role="dialog" aria-modal="true">' +
			"<h3>" +
			esc(ok ? "Sent to FBR" : "FBR not sent yet") +
			"</h3>" +
			'<div class="fbr-xpos-sub">' +
			esc(invoiceName) +
			"</div>" +
			'<div class="fbr-xpos-body">' +
			'<div class="fbr-xpos-banner ' +
			(ok ? "ok" : "pending") +
			'">' +
			esc(statusLine) +
			"</div>" +
			(qrSrc && fbrNo
				? '<div class="fbr-xpos-qr"><img src="' + esc(qrSrc) + '" alt="FBR QR"></div>'
				: "") +
			'<table class="fbr-xpos-table"><tbody>' +
			'<tr><td class="fbr-xpos-muted">ERP Invoice</td><td>' +
			esc((d && d.sales_invoice) || invoiceName) +
			"</td></tr>" +
			'<tr><td class="fbr-xpos-muted">FBR Invoice No</td><td>' +
			esc(fbrNo || "—") +
			"</td></tr>" +
			'<tr><td class="fbr-xpos-muted">FBR Status</td><td>' +
			esc((d && d.fbr_status) || "—") +
			(d && d.fbr_status_code ? " (" + esc(d.fbr_status_code) + ")" : "") +
			"</td></tr>" +
			'<tr><td class="fbr-xpos-muted">Customer</td><td>' +
			esc((d && (d.customer_name || d.customer)) || "") +
			"</td></tr>" +
			"</tbody></table></div>" +
			'<div class="fbr-xpos-actions">' +
			'<button type="button" class="fbr-xpos-close">Close</button>' +
			(ok ? "" : '<button type="button" class="primary fbr-xpos-send">Send to FBR</button>') +
			"</div></div>";

		overlay.addEventListener("click", function (ev) {
			if (ev.target === overlay) closeDialog();
		});
		overlay.querySelector(".fbr-xpos-close").addEventListener("click", closeDialog);
		var sendBtn = overlay.querySelector(".fbr-xpos-send");
		if (sendBtn) {
			sendBtn.addEventListener("click", function () {
				sendBtn.disabled = true;
				sendBtn.textContent = "Sending…";
				api("fbr_integration.handler.send_to_fbr_si", { name: invoiceName })
					.then(function () {
						showDialog(invoiceName);
					})
					.catch(function () {
						sendBtn.disabled = false;
						sendBtn.textContent = "Send to FBR";
					});
			});
		}
		document.body.appendChild(overlay);
	}

	function enrichHistory(names) {
		if (hasNativeFbrHistory()) return;
		api("fbr_integration.handler.get_pos_fbr_status_bulk", { names: names })
			.then(function (map) {
				STATUS_MAP = Object.assign(STATUS_MAP, map || {});
				paintHistory();
			})
			.catch(function () {});
	}

	function findNameHost(name) {
		var walker = document.createTreeWalker(document.getElementById("app") || document.body, NodeFilter.SHOW_TEXT);
		var node;
		while ((node = walker.nextNode())) {
			if (String(node.textContent || "").trim() === name) {
				return node.parentElement;
			}
		}
		return null;
	}

	function paintHistory() {
		if (hasNativeFbrHistory()) return;
		Object.keys(STATUS_MAP).forEach(function (name) {
			if (document.querySelector('[data-fbr-history="' + cssEscape(name) + '"]')) return;
			var host = findNameHost(name);
			if (!host) return;
			var d = STATUS_MAP[name] || {};
			var fbrNo = String(d.fbr_invoice_no || "").trim();
			var wrap = document.createElement("div");
			wrap.setAttribute("data-fbr-history", name);
			if (fbrNo) {
				wrap.className = "fbr-xpos-history";
				wrap.innerHTML =
					'<img src="' +
					esc(qrUrl(fbrNo, 72)) +
					'" alt="FBR QR">' +
					"<div><div class=\"label\">FBR Invoice</div><div class=\"no\">" +
					esc(fbrNo) +
					"</div></div>";
			} else {
				wrap.className = "fbr-xpos-history pending";
				wrap.textContent = "FBR not sent";
			}
			host.parentElement ? host.parentElement.appendChild(wrap) : host.appendChild(wrap);
		});
	}

	function injectPreview(invoiceName) {
		if (hasNativeFbrDialog() || hasNativeFbrHistory()) return;
		var dialog = document.querySelector('[role="dialog"]');
		if (!dialog) return;
		if (dialog.querySelector('[data-fbr-preview="' + cssEscape(invoiceName) + '"]')) return;
		api("fbr_integration.handler.get_pos_fbr_status", { name: invoiceName })
			.then(function (d) {
				d = d || {};
				var fbrNo = String(d.fbr_invoice_no || "").trim();
				var box = document.createElement("div");
				box.setAttribute("data-fbr-preview", invoiceName);
				box.className = "fbr-xpos-preview" + (fbrNo ? "" : " pending");
				if (fbrNo) {
					box.innerHTML =
						"<h4>FBR Digital Invoice</h4>" +
						'<div class="fbr-xpos-history">' +
						'<img src="' +
						esc(d.qr_data_url || qrUrl(fbrNo, 160)) +
						'" alt="FBR QR">' +
						"<div><div class=\"label\">FBR Invoice No</div><div class=\"no\">" +
						esc(fbrNo) +
						"</div></div></div>";
				} else {
					box.innerHTML =
						"<h4>FBR Digital Invoice</h4><div>Not sent to FBR yet</div>" +
						'<div class="fbr-xpos-actions" style="padding:10px 0 0;"><button type="button" class="primary">Send to FBR</button></div>';
					box.querySelector("button").addEventListener("click", function () {
						var btn = this;
						btn.disabled = true;
						api("fbr_integration.handler.send_to_fbr_si", { name: invoiceName })
							.then(function () {
								box.remove();
								injectPreview(invoiceName);
							})
							.catch(function () {
								btn.disabled = false;
							});
					});
				}
				var mount = dialog.querySelector("h3, h2") || dialog.firstElementChild;
				if (mount && mount.parentElement) {
					mount.parentElement.insertBefore(box, mount.nextSibling);
				} else {
					dialog.insertBefore(box, dialog.firstChild);
				}
			})
			.catch(function () {});
	}

	wrapFetch();

	var observer = new MutationObserver(function () {
		if (!hasNativeFbrHistory() && Object.keys(STATUS_MAP).length) {
			paintHistory();
		}
	});
	if (document.documentElement) {
		observer.observe(document.documentElement, { childList: true, subtree: true });
	}
})();
