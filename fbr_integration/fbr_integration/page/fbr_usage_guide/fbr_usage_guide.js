frappe.pages["fbr-usage-guide"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("FBR Usage Guide"),
        single_column: true,
    });

    $(wrapper).find(".layout-main-section").html(`
        <div style="max-width: 1120px; margin: 0 auto; padding: 14px 10px 28px 10px; line-height: 1.6;">
            <div style="background: linear-gradient(135deg, #1f4e79 0%, #2b6da8 55%, #4f8fcc 100%); border-radius: 14px; padding: 18px 18px; margin-bottom: 16px; color: #fff; box-shadow: 0 10px 25px rgba(22, 69, 112, 0.2);">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:14px;flex-wrap:wrap;">
                    <div>
                        <div style="font-size: 20px; font-weight: 700; margin-bottom: 4px; letter-spacing:0.2px;">FBR Pakistan Guide Center</div>
                        <div style="font-size: 13px; opacity:0.95;">Central place for onboarding, scenarios, logs, doctypes, and operational shortcuts.</div>
                    </div>
                    <div style="display:flex;gap:8px;flex-wrap:wrap;">
                        <a href="/app/fbr-pakistan" style="background:#fff;color:#1f4e79;font-size:12px;padding:6px 10px;border-radius:999px;font-weight:700;text-decoration:none;">Open Workspace</a>
                        <a href="/app/sales-invoice" style="background:rgba(255,255,255,0.16);border:1px solid rgba(255,255,255,0.35);color:#fff;font-size:12px;padding:6px 10px;border-radius:999px;font-weight:700;text-decoration:none;">Open Sales Invoice</a>
                    </div>
                </div>
            </div>

            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-bottom:16px;">
                <div style="border:1px solid #dbe4ee;border-radius:12px;padding:13px;background:#fff;box-shadow:0 2px 8px rgba(16,24,40,0.04);">
                    <div style="font-weight:700;margin-bottom:8px;color:#1f2937;">1) Select Scenario</div>
                    <ol style="padding-left:18px;margin:0;font-size:13px;color:#334155;">
                        <li>Open <b>Sales Invoice</b></li>
                        <li>Click <b>Scenario Index</b></li>
                        <li>Search by SN code/title</li>
                        <li>Click <b>Use</b> to apply</li>
                    </ol>
                </div>
                <div style="border:1px solid #dbe4ee;border-radius:12px;padding:13px;background:#fff;box-shadow:0 2px 8px rgba(16,24,40,0.04);">
                    <div style="font-weight:700;margin-bottom:8px;color:#1f2937;">2) Send to FBR</div>
                    <ol style="padding-left:18px;margin:0;font-size:13px;color:#334155;">
                        <li>Verify customer + tax fields</li>
                        <li>Save and Submit invoice</li>
                        <li>Click <b>Send to FBR</b></li>
                        <li>Use QR/status popup for confirmation</li>
                    </ol>
                </div>
                <div style="border:1px solid #dbe4ee;border-radius:12px;padding:13px;background:#fff;box-shadow:0 2px 8px rgba(16,24,40,0.04);">
                    <div style="font-weight:700;margin-bottom:8px;color:#1f2937;">3) Rebuild Scenario Files</div>
                    <pre style="background:#0f172a;color:#e2e8f0;padding:10px;border-radius:8px;font-size:11px;white-space:pre-wrap;">cd ~/frappe-bench/apps/fbr_integration
fbr-build-scenarios
cd ~/frappe-bench
bench build --app fbr_integration
bench --site site1.local clear-cache
bench restart</pre>
                </div>
            </div>

            <div style="border:1px solid #dbe4ee;border-radius:12px;padding:13px;background:#fff;margin-bottom:16px;box-shadow:0 2px 8px rgba(16,24,40,0.04);">
                <div style="font-weight:700;margin-bottom:8px;color:#1f2937;">Quick Access</div>
                <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:8px;font-size:13px;">
                    <a href="/app/sales-invoice" target="_blank">Sales Invoice</a>
                    <a href="/app/fbr-usage-guide" target="_blank">FBR Usage Guide</a>
                    <a href="/app/fbr-home" target="_blank">FBR Home</a>
                    <a href="/app/financial-dashboard" target="_blank">Financial Dashboard</a>
                    <a href="/app/error-log" target="_blank">Error Log</a>
                    <a href="/app/scheduled-job-log" target="_blank">Scheduled Job Log</a>
                    <a href="/app/scenario-id" target="_blank">Scenario ID</a>
                    <a href="/app/fbr-invoice-settings" target="_blank">FBR Invoice Settings</a>
                    <a href="/app/query-report/FBR%20Sales%20Detail" target="_blank">FBR Sales Detail Report</a>
                    <a href="/app/query-report/FBR%20Sales%20Summary" target="_blank">FBR Sales Summary Report</a>
                </div>
            </div>

            <div style="border:1px solid #dbe4ee;border-radius:12px;padding:13px;background:#fff;box-shadow:0 2px 8px rgba(16,24,40,0.04);">
                <div style="font-weight:700;margin-bottom:8px;color:#1f2937;">Debug & Reference</div>
                <div style="font-size:13px;color:#334155;margin-bottom:8px;">
                    Full written guide is available in repository file <b>USAGE_GUIDE.md</b>.
                </div>
                <div style="font-size:13px;color:#475569;">
                    Browser console helper: <code>clear_fbr_scenario_cache()</code>
                </div>
            </div>

            <div style="border:1px solid #e2e8f0;border-radius:12px;padding:16px;background:#fff;margin-top:16px;box-shadow:0 2px 8px rgba(16,24,40,0.04);">
                <div style="font-weight:700;margin-bottom:12px;font-size:15px;color:#1a202c;">28 Scenarios at a Glance</div>
                <div style="margin-bottom:12px;">
                    <input type="text" id="fbr_scenario_search" placeholder="Search by ID, title, or description..." style="width:100%;padding:8px;border:1px solid #cbd5e0;border-radius:6px;font-size:13px;box-sizing:border-box;" />
                </div>
                <div id="fbr_scenario_grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;max-height:600px;overflow-y:auto;padding-right:8px;">
                    <!-- Scenarios loaded here by JS -->
                </div>
            </div>
        </div>
    `);

    // Load and display 28 scenarios
    setTimeout(() => {
        const gridContainer = document.getElementById("fbr_scenario_grid");
        const searchInput = document.getElementById("fbr_scenario_search");
        let allScenarios = [];

        async function loadScenarios() {
            try {
                const resp = await fetch(
                    "/assets/fbr_integration/scenario_docs/index.json"
                );
                if (!resp.ok) throw new Error("Failed to load scenarios");
                allScenarios = await resp.json();
                renderScenarios(allScenarios);
            } catch (err) {
                gridContainer.innerHTML = `<div style="grid-column:1/-1;color:#c53030;font-size:13px;padding:12px;">Error loading scenarios: ${err.message}</div>`;
            }
        }

        function renderScenarios(scenarios) {
            gridContainer.innerHTML = scenarios
                .map(
                    (s) => `
                <div style="border:1px solid #e2e8f0;border-radius:8px;padding:12px;background:#f9fafb;transition:all 0.2s;cursor:pointer;" class="fbr-scenario-card">
                    <div style="font-weight:700;color:#2d3748;margin-bottom:4px;font-size:14px;">${
                        s.id
                    }</div>
                    <div style="font-size:12px;font-weight:600;color:#4a5568;margin-bottom:8px;line-height:1.3;">${
                        s.title
                    }</div>
                    <div style="font-size:12px;color:#718096;line-height:1.4;margin-bottom:10px;min-height:40px;max-height:50px;overflow:hidden;text-overflow:ellipsis;">${(
                        s.description || ""
                    ).substring(0, 120)}${
                        (s.description || "").length > 120 ? "..." : ""
                    }</div>
                    <div style="display:flex;gap:6px;flex-wrap:wrap;">
                        <button class="btn-view-scenario btn btn-sm btn-default" data-sid="${
                            s.id
                        }" style="flex:1;min-width:80px;font-size:12px;padding:6px 8px;cursor:pointer;">View JSON</button>
                        <button class="btn-copy-scenario btn btn-sm btn-default" data-sid="${
                            s.id
                        }" style="flex:1;min-width:80px;font-size:12px;padding:6px 8px;cursor:pointer;">Copy</button>
                    </div>
                </div>
            `
                )
                .join("");

            document.querySelectorAll(".btn-view-scenario").forEach((btn) => {
                btn.onclick = () =>
                    showScenarioJSON(btn.getAttribute("data-sid"));
            });
            document.querySelectorAll(".btn-copy-scenario").forEach((btn) => {
                btn.onclick = () =>
                    copyScenarioJSON(btn.getAttribute("data-sid"));
            });
        }

        async function showScenarioJSON(scenarioId) {
            try {
                const resp = await fetch(
                    `/assets/fbr_integration/scenario_docs/${scenarioId}.json`
                );
                const data = await resp.json();
                const jsonStr = JSON.stringify(data.sample || {}, null, 2);
                frappe.msgprint({
                    title: `Scenario ${scenarioId} - Sample Payload`,
                    indicator: "blue",
                    message: `<pre style="background:#1f2937;color:#e5e7eb;padding:12px;border-radius:6px;font-size:12px;max-height:500px;overflow:auto;white-space:pre-wrap;word-break:break-word;font-family:monospace;">${frappe.utils.escape_html(
                        jsonStr
                    )}</pre>`,
                    wide: true,
                });
            } catch (err) {
                frappe.msgprint({
                    title: "Error",
                    indicator: "red",
                    message: `Failed to load scenario: ${err.message}`,
                });
            }
        }

        async function copyScenarioJSON(scenarioId) {
            try {
                const resp = await fetch(
                    `/assets/fbr_integration/scenario_docs/${scenarioId}.json`
                );
                const data = await resp.json();
                const jsonStr = JSON.stringify(data.sample || {}, null, 2);
                navigator.clipboard
                    .writeText(jsonStr)
                    .then(() => {
                        frappe.show_alert({
                            message: `${scenarioId} JSON copied to clipboard`,
                            indicator: "green",
                        });
                    })
                    .catch((err) => {
                        frappe.show_alert({
                            message: `Copy failed: ${err.message}`,
                            indicator: "orange",
                        });
                    });
            } catch (err) {
                frappe.show_alert({
                    message: `Error: ${err.message}`,
                    indicator: "red",
                });
            }
        }

        searchInput.addEventListener("input", (e) => {
            const q = (e.target.value || "").toLowerCase().trim();
            const filtered = allScenarios.filter((s) => {
                const hay = `${s.id} ${s.title} ${s.description}`.toLowerCase();
                return !q || hay.includes(q);
            });
            renderScenarios(filtered.length ? filtered : allScenarios);
            if (filtered.length === 0 && q) {
                gridContainer.innerHTML = `<div style="grid-column:1/-1;color:#718096;font-size:13px;padding:12px;text-align:center;">No scenarios matched your search.</div>`;
            }
        });

        loadScenarios();
    }, 100);
};
