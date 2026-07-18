frappe.pages["account-details-trial-balance"].on_page_load = function (
    wrapper
) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Account Details Trial Balance",
        single_column: true,
    });

    page.body.html(frappe.render_template("account_details_trial_balance"));
    const root_element = page.body.get(0);

    // Trial Balance Dashboard
    (function (root_element) {
        // --- DOM ELEMENTS ---
        const btn = root_element.querySelector("#load_report");
        const resetBtn = root_element.querySelector("#reset_filters_btn");
        const errorEl = root_element.querySelector("#error_message");
        const loadingSpinner = root_element.querySelector("#loading_spinner");

        const fromDateEl = root_element.querySelector("#from_date");
        const toDateEl = root_element.querySelector("#to_date");
        const chartOfAccountsFilterEl = root_element.querySelector(
            "#chart_of_accounts_filter"
        );
        const rootTypeFilterEl =
            root_element.querySelector("#root_type_filter");
        const accountTypeFilterEl = root_element.querySelector(
            "#account_type_filter"
        );
        const parentAccountFilterEl = root_element.querySelector(
            "#parent_account_filter"
        );
        const accountFilterEl = root_element.querySelector("#account_filter");

        const exportCsvBtn = root_element.querySelector("#export_csv_btn");
        const printBtn = root_element.querySelector("#print_btn");
        const fullscreenBtn = root_element.querySelector("#fullscreen_btn");
        const dashboardRoot = root_element.querySelector(
            "#account_details_dashboard_root"
        );

        // --- DATA CACHES ---
        let cachedTrialBalanceDetail = [];
        let cachedTrialBalanceParent = [];
        let distinctValues = {};
        let fromDateStr = "";
        let toDateStr = "";

        // --- HELPERS ---
        function formatValue(val) {
            return Number(val || 0).toLocaleString(undefined, {
                maximumFractionDigits: 0,
            });
        }
        function formatDateYMD(d) {
            return d.toISOString().slice(0, 10);
        }

        function setDefaultDates() {
            const now = new Date();
            if (toDateEl && !toDateEl.value) {
                toDateEl.value = formatDateYMD(now);
            }
            if (fromDateEl && !fromDateEl.value) {
                // Set from date to one month before today
                const oneMonthAgo = new Date(now);
                oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);
                fromDateEl.value = formatDateYMD(oneMonthAgo);
            }
        }
        setDefaultDates();

        // Inject sticky/light table styles
        function ensureStickyLightTableStyles() {
            if (document.getElementById("sticky_light_table_styles")) return;
            const st = document.createElement("style");
            st.id = "sticky_light_table_styles";
            st.textContent = `
      table.sticky-light thead {
        position: sticky !important;
        top: 0 !important;
        z-index: 10 !important;
      }
      table.sticky-light thead th{
        position: sticky !important;
        top: 0 !important;
        z-index: 12 !important;
      }
      table.sticky-light tfoot {
        position: sticky !important;
        bottom: 0 !important;
        z-index: 10 !important;
      }
      table.sticky-light tfoot td{
        position: sticky !important;
        bottom: 0 !important;
        z-index: 11 !important;
        font-weight: 700 !important;
        background: inherit !important;
      }
      tr.group-header:hover {
        opacity: 0.9 !important;
        transform: scale(1.01) !important;
      }
      tr.group-item:hover {
        background: #e5e7eb !important;
      }
    `;
            document.head.appendChild(st);
        }

        function buildFilterObject() {
            return {
                chart_of_accounts: chartOfAccountsFilterEl?.value || "",
                root_type: rootTypeFilterEl?.value || "",
                account_type: accountTypeFilterEl?.value || "",
                parent_account: parentAccountFilterEl?.value || "",
                account: accountFilterEl?.value || "",
            };
        }

        // --- FILTER LOGIC ---
        function filterTrialBalanceDetail(data, filterCfg) {
            return (data || []).filter((row) => {
                if (filterCfg.account && row.account !== filterCfg.account)
                    return false;
                if (
                    filterCfg.parent_account &&
                    row.parent_account !== filterCfg.parent_account
                )
                    return false;
                return true;
            });
        }

        function filterTrialBalanceParent(data, filterCfg) {
            return (data || []).filter((row) => {
                if (
                    filterCfg.parent_account &&
                    row.parent_account !== filterCfg.parent_account
                )
                    return false;
                return true;
            });
        }

        // --- API CALL ---
        async function loadDashboardDataViaAPI(fromDate, toDate) {
            const filterCfg = buildFilterObject();
            const params = {
                from_date: fromDate,
                to_date: toDate,
                chart_of_accounts: filterCfg.chart_of_accounts || "",
                root_type: filterCfg.root_type || "",
                account_type: filterCfg.account_type || "",
                parent_account: filterCfg.parent_account || "",
                account: filterCfg.account || "",
            };

            return new Promise((resolve, reject) => {
                frappe.call({
                    method: "fbr_integration.custom_dashboard_api.account_details_dashboard_api",
                    args: params,
                    callback: (r) => {
                        if (r.message) resolve(r.message);
                        else reject(new Error("No data returned"));
                    },
                    error: (r) => reject(r),
                });
            });
        }

        // --- REFRESH FILTERS ---
        function refreshFilterDropdowns(distinct) {
            function setOptions(el, items, placeholder) {
                if (!el) return;
                const current = el.value;
                el.innerHTML = `<option value="">${
                    placeholder || "All"
                }</option>`;
                (items || []).forEach((item) => {
                    const opt = document.createElement("option");
                    opt.value = item;
                    opt.textContent = item;
                    el.appendChild(opt);
                });
                if (current && items.includes(current)) el.value = current;
            }

            setOptions(
                chartOfAccountsFilterEl,
                distinct.companies,
                "All Companies"
            );
            setOptions(rootTypeFilterEl, distinct.root_types, "All Root Types");
            setOptions(
                accountTypeFilterEl,
                distinct.account_types,
                "All Account Types"
            );
            setOptions(
                parentAccountFilterEl,
                distinct.parent_accounts,
                "All Parent Accounts"
            );
            setOptions(accountFilterEl, distinct.accounts, "All Accounts");
        }

        // Attach expand/collapse functionality to table container
        function attachTableExpandCollapse(host) {
            const header = host.querySelector(".table-header-collapsible");
            const content = host.querySelector(".table-content-collapsible");
            if (!header || !content) return;

            header.addEventListener("click", () => {
                const isHidden = content.style.display === "none";
                content.style.display = isHidden ? "block" : "none";
                const arrow = header.querySelector(".collapse-arrow");
                if (arrow) arrow.textContent = isHidden ? "▼" : "▶";
            });
        }

        // --- RENDERING ---
        function renderParentAccountTable(data, filterCfg) {
            const host = root_element.querySelector(
                "#parent_account_table_container"
            );
            if (!host) return;

            const filtered = filterTrialBalanceParent(data, filterCfg);

            if (!filtered.length) {
                host.innerHTML = `<div style="font-size:13px;font-weight:600;color:#374151;margin-bottom:6px;">Trial Balance - Parent Account</div>
        <div style="font-size:13px;color:#9ca3af;">No data for selected filters.</div>`;
                return;
            }

            const headerColor = "#2563eb";
            const totalColor = "#1e40af";
            const rowColor = "#eff6ff";

            const headerHtml = `
      <tr style="background:${headerColor};">
        <th style="padding:6px 8px;text-align:left;border-bottom:1px solid #e5e7eb;position:sticky;top:0;left:0;background:${headerColor};z-index:15;white-space:nowrap;font-size:14px;color:#fff;">Parent Account</th>
        <th style="padding:6px 8px;text-align:right;border-bottom:1px solid #e5e7eb;white-space:nowrap;position:sticky;top:0;background:${headerColor};z-index:12;font-size:14px;color:#fff;">Opening Balance Debit</th>
        <th style="padding:6px 8px;text-align:right;border-bottom:1px solid #e5e7eb;white-space:nowrap;position:sticky;top:0;background:${headerColor};z-index:12;font-size:14px;color:#fff;">Opening Balance Credit</th>
        <th style="padding:6px 8px;text-align:right;border-bottom:1px solid #e5e7eb;white-space:nowrap;position:sticky;top:0;background:${headerColor};z-index:12;font-size:14px;color:#fff;">Debit</th>
        <th style="padding:6px 8px;text-align:right;border-bottom:1px solid #e5e7eb;white-space:nowrap;position:sticky;top:0;background:${headerColor};z-index:12;font-size:14px;color:#fff;">Credit</th>
        <th style="padding:6px 8px;text-align:right;border-bottom:1px solid #e5e7eb;white-space:nowrap;position:sticky;top:0;background:${totalColor};color:#fff;z-index:12;font-size:14px;">Closing Balance Debit</th>
        <th style="padding:6px 8px;text-align:right;border-bottom:1px solid #e5e7eb;white-space:nowrap;position:sticky;top:0;background:${totalColor};color:#fff;z-index:12;font-size:14px;">Closing Balance Credit</th>
      </tr>`;

            let bodyHtml = "";
            filtered.forEach((row) => {
                // Try both new and old field names for backward compatibility
                const openingDebit = Number(
                    row.opening_debit !== undefined
                        ? row.opening_debit
                        : (row.opening_balance > 0 ? row.opening_balance : 0) ||
                              0
                );
                const openingCredit = Number(
                    row.opening_credit !== undefined
                        ? row.opening_credit
                        : (row.opening_balance < 0
                              ? Math.abs(row.opening_balance)
                              : 0) || 0
                );
                const closingDebit = Number(
                    row.closing_debit !== undefined
                        ? row.closing_debit
                        : (row.closing_balance > 0 ? row.closing_balance : 0) ||
                              0
                );
                const closingCredit = Number(
                    row.closing_credit !== undefined
                        ? row.closing_credit
                        : (row.closing_balance < 0
                              ? Math.abs(row.closing_balance)
                              : 0) || 0
                );

                // Calculate net balance: debit - credit
                // Split balance: if > 0 show in Debit column, if < 0 show in Credit column (absolute value)
                const openingBalanceNet = openingDebit - openingCredit;
                const closingBalanceNet = closingDebit - closingCredit;

                const openingBalanceDebit =
                    openingBalanceNet > 0 ? openingBalanceNet : 0;
                const openingBalanceCredit =
                    openingBalanceNet < 0 ? Math.abs(openingBalanceNet) : 0;
                const closingBalanceDebit =
                    closingBalanceNet > 0 ? closingBalanceNet : 0;
                const closingBalanceCredit =
                    closingBalanceNet < 0 ? Math.abs(closingBalanceNet) : 0;

                bodyHtml += `
        <tr style="background:#fff;">
          <td style="padding:6px 8px;text-align:left;border-bottom:1px solid #e5e7eb;position:sticky;left:0;background:#fff;z-index:1;font-size:12px;white-space:nowrap;">${
              row.parent_account_name || row.parent_account || ""
          }</td>
          <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;font-size:12px;font-weight:600;color:#10b981;">${
              openingBalanceDebit > 0 ? formatValue(openingBalanceDebit) : ""
          }</td>
          <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;font-size:12px;font-weight:600;color:#ef4444;">${
              openingBalanceCredit > 0 ? formatValue(openingBalanceCredit) : ""
          }</td>
          <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;font-size:12px;">${formatValue(
              row.debit || 0
          )}</td>
          <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;font-size:12px;">${formatValue(
              row.credit || 0
          )}</td>
          <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;font-weight:600;background:${rowColor};font-size:12px;color:#10b981;">${
                    closingBalanceDebit > 0
                        ? formatValue(closingBalanceDebit)
                        : ""
                }</td>
          <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;font-weight:600;background:${rowColor};font-size:12px;color:#ef4444;">${
                    closingBalanceCredit > 0
                        ? formatValue(closingBalanceCredit)
                        : ""
                }</td>
        </tr>`;
            });

            const grandTotal = filtered.reduce(
                (sum, row) => ({
                    opening_debit:
                        sum.opening_debit + (Number(row.opening_debit) || 0),
                    opening_credit:
                        sum.opening_credit + (Number(row.opening_credit) || 0),
                    debit: sum.debit + (Number(row.debit) || 0),
                    credit: sum.credit + (Number(row.credit) || 0),
                    closing_debit:
                        sum.closing_debit + (Number(row.closing_debit) || 0),
                    closing_credit:
                        sum.closing_credit + (Number(row.closing_credit) || 0),
                }),
                {
                    opening_debit: 0,
                    opening_credit: 0,
                    debit: 0,
                    credit: 0,
                    closing_debit: 0,
                    closing_credit: 0,
                }
            );

            const openingBalanceTotal =
                grandTotal.opening_debit - grandTotal.opening_credit;
            const closingBalanceTotal =
                grandTotal.closing_debit - grandTotal.closing_credit;

            const openingBalanceDebitTotal =
                openingBalanceTotal > 0 ? openingBalanceTotal : 0;
            const openingBalanceCreditTotal =
                openingBalanceTotal < 0 ? Math.abs(openingBalanceTotal) : 0;
            const closingBalanceDebitTotal =
                closingBalanceTotal > 0 ? closingBalanceTotal : 0;
            const closingBalanceCreditTotal =
                closingBalanceTotal < 0 ? Math.abs(closingBalanceTotal) : 0;

            const totalRow = `
      <tr style="background:${rowColor};font-weight:700;">
        <td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;position:sticky;bottom:0;left:0;background:${rowColor};z-index:13;font-size:14px;">Total</td>
        <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;position:sticky;bottom:0;background:${rowColor};z-index:13;font-size:14px;font-weight:700;color:#10b981;">${
                openingBalanceDebitTotal > 0
                    ? formatValue(openingBalanceDebitTotal)
                    : ""
            }</td>
        <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;position:sticky;bottom:0;background:${rowColor};z-index:13;font-size:14px;font-weight:700;color:#ef4444;">${
                openingBalanceCreditTotal > 0
                    ? formatValue(openingBalanceCreditTotal)
                    : ""
            }</td>
        <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;position:sticky;bottom:0;background:${rowColor};z-index:13;font-size:14px;">${formatValue(
                grandTotal.debit
            )}</td>
        <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;position:sticky;bottom:0;background:${rowColor};z-index:13;font-size:14px;">${formatValue(
                grandTotal.credit
            )}</td>
        <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;position:sticky;bottom:0;background:${totalColor};color:#fff;z-index:13;font-size:14px;font-weight:700;">${
                closingBalanceDebitTotal > 0
                    ? formatValue(closingBalanceDebitTotal)
                    : ""
            }</td>
        <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;position:sticky;bottom:0;background:${totalColor};color:#fff;z-index:13;font-size:14px;font-weight:700;">${
                closingBalanceCreditTotal > 0
                    ? formatValue(closingBalanceCreditTotal)
                    : ""
            }</td>
      </tr>`;

            host.innerHTML = `
      <div class="table-container-collapsible" style="background:#fff;border-radius:8px;padding:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
        <div class="table-header-collapsible" style="background:${headerColor};color:#fff;padding:12px 16px;border-radius:8px 8px 0 0;display:flex;justify-content:space-between;align-items:center;cursor:pointer;">
          <span style="font-size:14px;font-weight:700;">Trial Balance - Parent Account</span>
          <span class="collapse-arrow" style="font-size:18px;transition:transform 0.3s;">▼</span>
        </div>
        <div class="table-content-collapsible" style="overflow:auto;max-height:780px;border:1px solid #eef2f7;">
          <table class="sticky-light" style="border-collapse:collapse;width:100%;font-size:12px;background:#fff;">
            <thead>${headerHtml}</thead>
            <tbody>${bodyHtml}</tbody>
            <tfoot>${totalRow}</tfoot>
          </table>
        </div>
      </div>`;

            attachTableExpandCollapse(host);
        }

        function renderDetailAccountTable(data, filterCfg) {
            const host = root_element.querySelector(
                "#detail_account_table_container"
            );
            if (!host) return;

            const filtered = filterTrialBalanceDetail(data, filterCfg);

            if (!filtered.length) {
                host.innerHTML = `<div style="font-size:13px;font-weight:600;color:#374151;margin-bottom:6px;">Trial Balance - Detail Account</div>
        <div style="font-size:13px;color:#9ca3af;">No data for selected filters.</div>`;
                return;
            }

            const headerColor = "#7c3aed";
            const totalColor = "#6d28d9";
            const rowColor = "#f3e8ff";

            const headerHtml = `
      <tr style="background:${headerColor};">
        <th style="padding:6px 8px;text-align:left;border-bottom:1px solid #e5e7eb;position:sticky;top:0;left:0;background:${headerColor};z-index:15;white-space:nowrap;font-size:14px;color:#fff;">Account</th>
        <th style="padding:6px 8px;text-align:left;border-bottom:1px solid #e5e7eb;white-space:nowrap;position:sticky;top:0;background:${headerColor};z-index:12;font-size:14px;color:#fff;">Parent Account</th>
        <th style="padding:6px 8px;text-align:right;border-bottom:1px solid #e5e7eb;white-space:nowrap;position:sticky;top:0;background:${headerColor};z-index:12;font-size:14px;color:#fff;">Opening Balance Debit</th>
        <th style="padding:6px 8px;text-align:right;border-bottom:1px solid #e5e7eb;white-space:nowrap;position:sticky;top:0;background:${headerColor};z-index:12;font-size:14px;color:#fff;">Opening Balance Credit</th>
        <th style="padding:6px 8px;text-align:right;border-bottom:1px solid #e5e7eb;white-space:nowrap;position:sticky;top:0;background:${headerColor};z-index:12;font-size:14px;color:#fff;">Debit</th>
        <th style="padding:6px 8px;text-align:right;border-bottom:1px solid #e5e7eb;white-space:nowrap;position:sticky;top:0;background:${headerColor};z-index:12;font-size:14px;color:#fff;">Credit</th>
        <th style="padding:6px 8px;text-align:right;border-bottom:1px solid #e5e7eb;white-space:nowrap;position:sticky;top:0;background:${totalColor};color:#fff;z-index:12;font-size:14px;">Closing Balance Debit</th>
        <th style="padding:6px 8px;text-align:right;border-bottom:1px solid #e5e7eb;white-space:nowrap;position:sticky;top:0;background:${totalColor};color:#fff;z-index:12;font-size:14px;">Closing Balance Credit</th>
      </tr>`;

            let bodyHtml = "";
            filtered.forEach((row) => {
                // Try both new and old field names for backward compatibility
                const openingDebit = Number(
                    row.opening_debit !== undefined
                        ? row.opening_debit
                        : (row.opening_balance > 0 ? row.opening_balance : 0) ||
                              0
                );
                const openingCredit = Number(
                    row.opening_credit !== undefined
                        ? row.opening_credit
                        : (row.opening_balance < 0
                              ? Math.abs(row.opening_balance)
                              : 0) || 0
                );
                const closingDebit = Number(
                    row.closing_debit !== undefined
                        ? row.closing_debit
                        : (row.closing_balance > 0 ? row.closing_balance : 0) ||
                              0
                );
                const closingCredit = Number(
                    row.closing_credit !== undefined
                        ? row.closing_credit
                        : (row.closing_balance < 0
                              ? Math.abs(row.closing_balance)
                              : 0) || 0
                );

                // Calculate net balance: debit - credit
                // Split balance: if > 0 show in Debit column, if < 0 show in Credit column (absolute value)
                const openingBalanceNet = openingDebit - openingCredit;
                const closingBalanceNet = closingDebit - closingCredit;

                const openingBalanceDebit =
                    openingBalanceNet > 0 ? openingBalanceNet : 0;
                const openingBalanceCredit =
                    openingBalanceNet < 0 ? Math.abs(openingBalanceNet) : 0;
                const closingBalanceDebit =
                    closingBalanceNet > 0 ? closingBalanceNet : 0;
                const closingBalanceCredit =
                    closingBalanceNet < 0 ? Math.abs(closingBalanceNet) : 0;

                bodyHtml += `
        <tr style="background:#fff;">
          <td style="padding:6px 8px;text-align:left;border-bottom:1px solid #e5e7eb;position:sticky;left:0;background:#fff;z-index:1;font-size:12px;white-space:nowrap;">${
              row.account_name || row.account || ""
          }</td>
          <td style="padding:6px 8px;text-align:left;border-bottom:1px solid #e5e7eb;font-size:12px;white-space:nowrap;">${
              row.parent_account_name || row.parent_account || ""
          }</td>
          <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;font-size:12px;font-weight:600;color:#10b981;">${
              openingBalanceDebit > 0 ? formatValue(openingBalanceDebit) : ""
          }</td>
          <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;font-size:12px;font-weight:600;color:#ef4444;">${
              openingBalanceCredit > 0 ? formatValue(openingBalanceCredit) : ""
          }</td>
          <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;font-size:12px;">${formatValue(
              row.debit || 0
          )}</td>
          <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;font-size:12px;">${formatValue(
              row.credit || 0
          )}</td>
          <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;font-weight:600;background:${rowColor};font-size:12px;color:#10b981;">${
                    closingBalanceDebit > 0
                        ? formatValue(closingBalanceDebit)
                        : ""
                }</td>
          <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;font-weight:600;background:${rowColor};font-size:12px;color:#ef4444;">${
                    closingBalanceCredit > 0
                        ? formatValue(closingBalanceCredit)
                        : ""
                }</td>
        </tr>`;
            });

            const grandTotal = filtered.reduce(
                (sum, row) => ({
                    opening_debit:
                        sum.opening_debit + (Number(row.opening_debit) || 0),
                    opening_credit:
                        sum.opening_credit + (Number(row.opening_credit) || 0),
                    debit: sum.debit + (Number(row.debit) || 0),
                    credit: sum.credit + (Number(row.credit) || 0),
                    closing_debit:
                        sum.closing_debit + (Number(row.closing_debit) || 0),
                    closing_credit:
                        sum.closing_credit + (Number(row.closing_credit) || 0),
                }),
                {
                    opening_debit: 0,
                    opening_credit: 0,
                    debit: 0,
                    credit: 0,
                    closing_debit: 0,
                    closing_credit: 0,
                }
            );

            const openingBalanceTotal =
                grandTotal.opening_debit - grandTotal.opening_credit;
            const closingBalanceTotal =
                grandTotal.closing_debit - grandTotal.closing_credit;

            const openingBalanceDebitTotal =
                openingBalanceTotal > 0 ? openingBalanceTotal : 0;
            const openingBalanceCreditTotal =
                openingBalanceTotal < 0 ? Math.abs(openingBalanceTotal) : 0;
            const closingBalanceDebitTotal =
                closingBalanceTotal > 0 ? closingBalanceTotal : 0;
            const closingBalanceCreditTotal =
                closingBalanceTotal < 0 ? Math.abs(closingBalanceTotal) : 0;

            const totalRow = `
      <tr style="background:${rowColor};font-weight:700;">
        <td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;position:sticky;bottom:0;left:0;background:${rowColor};z-index:13;font-size:14px;">Total</td>
        <td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;position:sticky;bottom:0;background:${rowColor};z-index:13;font-size:14px;"></td>
        <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;position:sticky;bottom:0;background:${rowColor};z-index:13;font-size:14px;font-weight:700;color:#10b981;">${
                openingBalanceDebitTotal > 0
                    ? formatValue(openingBalanceDebitTotal)
                    : ""
            }</td>
        <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;position:sticky;bottom:0;background:${rowColor};z-index:13;font-size:14px;font-weight:700;color:#ef4444;">${
                openingBalanceCreditTotal > 0
                    ? formatValue(openingBalanceCreditTotal)
                    : ""
            }</td>
        <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;position:sticky;bottom:0;background:${rowColor};z-index:13;font-size:14px;">${formatValue(
                grandTotal.debit
            )}</td>
        <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;position:sticky;bottom:0;background:${rowColor};z-index:13;font-size:14px;">${formatValue(
                grandTotal.credit
            )}</td>
        <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;position:sticky;bottom:0;background:${totalColor};color:#fff;z-index:13;font-size:14px;font-weight:700;">${
                closingBalanceDebitTotal > 0
                    ? formatValue(closingBalanceDebitTotal)
                    : ""
            }</td>
        <td style="text-align:right;padding:6px 8px;border-bottom:1px solid #e5e7eb;position:sticky;bottom:0;background:${totalColor};color:#fff;z-index:13;font-size:14px;font-weight:700;">${
                closingBalanceCreditTotal > 0
                    ? formatValue(closingBalanceCreditTotal)
                    : ""
            }</td>
      </tr>`;

            host.innerHTML = `
      <div class="table-container-collapsible" style="background:#fff;border-radius:8px;padding:0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
        <div class="table-header-collapsible" style="background:${headerColor};color:#fff;padding:12px 16px;border-radius:8px 8px 0 0;display:flex;justify-content:space-between;align-items:center;cursor:pointer;">
          <span style="font-size:14px;font-weight:700;">Trial Balance - Detail Account</span>
          <span class="collapse-arrow" style="font-size:18px;transition:transform 0.3s;">▼</span>
        </div>
        <div class="table-content-collapsible" style="overflow:auto;max-height:780px;border:1px solid #eef2f7;">
          <table class="sticky-light" style="border-collapse:collapse;width:100%;font-size:12px;background:#fff;">
            <thead>${headerHtml}</thead>
            <tbody>${bodyHtml}</tbody>
            <tfoot>${totalRow}</tfoot>
          </table>
        </div>
      </div>`;

            attachTableExpandCollapse(host);
        }

        function renderAll(filterCfg) {
            ensureStickyLightTableStyles();
            renderParentAccountTable(cachedTrialBalanceParent, filterCfg);
            renderDetailAccountTable(cachedTrialBalanceDetail, filterCfg);
        }

        // --- MAIN LOAD ---
        async function loadFreshData() {
            if (loadingSpinner) loadingSpinner.style.display = "block";
            if (errorEl) errorEl.textContent = "";
            if (btn) {
                btn.disabled = true;
                btn.textContent = "Fetching…";
            }

            fromDateStr = (fromDateEl?.value || "").trim();
            toDateStr = (toDateEl?.value || "").trim();
            if (!fromDateStr) {
                // Set from date to one month before today
                const now = new Date();
                const oneMonthAgo = new Date(now);
                oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);
                fromDateStr = formatDateYMD(oneMonthAgo);
                if (fromDateEl) fromDateEl.value = fromDateStr;
            }
            if (!toDateStr) {
                const now = new Date();
                toDateStr = formatDateYMD(now);
                if (toDateEl) toDateEl.value = toDateStr;
            }

            if (!fromDateStr || !toDateStr) {
                if (errorEl)
                    errorEl.textContent =
                        "Please select both From and To dates.";
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = "Load Report";
                }
                if (loadingSpinner) loadingSpinner.style.display = "none";
                return;
            }

            try {
                const data = await loadDashboardDataViaAPI(
                    fromDateStr,
                    toDateStr
                );

                cachedTrialBalanceDetail = data.trial_balance_detail || [];
                cachedTrialBalanceParent = data.trial_balance_parent || [];
                distinctValues = data.distinct_values || {};

                // Debug: Check if data has the expected fields
                if (cachedTrialBalanceParent.length > 0) {
                    const sample = cachedTrialBalanceParent[0];
                    console.log("Sample parent row:", sample);
                    console.log("All keys:", Object.keys(sample));
                    console.log("opening_debit value:", sample.opening_debit);
                    console.log("opening_credit value:", sample.opening_credit);
                    console.log("closing_debit value:", sample.closing_debit);
                    console.log("closing_credit value:", sample.closing_credit);
                }

                refreshFilterDropdowns(distinctValues);
                const filterCfg = buildFilterObject();
                renderAll(filterCfg);
            } catch (e) {
                console.error(e);
                if (errorEl) errorEl.textContent = "Error: " + (e.message || e);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = "Load Report";
                }
                if (loadingSpinner) loadingSpinner.style.display = "none";
            }
        }

        function reRenderOnFilterChange() {
            const filterCfg = buildFilterObject();
            renderAll(filterCfg);
        }

        function resetFilters() {
            [
                chartOfAccountsFilterEl,
                rootTypeFilterEl,
                accountTypeFilterEl,
                parentAccountFilterEl,
                accountFilterEl,
            ].forEach((el) => {
                if (el) el.value = "";
            });
            reRenderOnFilterChange();
        }

        // --- EVENT HANDLERS ---
        if (btn) btn.addEventListener("click", loadFreshData);
        if (resetBtn) resetBtn.addEventListener("click", resetFilters);

        [
            chartOfAccountsFilterEl,
            rootTypeFilterEl,
            accountTypeFilterEl,
            parentAccountFilterEl,
            accountFilterEl,
        ].forEach((el) => {
            if (el) el.addEventListener("change", reRenderOnFilterChange);
        });

        // Helper function to format number for CSV (no commas, plain number)
        // Always returns a number string, even if value is 0, null, or undefined
        function formatNumberForCSV(val) {
            // Handle null, undefined, empty string, or NaN
            if (val === null || val === undefined || val === "" || isNaN(val)) {
                return "0";
            }
            const num = Number(val);
            // Return number as string without any formatting (no commas, no quotes)
            return num.toString();
        }

        // Helper function to safely get numeric value from row
        function getNumericValue(row, fieldName) {
            if (!row) return 0;

            // Try direct property access first
            let value = row[fieldName];

            // If not found, try with underscore variations
            if (value === undefined || value === null) {
                value = row[fieldName.replace(/_/g, "_")]; // Already has underscore
            }

            // Handle null, undefined, empty string
            if (value === null || value === undefined || value === "") {
                return 0;
            }

            // Convert to number
            const num = Number(value);

            // Return 0 if NaN, otherwise return the number
            return isNaN(num) ? 0 : num;
        }

        // CSV Export function
        function exportToCSV() {
            const filterCfg = buildFilterObject();
            const filteredDetail = filterTrialBalanceDetail(
                cachedTrialBalanceDetail,
                filterCfg
            );
            const filteredParent = filterTrialBalanceParent(
                cachedTrialBalanceParent,
                filterCfg
            );

            // Debug: Log first row to see what data we have
            if (filteredParent.length > 0) {
                console.log("First Parent Row for CSV:", filteredParent[0]);
                console.log(
                    "Opening Debit:",
                    filteredParent[0].opening_debit,
                    "Type:",
                    typeof filteredParent[0].opening_debit
                );
                console.log(
                    "Closing Debit:",
                    filteredParent[0].closing_debit,
                    "Type:",
                    typeof filteredParent[0].closing_debit
                );
            }
            if (filteredDetail.length > 0) {
                console.log("First Detail Row for CSV:", filteredDetail[0]);
                console.log(
                    "Opening Debit:",
                    filteredDetail[0].opening_debit,
                    "Type:",
                    typeof filteredDetail[0].opening_debit
                );
                console.log(
                    "Closing Debit:",
                    filteredDetail[0].closing_debit,
                    "Type:",
                    typeof filteredDetail[0].closing_debit
                );
            }

            // Create CSV content
            let csvContent = "Trial Balance Report\n";
            csvContent += `From Date: ${fromDateStr}, To Date: ${toDateStr}\n\n`;

            // Parent Account Table
            csvContent += "Parent Account Trial Balance\n";
            csvContent +=
                "Parent Account,Opening Balance Debit,Opening Balance Credit,Debit,Credit,Closing Balance Debit,Closing Balance Credit\n";
            filteredParent.forEach((row) => {
                // Directly access values and ensure they're numbers
                const openingBalanceNet =
                    getNumericValue(row, "opening_debit") -
                    getNumericValue(row, "opening_credit");
                const openingBalanceDebit = formatNumberForCSV(
                    openingBalanceNet > 0 ? openingBalanceNet : 0
                );
                const openingBalanceCredit = formatNumberForCSV(
                    openingBalanceNet < 0 ? Math.abs(openingBalanceNet) : 0
                );
                const debit = formatNumberForCSV(getNumericValue(row, "debit"));
                const credit = formatNumberForCSV(
                    getNumericValue(row, "credit")
                );
                const closingBalanceNet =
                    getNumericValue(row, "closing_debit") -
                    getNumericValue(row, "closing_credit");
                const closingBalanceDebit = formatNumberForCSV(
                    closingBalanceNet > 0 ? closingBalanceNet : 0
                );
                const closingBalanceCredit = formatNumberForCSV(
                    closingBalanceNet < 0 ? Math.abs(closingBalanceNet) : 0
                );
                csvContent += `"${
                    row.parent_account_name || row.parent_account || ""
                }",${openingBalanceDebit},${openingBalanceCredit},${debit},${credit},${closingBalanceDebit},${closingBalanceCredit}\n`;
            });

            // Add totals for parent account
            const parentTotal = filteredParent.reduce(
                (sum, row) => ({
                    opening_debit:
                        sum.opening_debit +
                        getNumericValue(row, "opening_debit"),
                    opening_credit:
                        sum.opening_credit +
                        getNumericValue(row, "opening_credit"),
                    debit: sum.debit + getNumericValue(row, "debit"),
                    credit: sum.credit + getNumericValue(row, "credit"),
                    closing_debit:
                        sum.closing_debit +
                        getNumericValue(row, "closing_debit"),
                    closing_credit:
                        sum.closing_credit +
                        getNumericValue(row, "closing_credit"),
                }),
                {
                    opening_debit: 0,
                    opening_credit: 0,
                    debit: 0,
                    credit: 0,
                    closing_debit: 0,
                    closing_credit: 0,
                }
            );
            const parentOpeningBalanceTotal =
                parentTotal.opening_debit - parentTotal.opening_credit;
            const parentClosingBalanceTotal =
                parentTotal.closing_debit - parentTotal.closing_credit;
            const parentOpeningBalanceDebitTotal =
                parentOpeningBalanceTotal > 0 ? parentOpeningBalanceTotal : 0;
            const parentOpeningBalanceCreditTotal =
                parentOpeningBalanceTotal < 0
                    ? Math.abs(parentOpeningBalanceTotal)
                    : 0;
            const parentClosingBalanceDebitTotal =
                parentClosingBalanceTotal > 0 ? parentClosingBalanceTotal : 0;
            const parentClosingBalanceCreditTotal =
                parentClosingBalanceTotal < 0
                    ? Math.abs(parentClosingBalanceTotal)
                    : 0;
            csvContent += `"Total",${formatNumberForCSV(
                parentOpeningBalanceDebitTotal
            )},${formatNumberForCSV(
                parentOpeningBalanceCreditTotal
            )},${formatNumberForCSV(parentTotal.debit)},${formatNumberForCSV(
                parentTotal.credit
            )},${formatNumberForCSV(
                parentClosingBalanceDebitTotal
            )},${formatNumberForCSV(parentClosingBalanceCreditTotal)}\n\n`;

            // Detail Account Table
            csvContent += "Detail Account Trial Balance\n";
            csvContent +=
                "Account,Parent Account,Opening Balance Debit,Opening Balance Credit,Debit,Credit,Closing Balance Debit,Closing Balance Credit\n";
            filteredDetail.forEach((row) => {
                // Directly access values and ensure they're numbers
                const openingBalanceNet =
                    getNumericValue(row, "opening_debit") -
                    getNumericValue(row, "opening_credit");
                const openingBalanceDebit = formatNumberForCSV(
                    openingBalanceNet > 0 ? openingBalanceNet : 0
                );
                const openingBalanceCredit = formatNumberForCSV(
                    openingBalanceNet < 0 ? Math.abs(openingBalanceNet) : 0
                );
                const debit = formatNumberForCSV(getNumericValue(row, "debit"));
                const credit = formatNumberForCSV(
                    getNumericValue(row, "credit")
                );
                const closingBalanceNet =
                    getNumericValue(row, "closing_debit") -
                    getNumericValue(row, "closing_credit");
                const closingBalanceDebit = formatNumberForCSV(
                    closingBalanceNet > 0 ? closingBalanceNet : 0
                );
                const closingBalanceCredit = formatNumberForCSV(
                    closingBalanceNet < 0 ? Math.abs(closingBalanceNet) : 0
                );
                csvContent += `"${row.account_name || row.account || ""}","${
                    row.parent_account_name || row.parent_account || ""
                }",${openingBalanceDebit},${openingBalanceCredit},${debit},${credit},${closingBalanceDebit},${closingBalanceCredit}\n`;
            });

            // Add totals for detail account
            const detailTotal = filteredDetail.reduce(
                (sum, row) => ({
                    opening_debit:
                        sum.opening_debit +
                        getNumericValue(row, "opening_debit"),
                    opening_credit:
                        sum.opening_credit +
                        getNumericValue(row, "opening_credit"),
                    debit: sum.debit + getNumericValue(row, "debit"),
                    credit: sum.credit + getNumericValue(row, "credit"),
                    closing_debit:
                        sum.closing_debit +
                        getNumericValue(row, "closing_debit"),
                    closing_credit:
                        sum.closing_credit +
                        getNumericValue(row, "closing_credit"),
                }),
                {
                    opening_debit: 0,
                    opening_credit: 0,
                    debit: 0,
                    credit: 0,
                    closing_debit: 0,
                    closing_credit: 0,
                }
            );
            const detailOpeningBalanceTotal =
                detailTotal.opening_debit - detailTotal.opening_credit;
            const detailClosingBalanceTotal =
                detailTotal.closing_debit - detailTotal.closing_credit;
            const detailOpeningBalanceDebitTotal =
                detailOpeningBalanceTotal > 0 ? detailOpeningBalanceTotal : 0;
            const detailOpeningBalanceCreditTotal =
                detailOpeningBalanceTotal < 0
                    ? Math.abs(detailOpeningBalanceTotal)
                    : 0;
            const detailClosingBalanceDebitTotal =
                detailClosingBalanceTotal > 0 ? detailClosingBalanceTotal : 0;
            const detailClosingBalanceCreditTotal =
                detailClosingBalanceTotal < 0
                    ? Math.abs(detailClosingBalanceTotal)
                    : 0;
            csvContent += `"Total","",${formatNumberForCSV(
                detailOpeningBalanceDebitTotal
            )},${formatNumberForCSV(
                detailOpeningBalanceCreditTotal
            )},${formatNumberForCSV(detailTotal.debit)},${formatNumberForCSV(
                detailTotal.credit
            )},${formatNumberForCSV(
                detailClosingBalanceDebitTotal
            )},${formatNumberForCSV(detailClosingBalanceCreditTotal)}\n`;

            // Create download link
            const blob = new Blob([csvContent], {
                type: "text/csv;charset=utf-8;",
            });
            const link = document.createElement("a");
            const url = URL.createObjectURL(blob);
            link.setAttribute("href", url);
            link.setAttribute(
                "download",
                `trial_balance_${fromDateStr}_to_${toDateStr}.csv`
            );
            link.style.visibility = "hidden";
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        if (exportCsvBtn) exportCsvBtn.addEventListener("click", exportToCSV);
        if (printBtn)
            printBtn.addEventListener("click", () => {
                window.print();
            });
        if (fullscreenBtn)
            fullscreenBtn.addEventListener("click", () => {
                if (!document.fullscreenElement) {
                    dashboardRoot.requestFullscreen();
                } else {
                    document.exitFullscreen();
                }
            });

        // Initial load
        loadFreshData();
    })(root_element);
};
