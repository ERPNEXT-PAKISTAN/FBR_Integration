frappe.pages["financial-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Financial Dashboard",
        single_column: true,
    });

    frappe.require("/assets/fbr_integration/css/financial_dashboard.css");
    page.body.html(frappe.render_template("financial_dashboard"));
    const body = $(page.body);

    const API =
        "fbr_integration.fbr_integration.page.financial_dashboard.financial_dashboard";
    const TAX_YEAR = { from_date: "2025-07-01", to_date: "2026-06-30" };
    const chartColors = [
        "#155eef",
        "#0f9f6e",
        "#f59e0b",
        "#dc2626",
        "#7c3aed",
        "#06b6d4",
        "#84cc16",
        "#f97316",
    ];
    const state = {
        company: frappe.defaults.get_user_default("Company") || "",
        from_date: TAX_YEAR.from_date,
        to_date: TAX_YEAR.to_date,
        group_by: "monthly",
        currency: frappe.defaults.get_default("currency") || "PKR",
    };

    function call(method, args = {}) {
        return new Promise((resolve) => {
            frappe.call({
                method: `${API}.${method}`,
                args,
                callback: (r) => resolve(r.message),
            });
        });
    }

    function money(value) {
        return frappe.format(value || 0, {
            fieldtype: "Currency",
            options: state.currency,
            precision: 0,
        });
    }

    function pct(value) {
        const number = Number(value || 0);
        return `${number >= 0 ? "+" : ""}${number.toFixed(1)}%`;
    }

    function fmtDate(value) {
        return frappe.datetime.str_to_user(value);
    }

    function escape(value) {
        return frappe.utils.escape_html(value || "-");
    }

    function setBusy(isBusy) {
        $("#fdRefresh")
            .prop("disabled", isBusy)
            .text(isBusy ? __("Loading...") : __("Refresh"));
        $(".fd-shell").toggleClass("fd-loading", isBusy);
    }

    function resetChart(selector) {
        const node = document.querySelector(selector);
        if (!node || !node.parentNode) return null;
        const clone = node.cloneNode(false);
        node.parentNode.replaceChild(clone, node);
        return clone;
    }

    function renderChart(selector, labelSelector, config, labelRows = []) {
        const node = resetChart(selector);
        if (node && typeof frappe.Chart !== "undefined") {
            new frappe.Chart(node, {
                ...config,
                tooltipOptions: { formatTooltipY: (d) => money(d) },
            });
        }
        renderChartLabels(labelSelector, labelRows);
    }

    function renderChartLabels(selector, rows) {
        const html = (rows || [])
            .slice(0, 24)
            .map(
                (row, index) =>
                    `<span class="fd-chart-label"><i style="background:${
                        chartColors[index % chartColors.length]
                    }"></i><b>${escape(row.label)}</b><em>${money(
                        row.value
                    )}</em></span>`
            )
            .join("");
        $(selector).html(html);
    }

    function datasetRows(labels, values) {
        return (labels || []).map((label, index) => ({
            label,
            value: (values || [])[index] || 0,
        }));
    }

    function setChange(selector, value, positiveIsGood = true) {
        const number = Number(value || 0);
        const good = positiveIsGood ? number >= 0 : number <= 0;
        $(selector)
            .text(pct(number))
            .toggleClass("fd-good", number !== 0 && good)
            .toggleClass("fd-bad", number !== 0 && !good);
    }

    function rowEmpty(cols, text = "No data found") {
        return `<tr><td colspan="${cols}" class="fd-empty">${__(
            text
        )}</td></tr>`;
    }

    function renderSimpleRows(selector, rows, type) {
        const html = (rows || [])
            .slice(-12)
            .map((row) => {
                const amount = row.amount || 0;
                const change = row.change || 0;
                const netClass = change >= 0 ? "fd-good" : "fd-bad";
                return `<tr><td>${escape(
                    row.period
                )}</td><td class="text-right">${money(
                    amount
                )}</td><td class="text-right ${netClass}">${pct(
                    change
                )}</td></tr>`;
            })
            .join("");
        $(selector).html(html || rowEmpty(3, `No ${type} rows found`));
    }

    function renderAging(selector, rows, labelField) {
        const html = (rows || [])
            .slice(0, 10)
            .map((row) => {
                const label =
                    row[`${labelField}_name`] ||
                    row[labelField] ||
                    row.party ||
                    row.name ||
                    "-";
                const value =
                    row.outstanding ||
                    row.outstanding_amount ||
                    row.total_due ||
                    row.amount ||
                    0;
                const age = Math.max(Number(row.age || 0), 0);
                return `<tr><td>${escape(
                    label
                )}</td><td class="text-right">${money(
                    value
                )}</td><td class="text-right">${age} days</td></tr>`;
            })
            .join("");
        $(selector).html(html || rowEmpty(3));
    }

    function renderRatioRows(rows) {
        const html = (rows || [])
            .map((row, index) => {
                const theme = [
                    "blue",
                    "green",
                    "amber",
                    "purple",
                    "red",
                    "teal",
                ][index % 6];
                return `<div class="fd-ratio fd-ratio-${theme}"><span>${escape(
                    row.category
                )}</span><strong>${escape(row.name)}</strong><b>${
                    row.value || 0
                }</b><small>${escape(row.description)}</small></div>`;
            })
            .join("");
        $("#fdRatioRows").html(
            html || `<div class="fd-empty">${__("No ratio data found")}</div>`
        );
    }

    function renderTrendCharts(data) {
        const trend = data.trend || {};
        const labels = trend.labels || [];
        const salesValues = trend.revenue || [];
        const purchaseValues = trend.expense || [];
        const salesPurchaseLabels = labels.flatMap((label, index) => [
            { label: `${label} Sales`, value: salesValues[index] || 0 },
            { label: `${label} Purchases`, value: purchaseValues[index] || 0 },
        ]);

        renderChart(
            "#fdOverviewSalesPurchaseChart",
            "#fdOverviewSalesPurchaseLabels",
            {
                type: "bar",
                height: 300,
                data: {
                    labels,
                    datasets: [
                        { name: __("Sales"), values: salesValues },
                        { name: __("Purchases"), values: purchaseValues },
                    ],
                },
                colors: ["#0f9f6e", "#155eef"],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 1 },
                barOptions: { stacked: 0 },
            },
            salesPurchaseLabels
        );

        renderChart(
            "#fdTrendChart",
            "#fdTrendLabels",
            {
                type: "line",
                height: 280,
                data: {
                    labels,
                    datasets: [
                        { name: __("Revenue"), values: salesValues },
                        { name: __("Expenses"), values: purchaseValues },
                    ],
                },
                colors: ["#16a34a", "#dc2626"],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 1 },
                lineOptions: { regionFill: 1 },
            },
            salesPurchaseLabels
        );

        renderChart(
            "#fdSalesChart",
            "#fdSalesLabels",
            {
                type: "bar",
                height: 300,
                data: {
                    labels,
                    datasets: [{ name: __("Sales"), values: salesValues }],
                },
                colors: ["#0f9f6e"],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 1 },
            },
            datasetRows(labels, salesValues)
        );

        renderChart(
            "#fdPurchaseChart",
            "#fdPurchaseLabels",
            {
                type: "bar",
                height: 300,
                data: {
                    labels,
                    datasets: [
                        { name: __("Purchases"), values: purchaseValues },
                    ],
                },
                colors: ["#155eef"],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 1 },
            },
            datasetRows(labels, purchaseValues)
        );
    }

    function renderDashboard(data) {
        state.currency = data.currency || state.currency;
        const s = data.summary || {};
        const activity = data.activity || {};

        $("#fdPeriodLabel").text(
            `${data.tax_year?.label || "Tax Year"} · ${fmtDate(
                data.from_date
            )} to ${fmtDate(data.to_date)}`
        );
        $("#fdCurrentPeriodText").text(data.period_label || "—");
        $("#fdPreviousPeriodText").text(data.previous_period_label || "—");
        $("#fdRevenue").html(money(s.revenue));
        $("#fdExpense").html(money(s.expense));
        $("#fdProfit").html(money(s.profit));
        $("#fdMargin").text(`${Number(s.margin || 0).toFixed(1)}%`);
        setChange("#fdRevenueChange", s.revenue_change, true);
        setChange("#fdExpenseChange", s.expense_change, false);
        setChange("#fdProfitChange", s.profit_change, true);
        setChange("#fdMarginChange", s.margin_change, true);
        $("#fdSalesCount").text(activity.sales_count || 0);
        $("#fdSalesTotal").html(money(activity.sales_total));
        $("#fdPurchaseCount").text(
            (activity.purchase_invoice_count || 0) +
                (activity.purchase_receipt_count || 0)
        );
        $("#fdPurchaseTotal").html(
            money(
                (activity.purchase_invoice_total || 0) +
                    (activity.purchase_receipt_total || 0)
            )
        );

        renderTrendCharts(data);

        renderChart(
            "#fdCashFlowChart",
            "#fdCashFlowLabels",
            {
                type: "bar",
                height: 280,
                data: {
                    labels: data.cash_flow?.labels || [],
                    datasets: [
                        {
                            name: __("Amount"),
                            values: data.cash_flow?.values || [],
                        },
                    ],
                },
                colors: ["#2563eb"],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 1 },
            },
            datasetRows(
                data.cash_flow?.labels || [],
                data.cash_flow?.values || []
            )
        );

        renderChart(
            "#fdRevenueSourceChart",
            "#fdRevenueSourceLabels",
            {
                type: "pie",
                height: 280,
                data: {
                    labels: (data.revenue_sources || []).map(
                        (row) => row.item_group || "-"
                    ),
                    datasets: [
                        {
                            values: (data.revenue_sources || []).map(
                                (row) => row.amount || 0
                            ),
                        },
                    ],
                },
                colors: chartColors,
            },
            (data.revenue_sources || []).map((row) => ({
                label: row.item_group,
                value: row.amount,
            }))
        );

        renderChart(
            "#fdExpenseChart",
            "#fdExpenseLabels",
            {
                type: "donut",
                height: 280,
                data: {
                    labels: data.expense_breakdown?.labels || [],
                    datasets: [
                        { values: data.expense_breakdown?.values || [] },
                    ],
                },
                colors: ["#ef4444", "#f59e0b"],
            },
            datasetRows(
                data.expense_breakdown?.labels || [],
                data.expense_breakdown?.values || []
            )
        );

        $("#fdRevenueSources").html(
            (data.revenue_sources || [])
                .map(
                    (row) =>
                        `<tr><td>${escape(
                            row.item_group
                        )}</td><td class="text-right">${money(
                            row.amount
                        )}</td><td class="text-right">${Number(
                            row.percent || 0
                        ).toFixed(1)}%</td></tr>`
                )
                .join("") || rowEmpty(3)
        );

        renderSimpleRows("#fdSalesRows", data.sales_summary, "sales");
        renderSimpleRows("#fdPurchaseRows", data.purchases_summary, "purchase");
        renderAging("#fdReceivablesRows", data.receivables, "customer");
        renderAging("#fdPayablesRows", data.payables, "supplier");

        const salesByPeriod = Object.fromEntries(
            (data.sales_summary || []).map((row) => [
                row.period,
                row.amount || 0,
            ])
        );
        const purchaseByPeriod = Object.fromEntries(
            (data.purchases_summary || []).map((row) => [
                row.period,
                row.amount || 0,
            ])
        );
        const periods = Array.from(
            new Set([
                ...Object.keys(salesByPeriod),
                ...Object.keys(purchaseByPeriod),
            ])
        ).sort();
        $("#fdTaxYearRows").html(
            periods
                .map((period) => {
                    const sales = salesByPeriod[period] || 0;
                    const purchases = purchaseByPeriod[period] || 0;
                    const net = sales - purchases;
                    return `<tr><td>${period}</td><td class="text-right">${money(
                        sales
                    )}</td><td class="text-right">${money(
                        purchases
                    )}</td><td class="text-right ${
                        net >= 0 ? "fd-good" : "fd-bad"
                    }">${money(net)}</td></tr>`;
                })
                .join("") || rowEmpty(4)
        );

        renderRatioRows(data.ratios);
    }

    async function loadCompanies() {
        const companies = await call("get_companies");
        const options = (companies || [])
            .map(
                (company) =>
                    `<option value="${escape(company)}">${escape(
                        company
                    )}</option>`
            )
            .join("");
        $("#fdCompany").html(options);
        if (!state.company && companies?.length) state.company = companies[0];
        $("#fdCompany").val(state.company);
    }

    async function loadDashboard() {
        if (!state.company) return;
        setBusy(true);
        try {
            const data = await call("get_dashboard_data", {
                company: state.company,
                from_date: state.from_date,
                to_date: state.to_date,
                group_by: state.group_by,
            });
            renderDashboard(data || {});
        } finally {
            setBusy(false);
        }
    }

    function applyPreset(preset) {
        const today = frappe.datetime.get_today();
        if (preset === "tax_year") {
            state.from_date = TAX_YEAR.from_date;
            state.to_date = TAX_YEAR.to_date;
        } else if (preset === "today") {
            state.from_date = today;
            state.to_date = today;
        } else if (preset === "this_month") {
            state.from_date = frappe.datetime.month_start();
            state.to_date = today;
        } else if (preset === "this_quarter") {
            state.from_date = frappe.datetime.quarter_start();
            state.to_date = today;
        }
        $("#fdFromDate").val(state.from_date);
        $("#fdToDate").val(state.to_date);
    }

    body.on("click", ".fd-tab", function () {
        const tab = $(this).data("tab");
        $(".fd-tab").removeClass("active");
        $(this).addClass("active");
        $(".fd-tab-panel").removeClass("active");
        $(`#fd-tab-${tab}`).addClass("active");
    });

    body.on("click", ".fd-preset", function () {
        $(".fd-preset").removeClass("active");
        $(this).addClass("active");
        applyPreset($(this).data("preset"));
        loadDashboard();
    });

    $("#fdCompany").on("change", function () {
        state.company = this.value;
        loadDashboard();
    });
    $("#fdFromDate, #fdToDate").on("change", function () {
        state.from_date = $("#fdFromDate").val();
        state.to_date = $("#fdToDate").val();
        $(".fd-preset").removeClass("active");
        loadDashboard();
    });
    $("#fdGroupBy").on("change", function () {
        state.group_by = this.value;
        loadDashboard();
    });
    $("#fdRefresh").on("click", loadDashboard);

    $("#fdFromDate").val(state.from_date);
    $("#fdToDate").val(state.to_date);
    $("#fdGroupBy").val(state.group_by);
    loadCompanies().then(loadDashboard);
};
