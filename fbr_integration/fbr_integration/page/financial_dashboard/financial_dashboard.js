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
    const chartBlue = "#2da9e1";
    const chartGreen = "#47c878";
    const chartColors = [
        chartBlue,
        chartGreen,
        "#f6a623",
        "#7e57c2",
        "#ef5350",
        "#26c6da",
        "#9ccc65",
        "#ff7043",
    ];
    const state = {
        company: frappe.defaults.get_user_default("Company") || "",
        from_date: TAX_YEAR.from_date,
        to_date: TAX_YEAR.to_date,
        group_by: "monthly",
        currency: frappe.defaults.get_default("currency") || "PKR",
        lastData: null,
        warehouse: "",
        chartLabels: new Map(),
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
        const amount = Math.round(Number(value || 0));
        if (typeof format_currency === "function") {
            return format_currency(amount, state.currency, 0).replace(
                /([.,])00\b/g,
                ""
            );
        }
        return amount.toLocaleString();
    }

    function chartNumber(value) {
        return Math.round(Number(value || 0)).toLocaleString();
    }

    function roundedChartData(data = {}) {
        return {
            ...data,
            datasets: (data.datasets || []).map((dataset) => ({
                ...dataset,
                values: (dataset.values || []).map((value) =>
                    Math.round(Number(value || 0))
                ),
            })),
        };
    }

    function number(value) {
        return Math.round(Number(value || 0)).toLocaleString();
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
            const axisOptions = ["bar", "line"].includes(config.type)
                ? {
                      ...(config.axisOptions || {}),
                      shortenYAxisNumbers: 1,
                      numberFormatter: chartNumber,
                  }
                : config.axisOptions;
            const chartConfig = ["bar", "line"].includes(config.type)
                ? {
                      valuesOverPoints: 1,
                      ...config,
                      data: roundedChartData(config.data),
                      axisOptions,
                      barOptions: {
                          ...(config.barOptions || {}),
                          spaceRatio: 0.08,
                      },
                  }
                : config;
            new frappe.Chart(node, {
                showLegend: 0,
                ...chartConfig,
                tooltipOptions: { formatTooltipY: (d) => money(d) },
            });
            if (["bar", "line"].includes(config.type)) {
                state.chartLabels.set(selector, {
                    node,
                    type: chartConfig.type,
                    values: (chartConfig.data?.datasets || []).flatMap(
                        (dataset) => dataset.values || []
                    ),
                });
                formatAxisValueLabels(node, chartConfig);
            } else if (config.type === "pie") {
                window.setTimeout(
                    () => renderExternalSliceLabels(node, labelRows),
                    80
                );
            }
        }
        if (labelSelector) renderChartLabels(labelSelector, labelRows);
    }

    function formatAxisValueLabels(node, config) {
        const values = (config.data?.datasets || []).flatMap(
            (dataset) => dataset.values || []
        );
        let attempts = 0;
        const applyFullLabels = () => {
            const labels = node.querySelectorAll(
                "text.data-point-value, [class*='data-point-value']"
            );
            labels.forEach((element, index) => {
                if (values[index] !== undefined) {
                    element.textContent = chartNumber(values[index]);
                    orientChartLabel(element, config.type);
                }
            });
            attempts += 1;
            if (attempts < 25) {
                window.setTimeout(applyFullLabels, 250);
            }
        };
        applyFullLabels();
        window.setTimeout(applyFullLabels, 0);
        window.setTimeout(applyFullLabels, 80);
        window.setTimeout(() => {
            node.querySelectorAll("svg text").forEach((element, index) => {
                if (/^-?\d+(\.\d+)?[KMBT]$/.test(element.textContent || "")) {
                    if (values[index] !== undefined) {
                        element.textContent = chartNumber(values[index]);
                        orientChartLabel(element, config.type);
                    }
                }
            });
        }, 500);
    }

    function orientChartLabel(element, type) {
        if (type !== "bar") {
            element.removeAttribute("transform");
            element.setAttribute("text-anchor", "middle");
            return;
        }
        const x = Number(element.getAttribute("x") || 0);
        const y = Number(element.getAttribute("y") || 0);
        element.setAttribute("transform", `rotate(-90 ${x} ${y})`);
        element.setAttribute("text-anchor", "start");
        element.setAttribute("dominant-baseline", "middle");
        element.setAttribute("dx", "4");
        element.setAttribute("dy", "0");
    }

    function relabelAllCharts() {
        state.chartLabels.forEach(({ node, type, values }) => {
            if (!node || !node.isConnected) return;
            const labels = node.querySelectorAll(
                "text.data-point-value, [class*='data-point-value']"
            );
            labels.forEach((element, index) => {
                if (values[index] !== undefined) {
                    element.textContent = chartNumber(values[index]);
                    orientChartLabel(element, type);
                }
            });
        });
    }

    function scheduleRelabelAllCharts() {
        [0, 80, 250, 700, 1200, 2200, 4000, 7000, 10000].forEach((delay) =>
            window.setTimeout(relabelAllCharts, delay)
        );
    }

    function renderExternalSliceLabels(node, rows) {
        $(node).find(".fd-pie-label-layer").remove();
        const total = (rows || []).reduce(
            (sum, row) => sum + Number(row.value || 0),
            0
        );
        if (!total) return;

        const layer = $(
            "<div class='fd-pie-label-layer'><svg viewBox='0 0 100 100' preserveAspectRatio='none'></svg></div>"
        ).appendTo(node);
        const svg = layer.find("svg");
        let angle = -90;
        const positions = [];

        (rows || []).forEach((row) => {
            const value = Number(row.value || 0);
            if (value <= 0) return;
            const portion = value / total;
            const midAngle = angle + portion * 180;
            const radians = (midAngle * Math.PI) / 180;
            const edgeX = 50 + Math.cos(radians) * 31;
            const edgeY = 50 + Math.sin(radians) * 31;
            const elbowX = 50 + Math.cos(radians) * 39;
            const elbowY = 50 + Math.sin(radians) * 39;
            const side = Math.cos(radians) >= 0 ? "right" : "left";
            positions.push({
                row,
                value,
                edgeX,
                edgeY,
                elbowX,
                elbowY,
                side,
                y: elbowY,
            });
            angle += portion * 360;
        });

        ["left", "right"].forEach((side) => {
            const sideRows = positions
                .filter((position) => position.side === side)
                .sort((a, b) => a.y - b.y);
            sideRows.forEach((position, index) => {
                const minY = 8 + index * 9;
                const maxY = 92 - (sideRows.length - index - 1) * 9;
                position.labelY = Math.min(Math.max(position.y, minY), maxY);
                position.labelX = side === "right" ? 72 : 28;
                position.anchorX = side === "right" ? 62 : 38;
            });
        });

        positions.forEach((position) => {
            svg.append(
                `<polyline points="${position.edgeX},${position.edgeY} ${position.elbowX},${position.elbowY} ${position.anchorX},${position.labelY}" />`
            );
            $(
                `<span class="fd-pie-label fd-pie-label-${
                    position.side
                }"><b>${escape(position.row.label)}</b> — <em>${money(
                    position.value
                )}</em></span>`
            )
                .css({
                    left: `${position.labelX}%`,
                    top: `${position.labelY}%`,
                })
                .appendTo(layer);
        });
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
                const change = row.change || 0;
                const netClass = change >= 0 ? "fd-good" : "fd-bad";
                return `<tr><td>${escape(
                    row.period
                )}</td><td class="text-right">${money(
                    row.exclusive || 0
                )}</td><td class="text-right">${money(
                    row.tax || 0
                )}</td><td class="text-right">${money(
                    row.inclusive || row.amount || 0
                )}</td><td class="text-right ${netClass}">${pct(
                    change
                )}</td></tr>`;
            })
            .join("");
        $(selector).html(html || rowEmpty(5, `No ${type} rows found`));
    }

    function renderAging(selector, rows, labelField) {
        const total = (rows || []).reduce(
            (sum, row) =>
                sum +
                Number(
                    row.outstanding ||
                        row.outstanding_amount ||
                        row.total_due ||
                        row.amount ||
                        0
                ),
            0
        );
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
        const totalRow = `<tr class="fd-total-row"><td>Total</td><td class="text-right">${money(
            total
        )}</td><td></td></tr>`;
        $(selector).html((html ? html + totalRow : "") || rowEmpty(3));
    }

    function renderInvoiceTaxRows(selector, rows) {
        const total = (rows || []).reduce(
            (sum, row) => sum + Number(row.tax_amount || 0),
            0
        );
        const html = (rows || [])
            .map(
                (row) =>
                    `<tr><td>${escape(row.account_head)}</td><td>${escape(
                        row.description
                    )}</td><td class="text-right">${number(
                        row.rate
                    )}%</td><td class="text-right">${money(
                        row.tax_amount
                    )}</td><td class="text-right">${number(
                        row.invoice_count
                    )}</td></tr>`
            )
            .join("");
        const totalRow = `<tr class="fd-total-row"><td colspan="3">Total</td><td class="text-right">${money(
            total
        )}</td><td></td></tr>`;
        $(selector).html((html ? html + totalRow : "") || rowEmpty(5));
    }

    function renderTaxAccountRows(selector, rows) {
        const html = (rows || [])
            .map((row) => {
                const indent = Number(row.indent || 0);
                return `<tr class="${
                    row.is_group ? "fd-tree-group" : ""
                }"><td style="padding-left: ${8 + indent * 18}px">${escape(
                    row.account
                )}</td><td class="text-right">${money(
                    row.debit
                )}</td><td class="text-right">${money(
                    row.credit
                )}</td><td class="text-right">${money(row.balance)}</td></tr>`;
            })
            .join("");
        $(selector).html(html || rowEmpty(4));
    }

    function taxRowLabel(row) {
        const rate = Number(row.rate || 0);
        return `${row.description || row.account_head || "-"} ${
            rate ? `(${number(rate)}%)` : ""
        }`.trim();
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
        renderChart(
            "#fdOverviewSalesPurchaseChart",
            null,
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
                colors: [chartBlue, chartGreen],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
                barOptions: { stacked: 0 },
            },
            []
        );

        renderChart(
            "#fdTrendChart",
            null,
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
                colors: [chartBlue, chartGreen],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
                lineOptions: { regionFill: 1, showDots: 1 },
            },
            []
        );

        renderChart(
            "#fdSalesChart",
            null,
            {
                type: "bar",
                height: 300,
                data: {
                    labels,
                    datasets: [{ name: __("Sales"), values: salesValues }],
                },
                colors: [chartBlue],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
            },
            []
        );

        renderChart(
            "#fdPurchaseChart",
            null,
            {
                type: "bar",
                height: 300,
                data: {
                    labels,
                    datasets: [
                        { name: __("Purchases"), values: purchaseValues },
                    ],
                },
                colors: [chartGreen],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
            },
            []
        );
    }

    function renderDashboard(data) {
        state.lastData = data;
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
            null,
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
                colors: [chartBlue],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
            },
            []
        );

        renderChart(
            "#fdRevenueSourceChart",
            null,
            {
                type: "bar",
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
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
            },
            []
        );

        renderChart(
            "#fdExpenseChart",
            null,
            {
                type: "bar",
                height: 280,
                data: {
                    labels: data.expense_breakdown?.labels || [],
                    datasets: [
                        { values: data.expense_breakdown?.values || [] },
                    ],
                },
                colors: [chartBlue, chartGreen],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
            },
            []
        );
        renderChart(
            "#fdExpensesTabChart",
            null,
            {
                type: "bar",
                height: 320,
                data: {
                    labels: data.expense_breakdown?.labels || [],
                    datasets: [
                        { values: data.expense_breakdown?.values || [] },
                    ],
                },
                colors: [chartBlue, chartGreen],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
            },
            []
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
        $("#fdExpenseRows").html(
            datasetRows(
                data.expense_breakdown?.labels || [],
                data.expense_breakdown?.values || []
            )
                .map(
                    (row) =>
                        `<tr><td>${escape(
                            row.label
                        )}</td><td class="text-right">${money(
                            row.value
                        )}</td></tr>`
                )
                .join("") || rowEmpty(2)
        );
        const expenseGroupRows = (data.expense_hierarchy || []).filter(
            (row) => row.is_group
        );
        const expenseGroupTotal = expenseGroupRows
            .filter((row) => Number(row.indent || 0) === 0)
            .reduce((sum, row) => sum + Number(row.value || 0), 0);
        const expenseGroupTotalRow = expenseGroupTotal
            ? `<tr class="fd-expense-group-total fd-total-row"><td>Total Expenses</td><td class="text-right">${money(
                  expenseGroupTotal
              )}</td></tr>`
            : "";
        $("#fdExpenseGroupRows").html(
            expenseGroupRows
                .map((row) => {
                    const indent = Number(row.indent || 0);
                    return `<tr class="fd-expense-group-row fd-expense-group-level-${Math.min(
                        indent,
                        4
                    )}"><td style="padding-left: ${8 + indent * 18}px">${escape(
                        row.account
                    )}</td><td class="text-right">${money(
                        row.value
                    )}</td></tr>`;
                })
                .join("") + expenseGroupTotalRow || rowEmpty(2)
        );
        $("#fdExpenseHierarchyRows").html(
            (data.expense_hierarchy || [])
                .map((row) => {
                    const indent = Number(row.indent || 0);
                    return `<tr class="${
                        row.is_group ? "fd-tree-group" : ""
                    }"><td style="padding-left: ${8 + indent * 18}px">${escape(
                        row.account
                    )}</td><td class="text-right">${money(
                        row.value
                    )}</td></tr>`;
                })
                .join("") || rowEmpty(2)
        );
        renderStock(data.stock_by_item_group || []);
        renderWarehouseOptions(data.warehouses || []);

        renderSimpleRows("#fdSalesRows", data.sales_summary, "sales");
        renderSimpleRows("#fdPurchaseRows", data.purchases_summary, "purchase");
        renderAging("#fdReceivablesRows", data.receivables, "customer");
        renderAging("#fdPayablesRows", data.payables, "supplier");
        renderInvoiceTaxRows("#fdSalesTaxRows", data.sales_tax_summary);
        renderInvoiceTaxRows("#fdPurchaseTaxRows", data.purchase_tax_summary);
        renderChart(
            "#fdSalesTaxChart",
            null,
            {
                type: "bar",
                height: 240,
                data: {
                    labels: (data.sales_tax_summary || []).map(taxRowLabel),
                    datasets: [
                        {
                            name: __("Sales Tax"),
                            values: (data.sales_tax_summary || []).map(
                                (row) => row.tax_amount || 0
                            ),
                        },
                    ],
                },
                colors: [chartBlue],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
            },
            []
        );
        renderChart(
            "#fdPurchaseTaxChart",
            null,
            {
                type: "bar",
                height: 240,
                data: {
                    labels: (data.purchase_tax_summary || []).map(taxRowLabel),
                    datasets: [
                        {
                            name: __("Purchase Tax"),
                            values: (data.purchase_tax_summary || []).map(
                                (row) => row.tax_amount || 0
                            ),
                        },
                    ],
                },
                colors: [chartGreen],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
            },
            []
        );
        renderTaxAccountRows(
            "#fdWithholdingTaxRows",
            data.tax_account_reports?.withholding_income_taxes || []
        );
        renderTaxAccountRows(
            "#fdDutiesTaxRows",
            data.tax_account_reports?.duties_and_taxes || []
        );

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
        $("#fdTaxPeriodRows").html(
            (data.tax_period_summary || [])
                .map((row) => {
                    const net = row.net_tax || 0;
                    return `<tr><td>${escape(
                        row.period
                    )}</td><td class="text-right">${money(
                        row.sales_tax
                    )}</td><td class="text-right">${money(
                        row.purchase_tax
                    )}</td><td class="text-right ${
                        net >= 0 ? "fd-good" : "fd-bad"
                    }">${money(net)}</td></tr>`;
                })
                .join("") || rowEmpty(4)
        );
        renderChart(
            "#fdTaxPeriodChart",
            null,
            {
                type: "bar",
                height: 260,
                data: {
                    labels: (data.tax_period_summary || []).map(
                        (row) => row.period || "-"
                    ),
                    datasets: [
                        {
                            name: __("Sales Tax"),
                            values: (data.tax_period_summary || []).map(
                                (row) => row.sales_tax || 0
                            ),
                        },
                        {
                            name: __("Purchase Tax"),
                            values: (data.tax_period_summary || []).map(
                                (row) => row.purchase_tax || 0
                            ),
                        },
                        {
                            name: __("Net Tax"),
                            values: (data.tax_period_summary || []).map(
                                (row) => row.net_tax || 0
                            ),
                        },
                    ],
                },
                colors: [chartBlue, chartGreen, "#f6a623"],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
            },
            []
        );

        renderRatioRows(data.ratios);
    }

    function renderStock(rows) {
        const chartRows = rows.slice(0, 12);
        renderChart(
            "#fdStockChart",
            null,
            {
                type: "bar",
                height: 320,
                data: {
                    labels: chartRows.map((row) => row.item_group || "-"),
                    datasets: [
                        {
                            name: __("Stock Value"),
                            values: chartRows.map(
                                (row) => row.closing_value || 0
                            ),
                        },
                    ],
                },
                colors: [chartBlue],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
            },
            []
        );
        $("#fdStockRows").html(
            rows
                .map(
                    (row) =>
                        `<tr><td>${escape(
                            row.item_group
                        )}</td><td class="text-right">${number(
                            row.closing_qty
                        )}</td><td class="text-right">${money(
                            row.closing_value
                        )}</td></tr>`
                )
                .join("") || rowEmpty(3)
        );
    }

    function renderWarehouseOptions(warehouses) {
        const current = state.warehouse;
        const options =
            `<option value="">${__("All Warehouses")}</option>` +
            (warehouses || [])
                .map(
                    (warehouse) =>
                        `<option value="${escape(warehouse)}">${escape(
                            warehouse
                        )}</option>`
                )
                .join("");
        $("#fdStockWarehouse").html(options).val(current);
    }

    async function loadStockForWarehouse() {
        if (!state.company) return;
        const rows = await call("get_stock_by_item_group", {
            company: state.company,
            warehouse: state.warehouse,
        });
        renderStock(rows || []);
        scheduleRelabelAllCharts();
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
            scheduleRelabelAllCharts();
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
        scheduleRelabelAllCharts();
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
    $("#fdStockWarehouse").on("change", function () {
        state.warehouse = this.value;
        loadStockForWarehouse();
    });
    $("#fdRefresh").on("click", loadDashboard);

    $("#fdFromDate").val(state.from_date);
    $("#fdToDate").val(state.to_date);
    $("#fdGroupBy").val(state.group_by);
    loadCompanies().then(loadDashboard);
};
