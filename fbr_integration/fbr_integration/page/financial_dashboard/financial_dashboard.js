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
    const today = frappe.datetime.get_today();
    const todayYear = Number(today.slice(0, 4));
    const todayMonth = Number(today.slice(5, 7));
    const taxYearStart = todayMonth >= 7 ? todayYear : todayYear - 1;
    const TAX_YEAR = {
        from_date: `${taxYearStart}-07-01`,
        to_date: `${taxYearStart + 1}-06-30`,
        label: `Tax Year ${taxYearStart}-${taxYearStart + 1}`,
    };
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

    function statusBadge(value, kind = "invoice") {
        const label = value || "-";
        const normalized = String(label).toLowerCase();
        let theme = "neutral";
        if (
            normalized.includes("paid") ||
            normalized.includes("submit") ||
            normalized.includes("success") ||
            normalized === "yes"
        ) {
            theme = "green";
        } else if (
            normalized.includes("draft") ||
            normalized.includes("pending") ||
            normalized.includes("unpaid") ||
            normalized === "no"
        ) {
            theme = "amber";
        } else if (
            normalized.includes("fail") ||
            normalized.includes("cancel") ||
            normalized.includes("overdue")
        ) {
            theme = "red";
        } else if (kind === "fbr" && normalized.includes("fbr")) {
            theme = "blue";
        }
        return `<span class="fd-status-badge fd-status-badge-${theme}">${escape(
            label
        )}</span>`;
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
                    orientChartLabel(element, config.type, node);
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
                        orientChartLabel(element, config.type, node);
                    }
                }
            });
        }, 500);
    }

    function orientChartLabel(element, type, node) {
        if (type !== "bar") {
            element.removeAttribute("transform");
            element.setAttribute("text-anchor", "middle");
            return;
        }
        const x = Number(element.getAttribute("x") || 0);
        const y = Number(element.getAttribute("y") || 0);
        element.setAttribute("transform", `rotate(-90 ${x} ${y})`);
        element.setAttribute("text-anchor", "end");
        element.setAttribute("dominant-baseline", "middle");
        element.setAttribute("dx", "-6");
        element.setAttribute("dy", "0");
        window.requestAnimationFrame(() =>
            fitBarLabelInsideChart(element, node)
        );
    }

    function fitBarLabelInsideChart(element, node, attempt = 0) {
        if (!element?.isConnected || !node?.isConnected || attempt > 2) return;
        const svg = node.querySelector("svg");
        if (!svg) return;
        const chartBox = svg.getBoundingClientRect();
        const labelBox = element.getBoundingClientRect();
        if (!chartBox.height || !labelBox.height) return;

        const safeTop = chartBox.top + 12;
        const safeBottom = chartBox.bottom - 42;
        const availableHeight = Math.max(safeBottom - safeTop, 40);
        if (labelBox.height > availableHeight && attempt === 0) {
            element.style.fontSize = "9px";
        }

        let dx = Number(element.getAttribute("dx") || 0);
        if (labelBox.bottom > safeBottom) {
            dx += labelBox.bottom - safeBottom + 6;
        }
        if (labelBox.top < safeTop) {
            dx -= safeTop - labelBox.top + 6;
        }
        element.setAttribute("dx", String(Math.round(dx)));

        window.requestAnimationFrame(() =>
            fitBarLabelInsideChart(element, node, attempt + 1)
        );
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
                    orientChartLabel(element, type, node);
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
        const visibleRows = (rows || []).slice(-12);
        const totals = visibleRows.reduce(
            (sum, row) => ({
                exclusive: sum.exclusive + Number(row.exclusive || 0),
                tax: sum.tax + Number(row.tax || 0),
                inclusive:
                    sum.inclusive + Number(row.inclusive || row.amount || 0),
            }),
            { exclusive: 0, tax: 0, inclusive: 0 }
        );
        const html = visibleRows
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
        const totalRow = `<tr class="fd-total-row"><td>Total</td><td class="text-right">${money(
            totals.exclusive
        )}</td><td class="text-right">${money(
            totals.tax
        )}</td><td class="text-right">${money(
            totals.inclusive
        )}</td><td></td></tr>`;
        $(selector).html(
            (html ? html + totalRow : "") ||
                rowEmpty(5, `No ${type} rows found`)
        );
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

    function renderSalesReturnRows(selector, rows) {
        const totals = (rows || []).reduce(
            (sum, row) => {
                sum.exclusive += Number(row.exclusive || 0);
                sum.tax += Number(row.tax || 0);
                sum.inclusive += Number(row.inclusive || 0);
                return sum;
            },
            { exclusive: 0, tax: 0, inclusive: 0 }
        );
        const html = (rows || [])
            .map(
                (row) =>
                    `<tr><td><a href="/app/sales-invoice/${escape(
                        row.name
                    )}" target="_blank">${escape(
                        row.name
                    )}</a></td><td>${escape(
                        fmtDate(row.posting_date)
                    )}</td><td>${escape(row.customer_name || "-")}</td><td>${
                        row.return_against
                            ? `<a href="/app/sales-invoice/${escape(
                                  row.return_against
                              )}" target="_blank">${escape(
                                  row.return_against
                              )}</a>`
                            : "-"
                    }</td><td>${escape(
                        row.custom_fbr_source_invoice_no || "-"
                    )}</td><td class="text-right">${money(
                        row.exclusive || 0
                    )}</td><td class="text-right">${money(
                        row.tax || 0
                    )}</td><td class="text-right">${money(
                        row.inclusive || 0
                    )}</td></tr>`
            )
            .join("");
        const totalRow = `<tr class="fd-total-row"><td colspan="5">Total</td><td class="text-right">${money(
            totals.exclusive
        )}</td><td class="text-right">${money(
            totals.tax
        )}</td><td class="text-right">${money(totals.inclusive)}</td></tr>`;
        $(selector).html(
            (html ? html + totalRow : "") ||
                rowEmpty(8, "No sales returns in selected period")
        );
    }

    function renderTaxAccountRows(selector, rows) {
        const totalDebit = (rows || []).reduce(
            (sum, row) => sum + Number(row.debit || 0),
            0
        );
        const totalCredit = (rows || []).reduce(
            (sum, row) => sum + Number(row.credit || 0),
            0
        );
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
        const totalRow = `<tr class="fd-total-row"><td>Total</td><td class="text-right">${money(
            totalDebit
        )}</td><td class="text-right">${money(totalCredit)}</td><td></td></tr>`;
        $(selector).html((html ? html + totalRow : "") || rowEmpty(4));
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

        const customerGroupSales = data.customer_group_sales || [];
        renderChart(
            "#fdCustomerGroupSalesChart",
            "#fdCustomerGroupSalesLabels",
            {
                type: "bar",
                height: 320,
                data: {
                    labels: customerGroupSales.map(
                        (row) => row.customer_group || __("No Customer Group")
                    ),
                    datasets: [
                        {
                            name: __("Sales"),
                            values: customerGroupSales.map(
                                (row) => row.amount || 0
                            ),
                        },
                    ],
                },
                colors: [chartBlue],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
            },
            customerGroupSales.map((row) => ({
                label: row.customer_group || __("No Customer Group"),
                value: row.amount || 0,
            }))
        );

        const supplierGroupPurchases = data.supplier_group_purchases || [];
        renderChart(
            "#fdSupplierGroupPurchaseChart",
            "#fdSupplierGroupPurchaseLabels",
            {
                type: "bar",
                height: 320,
                data: {
                    labels: supplierGroupPurchases.map(
                        (row) => row.supplier_group || __("No Supplier Group")
                    ),
                    datasets: [
                        {
                            name: __("Purchases"),
                            values: supplierGroupPurchases.map(
                                (row) => row.amount || 0
                            ),
                        },
                    ],
                },
                colors: [chartGreen],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
            },
            supplierGroupPurchases.map((row) => ({
                label: row.supplier_group || __("No Supplier Group"),
                value: row.amount || 0,
            }))
        );
    }

    function renderStatusSummaryTable(selector, rows, labelTitle = "Label") {
        const totals = (rows || []).reduce(
            (sum, row) => ({
                invoice_count:
                    sum.invoice_count + Number(row.invoice_count || 0),
                exclusive: sum.exclusive + Number(row.exclusive || 0),
                tax: sum.tax + Number(row.tax || 0),
                inclusive: sum.inclusive + Number(row.inclusive || 0),
            }),
            { invoice_count: 0, exclusive: 0, tax: 0, inclusive: 0 }
        );
        const html = (rows || [])
            .map(
                (row) =>
                    `<tr><td>${escape(
                        row.label || labelTitle
                    )}</td><td class="text-right">${number(
                        row.invoice_count || 0
                    )}</td><td class="text-right">${money(
                        row.exclusive || 0
                    )}</td><td class="text-right">${money(
                        row.tax || 0
                    )}</td><td class="text-right">${money(
                        row.inclusive || 0
                    )}</td></tr>`
            )
            .join("");
        const totalRow = `<tr class="fd-total-row"><td>Total</td><td class="text-right">${number(
            totals.invoice_count
        )}</td><td class="text-right">${money(
            totals.exclusive
        )}</td><td class="text-right">${money(
            totals.tax
        )}</td><td class="text-right">${money(totals.inclusive)}</td></tr>`;
        $(selector).html((html ? html + totalRow : "") || rowEmpty(5));
    }

    function renderStatusMiniTable(selector, rows) {
        const total = (rows || []).reduce(
            (sum, row) => sum + Number(row.inclusive || 0),
            0
        );
        const html = (rows || [])
            .slice(0, 12)
            .map(
                (row) =>
                    `<tr><td>${escape(
                        row.label || "Not Set"
                    )}<br><small>${number(
                        row.invoice_count || 0
                    )} invoices</small></td><td class="text-right">${money(
                        row.inclusive || 0
                    )}</td></tr>`
            )
            .join("");
        const totalRow = `<tr class="fd-total-row"><td>Total</td><td class="text-right">${money(
            total
        )}</td></tr>`;
        $(selector).html((html ? html + totalRow : "") || rowEmpty(2));
    }

    function renderSalesInvoiceStatus(data) {
        const status = data.sales_invoice_status || data || {};
        const summary = status.summary || {};
        const total = Number(summary.total_invoices || 0);
        const fbrSubmitted = Number(summary.fbr_submitted_count || 0);
        const compliance = total ? (fbrSubmitted / total) * 100 : 0;
        $("#fdStatusTotal").text(number(total));
        $("#fdStatusSubmitted").text(number(summary.submitted_count || 0));
        $("#fdStatusDraft").text(number(summary.draft_count || 0));
        $("#fdStatusFailed").text(number(summary.fbr_error_count || 0));
        $("#fdStatusFbrSubmitted").text(
            number(summary.fbr_submitted_count || 0)
        );
        $("#fdStatusSalesReturn").text(number(summary.sales_return_count || 0));
        $("#fdStatusCompliance").text(`${compliance.toFixed(0)}%`);
        $("#fdStatusExclusive").html(money(summary.exclusive_sales || 0));
        $("#fdStatusTaxes").html(money(summary.taxes || 0));
        $("#fdStatusInclusive").html(money(summary.inclusive_sales || 0));
        const inclusiveSales = Number(summary.inclusive_sales || 0);
        const exclusivePct = inclusiveSales
            ? (Number(summary.exclusive_sales || 0) / inclusiveSales) * 100
            : 0;
        const taxesPct = inclusiveSales
            ? (Number(summary.taxes || 0) / inclusiveSales) * 100
            : 0;
        $("#fdStatusExclusivePct").text(
            `${exclusivePct.toFixed(1)}% of inclusive`
        );
        $("#fdStatusTaxesPct").text(`${taxesPct.toFixed(1)}% of inclusive`);
        $("#fdStatusInclusivePct").text(
            inclusiveSales ? "100.0% total" : "0.0%"
        );

        renderChart(
            "#fdInvoiceStatusChart",
            "#fdInvoiceStatusLabels",
            {
                type: "bar",
                height: 260,
                data: {
                    labels: (status.status_mix || []).map(
                        (row) => row.label || "-"
                    ),
                    datasets: [
                        {
                            values: (status.status_mix || []).map(
                                (row) => row.value || 0
                            ),
                        },
                    ],
                },
                colors: ["#22c55e", "#f59e0b", "#ef4444", "#3b82f6"],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
            },
            (status.status_mix || []).map((row) => ({
                label: row.label || "-",
                value: row.value || 0,
            }))
        );
        renderChart(
            "#fdFbrStatusChart",
            "#fdFbrStatusLabels",
            {
                type: "bar",
                height: 260,
                data: {
                    labels: (status.fbr_status_mix || []).map(
                        (row) => row.label || "-"
                    ),
                    datasets: [
                        {
                            values: (status.fbr_status_mix || []).map(
                                (row) => row.value || 0
                            ),
                        },
                    ],
                },
                colors: ["#16a34a", "#f59e0b", "#ef4444", "#64748b"],
                axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
            },
            (status.fbr_status_mix || []).map((row) => ({
                label: row.label || "-",
                value: row.value || 0,
            }))
        );

        renderStatusSummaryTable(
            "#fdStatusTaxPayerRows",
            status.tax_payer_type || [],
            "Tax Payer Type"
        );
        const itemTaxTemplateRows = status.item_tax_template || [];
        const itemTaxChartRows = itemTaxTemplateRows.slice(0, 12);
        const itemTaxMetric = itemTaxChartRows.some(
            (row) => Number(row.tax || 0) > 0
        )
            ? "tax"
            : "inclusive";
        if (itemTaxChartRows.length) {
            renderChart(
                "#fdStatusItemTaxTemplateChart",
                "#fdStatusItemTaxTemplateLabels",
                {
                    type: "bar",
                    height: 260,
                    data: {
                        labels: itemTaxChartRows.map(
                            (row) => row.item_tax_template || "Not Set"
                        ),
                        datasets: [
                            {
                                name:
                                    itemTaxMetric === "tax"
                                        ? __("Tax Amount")
                                        : __("Inclusive Sales"),
                                values: itemTaxChartRows.map(
                                    (row) => row[itemTaxMetric] || 0
                                ),
                            },
                        ],
                    },
                    colors: ["#14b8a6"],
                    axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 0 },
                },
                itemTaxChartRows.map((row) => ({
                    label: `${row.item_tax_template || "Not Set"} (${Number(
                        row.percentage || 0
                    ).toFixed(2)}%)`,
                    value: row.tax || row.inclusive || 0,
                }))
            );
        } else {
            resetChart("#fdStatusItemTaxTemplateChart");
            $("#fdStatusItemTaxTemplateLabels").empty();
        }
        const itemTaxTotals = itemTaxTemplateRows.reduce(
            (sum, row) => {
                sum.exclusive += Number(row.exclusive || 0);
                sum.tax += Number(row.tax || 0);
                sum.inclusive += Number(row.inclusive || 0);
                return sum;
            },
            { exclusive: 0, tax: 0, inclusive: 0 }
        );
        const itemTaxHtml = itemTaxTemplateRows
            .map(
                (row) =>
                    `<tr><td>${escape(
                        row.item_tax_template || "Not Set"
                    )}</td><td>${escape(
                        row.account_head || "No GL Account"
                    )}</td><td class="text-right">${Number(
                        row.percentage || 0
                    ).toFixed(2)}%</td><td class="text-right">${money(
                        row.exclusive || 0
                    )}</td><td class="text-right">${money(
                        row.tax || 0
                    )}</td><td class="text-right">${money(
                        row.inclusive || 0
                    )}</td></tr>`
            )
            .join("");
        const itemTaxTotalPct = itemTaxTotals.exclusive
            ? (itemTaxTotals.tax / itemTaxTotals.exclusive) * 100
            : 0;
        const itemTaxTotalRow = `<tr class="fd-total-row"><td>Total</td><td></td><td class="text-right">${itemTaxTotalPct.toFixed(
            2
        )}%</td><td class="text-right">${money(
            itemTaxTotals.exclusive
        )}</td><td class="text-right">${money(
            itemTaxTotals.tax
        )}</td><td class="text-right">${money(
            itemTaxTotals.inclusive
        )}</td></tr>`;
        $("#fdStatusItemTaxTemplateRows").html(
            (itemTaxHtml ? itemTaxHtml + itemTaxTotalRow : "") || rowEmpty(6)
        );
        renderStatusMiniTable(
            "#fdStatusProvinceRows",
            status.buyer_province || []
        );
        renderStatusMiniTable(
            "#fdStatusScenarioRows",
            status.scenario_detail || []
        );
        renderStatusMiniTable("#fdStatusSaleTypeRows", status.sale_type || []);
        renderStatusMiniTable("#fdStatusSroRows", status.sro_schedule || []);
        $("#fdStatusInvoiceRows").html(
            (status.recent_invoices || [])
                .map(
                    (row) =>
                        `<tr><td><a href="/app/sales-invoice/${encodeURIComponent(
                            row.name
                        )}" target="_blank">${escape(
                            row.name
                        )}</a></td><td>${fmtDate(
                            row.posting_date
                        )}</td><td>${escape(
                            row.customer_name || "-"
                        )}</td><td>${statusBadge(
                            row.status || "-",
                            "invoice"
                        )}</td><td>${statusBadge(
                            row.fbr_status ||
                                (row.fbr_invoice_no
                                    ? "Submitted to FBR"
                                    : "Pending FBR"),
                            "fbr"
                        )}</td><td>${statusBadge(
                            row.custom_fbr_responsed || "-",
                            "fbr"
                        )}</td><td>${escape(
                            row.custom_tax_payer_type || "-"
                        )}</td><td>${escape(
                            row.custom_buyer_province || "-"
                        )}</td><td class="text-right">${money(
                            row.inclusive || 0
                        )}</td></tr>`
                )
                .join("") || rowEmpty(9)
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

        const revenueRows = data.revenue_sources || [];
        const revenueTotal = revenueRows.reduce(
            (sum, row) => sum + Number(row.amount || 0),
            0
        );
        const revenuePercentTotal = revenueRows.reduce(
            (sum, row) => sum + Number(row.percent || 0),
            0
        );
        const revenueHtml = revenueRows
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
            .join("");
        const revenueTotalRow = `<tr class="fd-total-row"><td>Total</td><td class="text-right">${money(
            revenueTotal
        )}</td><td class="text-right">${revenuePercentTotal.toFixed(
            1
        )}%</td></tr>`;
        $("#fdRevenueSources").html(
            (revenueHtml ? revenueHtml + revenueTotalRow : "") || rowEmpty(3)
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
        renderSalesInvoiceStatus(data);

        renderSimpleRows("#fdSalesRows", data.sales_summary, "sales");
        renderSalesReturnRows("#fdSalesReturnRows", data.sales_returns || []);
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
        const taxYearTotals = periods.reduce(
            (sum, period) => {
                const sales = Number(salesByPeriod[period] || 0);
                const purchases = Number(purchaseByPeriod[period] || 0);
                sum.sales += sales;
                sum.purchases += purchases;
                sum.net += sales - purchases;
                return sum;
            },
            { sales: 0, purchases: 0, net: 0 }
        );
        const taxYearHtml = periods
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
            .join("");
        const taxYearTotalRow = `<tr class="fd-total-row"><td>Total</td><td class="text-right">${money(
            taxYearTotals.sales
        )}</td><td class="text-right">${money(
            taxYearTotals.purchases
        )}</td><td class="text-right ${
            taxYearTotals.net >= 0 ? "fd-good" : "fd-bad"
        }">${money(taxYearTotals.net)}</td></tr>`;
        $("#fdTaxYearRows").html(
            (taxYearHtml ? taxYearHtml + taxYearTotalRow : "") || rowEmpty(4)
        );
        const taxPeriodRows = data.tax_period_summary || [];
        const taxPeriodTotals = taxPeriodRows.reduce(
            (sum, row) => {
                sum.sales += Number(row.sales_tax || 0);
                sum.purchases += Number(row.purchase_tax || 0);
                sum.net += Number(row.net_tax || 0);
                return sum;
            },
            { sales: 0, purchases: 0, net: 0 }
        );
        const taxPeriodHtml = taxPeriodRows
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
            .join("");
        const taxPeriodTotalRow = `<tr class="fd-total-row"><td>Total</td><td class="text-right">${money(
            taxPeriodTotals.sales
        )}</td><td class="text-right">${money(
            taxPeriodTotals.purchases
        )}</td><td class="text-right ${
            taxPeriodTotals.net >= 0 ? "fd-good" : "fd-bad"
        }">${money(taxPeriodTotals.net)}</td></tr>`;
        $("#fdTaxPeriodRows").html(
            (taxPeriodHtml ? taxPeriodHtml + taxPeriodTotalRow : "") ||
                rowEmpty(4)
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
        const stockQtyTotal = rows.reduce(
            (sum, row) => sum + Number(row.closing_qty || 0),
            0
        );
        const stockValueTotal = rows.reduce(
            (sum, row) => sum + Number(row.closing_value || 0),
            0
        );
        const stockHtml = rows
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
            .join("");
        const stockTotalRow = `<tr class="fd-total-row"><td>Total</td><td class="text-right">${number(
            stockQtyTotal
        )}</td><td class="text-right">${money(stockValueTotal)}</td></tr>`;
        $("#fdStockRows").html(
            (stockHtml ? stockHtml + stockTotalRow : "") || rowEmpty(3)
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

    async function refreshDashboard() {
        await loadDashboard();
    }

    function applyPreset(preset) {
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
        if (tab === "status") {
            if (state.lastData) {
                renderSalesInvoiceStatus(state.lastData);
                scheduleRelabelAllCharts();
            } else {
                refreshDashboard();
            }
        }
    });

    body.on("click", ".fd-preset", function () {
        $(".fd-preset").removeClass("active");
        $(this).addClass("active");
        applyPreset($(this).data("preset"));
        refreshDashboard();
    });

    $("#fdCompany").on("change", function () {
        state.company = this.value;
        refreshDashboard();
    });
    $("#fdFromDate, #fdToDate").on("change", function () {
        state.from_date = $("#fdFromDate").val();
        state.to_date = $("#fdToDate").val();
        $(".fd-preset").removeClass("active");
        refreshDashboard();
    });
    $("#fdGroupBy").on("change", function () {
        state.group_by = this.value;
        refreshDashboard();
    });
    $("#fdStockWarehouse").on("change", function () {
        state.warehouse = this.value;
        loadStockForWarehouse();
    });
    $("#fdRefresh").on("click", refreshDashboard);

    $("#fdFromDate").val(state.from_date);
    $("#fdToDate").val(state.to_date);
    $("#fdGroupBy").val(state.group_by);
    loadCompanies().then(refreshDashboard);
};
