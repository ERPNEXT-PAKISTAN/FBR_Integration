import frappe
from frappe.utils import getdate, cint, add_to_date, get_first_day, get_last_day
from datetime import timedelta


@frappe.whitelist()
def get_companies():
    return frappe.get_all("Company", pluck="name")


def _get_dates(company, from_date, to_date):
    from_date = getdate(from_date)
    to_date = getdate(to_date)
    if not company:
        frappe.throw("Company is required")
    return from_date, to_date


@frappe.whitelist()
def get_financial_summary(company, from_date, to_date):
    from_date, to_date = _get_dates(company, from_date, to_date)

    # Revenue: Income accounts use (credit - debit)
    revenue_row = frappe.db.sql(
        """
        SELECT COALESCE(SUM(gle.credit) - SUM(gle.debit), 0) AS value
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s
          AND acc.root_type = 'Income'
          AND gle.posting_date BETWEEN %s AND %s
          AND gle.is_cancelled = 0
        """,
        (company, from_date, to_date),
        as_dict=True,
    )
    revenue = (revenue_row[0]["value"] or 0) if revenue_row else 0

    # Expense: Expense accounts use (debit - credit)
    expense_row = frappe.db.sql(
        """
        SELECT COALESCE(SUM(gle.debit) - SUM(gle.credit), 0) AS value
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s
          AND acc.root_type = 'Expense'
          AND gle.posting_date BETWEEN %s AND %s
          AND gle.is_cancelled = 0
        """,
        (company, from_date, to_date),
        as_dict=True,
    )
    expense = (expense_row[0]["value"] or 0) if expense_row else 0

    profit = revenue - expense
    margin = (profit / revenue * 100) if revenue else 0

    # Previous period for % change (same length)
    period_days = (to_date - from_date).days + 1
    prev_to = from_date - timedelta(days=1)
    prev_from = prev_to - timedelta(days=period_days - 1)

    prev_revenue_row = frappe.db.sql(
        """
        SELECT COALESCE(SUM(gle.credit) - SUM(gle.debit), 0) AS value
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND acc.root_type = 'Income'
          AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled = 0
        """,
        (company, prev_from, prev_to),
        as_dict=True,
    )
    prev_revenue = (prev_revenue_row[0]["value"] or 0) if prev_revenue_row else 0

    prev_expense_row = frappe.db.sql(
        """
        SELECT COALESCE(SUM(gle.debit) - SUM(gle.credit), 0) AS value
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND acc.root_type = 'Expense'
          AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled = 0
        """,
        (company, prev_from, prev_to),
        as_dict=True,
    )
    prev_expense = (prev_expense_row[0]["value"] or 0) if prev_expense_row else 0
    prev_profit = prev_revenue - prev_expense
    prev_margin = (prev_profit / prev_revenue * 100) if prev_revenue else 0

    def pct_change(current, previous):
        if not previous:
            return 0
        return round((current - previous) / previous * 100, 1)

    currency = frappe.get_cached_value("Company", company, "default_currency") or frappe.db.get_default("currency")

    return {
        "revenue": round(revenue, 0),
        "expense": round(expense, 0),
        "profit": round(profit, 0),
        "margin": round(margin, 1),
        "currency": currency,
        "revenue_change": pct_change(revenue, prev_revenue),
        "expense_change": pct_change(expense, prev_expense),
        "profit_change": pct_change(profit, prev_profit),
        "margin_change": round(margin - prev_margin, 1),
    }


@frappe.whitelist()
def get_trend_data(company, from_date, to_date, group_by="monthly"):
    from_date, to_date = _get_dates(company, from_date, to_date)
    if group_by == "yearly":
        period_expr = "YEAR(gle.posting_date)"
    elif group_by == "quarterly":
        period_expr = "CONCAT(YEAR(gle.posting_date), '-Q', QUARTER(gle.posting_date))"
    else:
        period_expr = "DATE_FORMAT(gle.posting_date, '%%Y-%%m')"

    rows = frappe.db.sql(
        """
        SELECT
            """ + period_expr + """ AS period,
            acc.root_type,
            SUM(gle.credit) - SUM(gle.debit) AS income,
            SUM(gle.debit) - SUM(gle.credit) AS expense
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s
          AND gle.posting_date BETWEEN %s AND %s
          AND gle.is_cancelled = 0
          AND acc.root_type IN ('Income', 'Expense')
        GROUP BY period, acc.root_type
        ORDER BY period
        """,
        (company, from_date, to_date),
        as_dict=True,
    )
    periods = sorted(set(r["period"] for r in rows))
    revenue = []
    expense = []
    for p in periods:
        rev = next((r["income"] or 0 for r in rows if r["period"] == p and r["root_type"] == "Income"), 0)
        exp = next((r["expense"] or 0 for r in rows if r["period"] == p and r["root_type"] == "Expense"), 0)
        revenue.append(rev)
        expense.append(exp)
    return {"labels": [str(p) for p in periods], "revenue": revenue, "expense": expense}


@frappe.whitelist()
def get_expense_breakdown(company, from_date, to_date):
    from_date, to_date = _get_dates(company, from_date, to_date)
    rows = frappe.db.sql(
        """
        SELECT acc.account_name AS label, SUM(gle.debit) - SUM(gle.credit) AS value
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND acc.root_type = 'Expense'
          AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled = 0
        GROUP BY acc.name
        HAVING value > 0
        ORDER BY value DESC
        LIMIT 10
        """,
        (company, from_date, to_date),
        as_dict=True,
    )
    labels = [r["label"] for r in rows]
    values = [r["value"] for r in rows]
    return {"labels": labels, "values": values}


@frappe.whitelist()
def get_cash_flow(company, from_date, to_date):
    """Cash flow summary for chart: Operating, Investing, Financing (linked to statement logic)."""
    from_date, to_date = _get_dates(company, from_date, to_date)
    rev_row = frappe.db.sql(
        """SELECT COALESCE(SUM(credit)-SUM(debit),0) AS v FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company=%s AND acc.root_type='Income' AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled=0""",
        (company, from_date, to_date),
        as_dict=True,
    )
    exp_row = frappe.db.sql(
        """SELECT COALESCE(SUM(debit)-SUM(credit),0) AS v FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company=%s AND acc.root_type='Expense' AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled=0""",
        (company, from_date, to_date),
        as_dict=True,
    )
    operating = (rev_row[0]["v"] or 0) - (exp_row[0]["v"] or 0)
    investing = _cash_flow_investing(company, from_date, to_date)
    financing = _cash_flow_financing(company, from_date, to_date)
    return {
        "labels": ["Operating", "Investing", "Financing"],
        "values": [round(operating, 0), round(investing, 0), round(financing, 0)],
    }


@frappe.whitelist()
def get_revenue_sources(company, from_date, to_date):
    from_date, to_date = _get_dates(company, from_date, to_date)
    total_row = frappe.db.sql(
        """
        SELECT COALESCE(SUM(gle.credit)-SUM(gle.debit),0) AS total
        FROM `tabGL Entry` gle INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company=%s AND acc.root_type='Income' AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled=0
        """,
        (company, from_date, to_date),
        as_dict=True,
    )
    total = (total_row[0]["total"] or 0) if total_row else 0
    rows = frappe.db.sql(
        """
        SELECT acc.account_name AS account, SUM(gle.credit)-SUM(gle.debit) AS amount
        FROM `tabGL Entry` gle INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company=%s AND acc.root_type='Income' AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled=0
        GROUP BY acc.name HAVING amount > 0 ORDER BY amount DESC LIMIT 10
        """,
        (company, from_date, to_date),
        as_dict=True,
    )
    result = []
    for r in rows:
        pct = round(r["amount"] / total * 100, 1) if total else 0
        result.append({"account": r["account"], "amount": r["amount"], "percent": pct})
    return result


def _get_pl_accounts_tree(company, root_type):
    """Get accounts for root_type (Income/Expense) in tree order: name, account_name, parent_account, lft, is_group, include_in_gross."""
    return frappe.db.sql(
        """
        SELECT name, account_name, parent_account, lft, is_group, COALESCE(include_in_gross, 0) AS include_in_gross
        FROM `tabAccount`
        WHERE company = %s AND root_type = %s AND disabled = 0
        ORDER BY lft
        """,
        (company, root_type),
        as_dict=True,
    )


def _get_gl_balances(company, from_d, to_d):
    """Return dict name -> (income_value, expense_value) for leaf accounts in period."""
    rows = frappe.db.sql(
        """
        SELECT acc.name, acc.root_type,
            SUM(CASE WHEN acc.root_type='Income' THEN gle.credit-gle.debit ELSE 0 END) AS income,
            SUM(CASE WHEN acc.root_type='Expense' THEN gle.debit-gle.credit ELSE 0 END) AS expense
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled = 0
          AND acc.root_type IN ('Income','Expense') AND acc.is_group = 0
        GROUP BY acc.name
        """,
        (company, from_d, to_d),
        as_dict=True,
    )
    out = {}
    for r in rows:
        inc = r["income"] or 0
        exp = r["expense"] or 0
        out[r["name"]] = (inc, exp)
    return out


def _rollup_balances(accounts, gl_cur, gl_prev, root_type, gl_prev_month=None, gl_prev_quarter=None, gl_prev_year=None):
    """Set current/previous balance on each account (leaf from GL, group = sum of children). Optionally set _prev_month, _prev_quarter, _prev_year."""
    by_name = {a["name"]: a for a in accounts}
    for a in accounts:
        a["_cur"] = 0.0
        a["_prev"] = 0.0
        a["_prev_month"] = 0.0
        a["_prev_quarter"] = 0.0
        a["_prev_year"] = 0.0
    def _set_bal(gl_dict, attr, root_type):
        if not gl_dict:
            return
        for name, (inc, exp) in gl_dict.items():
            if name in by_name:
                val = inc - exp if root_type == "Income" else exp
                by_name[name][attr] = val
    _set_bal(gl_cur, "_cur", root_type)
    _set_bal(gl_prev, "_prev", root_type)
    _set_bal(gl_prev_month, "_prev_month", root_type)
    _set_bal(gl_prev_quarter, "_prev_quarter", root_type)
    _set_bal(gl_prev_year, "_prev_year", root_type)
    for a in reversed(accounts):
        if a.get("parent_account") and a["parent_account"] in by_name:
            p = by_name[a["parent_account"]]
            p["_cur"] = p.get("_cur", 0) + a["_cur"]
            p["_prev"] = p.get("_prev", 0) + a["_prev"]
            p["_prev_month"] = p.get("_prev_month", 0) + a.get("_prev_month", 0)
            p["_prev_quarter"] = p.get("_prev_quarter", 0) + a.get("_prev_quarter", 0)
            p["_prev_year"] = p.get("_prev_year", 0) + a.get("_prev_year", 0)


def _chg(v_cur, v_prev):
    return round((v_cur - v_prev) / v_prev * 100, 1) if v_prev else 0


def _append_tree_rows(out, accounts, parent_name, indent_start, row_type_account="account"):
    """Append rows for all descendants of parent_name in tree order with indent and comparative changes."""
    for a in accounts:
        if a.get("parent_account") != parent_name:
            continue
        indent = indent_start
        prev = a.get("_prev") or 0
        prev_m = a.get("_prev_month") or 0
        prev_q = a.get("_prev_quarter") or 0
        prev_y = a.get("_prev_year") or 0
        cur = a.get("_cur") or 0
        out.append({
            "account": a["account_name"],
            "current": cur,
            "previous": prev,
            "change": _chg(cur, prev),
            "change_monthly": _chg(cur, prev_m),
            "change_quarterly": _chg(cur, prev_q),
            "change_yearly": _chg(cur, prev_y),
            "row_type": row_type_account,
            "indent": indent,
        })
        _append_tree_rows(out, accounts, a["name"], indent + 1, row_type_account)


def _tree_total(accounts, parent_name):
    """Sum of _cur, _prev, etc. for direct children of parent_name only.
    After _rollup_balances, each account's _cur is already the sum of its subtree, so we must not add recursively (would double-count)."""
    cur_t = prev_t = prev_m_t = prev_q_t = prev_y_t = 0.0
    for a in accounts:
        if a.get("parent_account") != parent_name:
            continue
        cur_t += a.get("_cur", 0)
        prev_t += a.get("_prev", 0)
        prev_m_t += a.get("_prev_month", 0)
        prev_q_t += a.get("_prev_quarter", 0)
        prev_y_t += a.get("_prev_year", 0)
    return cur_t, prev_t, prev_m_t, prev_q_t, prev_y_t


@frappe.whitelist()
def get_profit_loss(company, from_date, to_date):
    """P&L with Chart of Accounts hierarchy and comparative columns (monthly, quarterly, yearly change)."""
    from_date, to_date = _get_dates(company, from_date, to_date)
    period_days = (to_date - from_date).days + 1
    prev_to = from_date - timedelta(days=1)
    prev_from = prev_to - timedelta(days=period_days - 1)
    prev_month_from = getdate(add_to_date(from_date, months=-1))
    prev_month_to = getdate(add_to_date(to_date, months=-1))
    prev_quarter_from = getdate(add_to_date(from_date, months=-3))
    prev_quarter_to = getdate(add_to_date(to_date, months=-3))
    prev_year_from = getdate(add_to_date(from_date, months=-12))
    prev_year_to = getdate(add_to_date(to_date, months=-12))

    gl_cur = _get_gl_balances(company, from_date, to_date)
    gl_prev = _get_gl_balances(company, prev_from, prev_to)
    gl_prev_month = _get_gl_balances(company, prev_month_from, prev_month_to)
    gl_prev_quarter = _get_gl_balances(company, prev_quarter_from, prev_quarter_to)
    gl_prev_year = _get_gl_balances(company, prev_year_from, prev_year_to)

    income_accounts = _get_pl_accounts_tree(company, "Income")
    expense_accounts = _get_pl_accounts_tree(company, "Expense")
    _rollup_balances(income_accounts, gl_cur, gl_prev, "Income", gl_prev_month, gl_prev_quarter, gl_prev_year)
    _rollup_balances(expense_accounts, gl_cur, gl_prev, "Expense", gl_prev_month, gl_prev_quarter, gl_prev_year)

    def _row(account, cur, prev, prev_m, prev_q, prev_y, row_type):
        return {
            "account": account,
            "current": cur, "previous": prev,
            "change": _chg(cur, prev),
            "change_monthly": _chg(cur, prev_m), "change_quarterly": _chg(cur, prev_q), "change_yearly": _chg(cur, prev_y),
            "row_type": row_type,
        }

    out = []
    # ---------- 1. Sales ----------
    out.append(_row("Sales", 0, 0, 0, 0, 0, "section_header"))
    total_sales_cur, total_sales_prev, total_sales_m, total_sales_q, total_sales_y = 0.0, 0.0, 0.0, 0.0, 0.0
    income_root = next((a["name"] for a in income_accounts if not a.get("parent_account")), None)
    if income_root:
        total_sales_cur, total_sales_prev, total_sales_m, total_sales_q, total_sales_y = _tree_total(income_accounts, income_root)
        _append_tree_rows(out, income_accounts, income_root, 1)
    out.append(_row("Total Sales", total_sales_cur, total_sales_prev, total_sales_m, total_sales_q, total_sales_y, "subtotal"))

    # ---------- 2. Direct Expenses ----------
    out.append(_row("Direct Expenses", 0, 0, 0, 0, 0, "section_header"))
    expense_root = next((a["name"] for a in expense_accounts if not a.get("parent_account")), None)
    direct_group = indirect_group = None
    expense_children = [a for a in expense_accounts if a.get("parent_account") == expense_root] if expense_root else []
    expense_children.sort(key=lambda x: x.get("lft") or 0)
    for a in expense_children:
        an = (a.get("account_name") or "").lower()
        if "direct" in an and "indirect" not in an:
            direct_group = a["name"]
        elif "indirect" in an:
            indirect_group = a["name"]
    total_direct_cur, total_direct_prev, total_direct_m, total_direct_q, total_direct_y = 0.0, 0.0, 0.0, 0.0, 0.0
    if direct_group:
        total_direct_cur, total_direct_prev, total_direct_m, total_direct_q, total_direct_y = _tree_total(expense_accounts, direct_group)
        _append_tree_rows(out, expense_accounts, direct_group, 1)
    out.append(_row("Total Direct Expenses", total_direct_cur, total_direct_prev, total_direct_m, total_direct_q, total_direct_y, "subtotal"))

    # ---------- 3. Gross Profit ----------
    gp_cur = total_sales_cur - total_direct_cur
    gp_prev = total_sales_prev - total_direct_prev
    gp_m = total_sales_m - total_direct_m
    gp_q = total_sales_q - total_direct_q
    gp_y = total_sales_y - total_direct_y
    out.append(_row("Gross Profit", gp_cur, gp_prev, gp_m, gp_q, gp_y, "subtotal"))

    # ---------- 4. Indirect Expenses ----------
    out.append(_row("Indirect Expenses", 0, 0, 0, 0, 0, "section_header"))
    total_indirect_cur, total_indirect_prev, total_indirect_m, total_indirect_q, total_indirect_y = 0.0, 0.0, 0.0, 0.0, 0.0
    if indirect_group:
        total_indirect_cur, total_indirect_prev, total_indirect_m, total_indirect_q, total_indirect_y = _tree_total(expense_accounts, indirect_group)
        _append_tree_rows(out, expense_accounts, indirect_group, 1)
    out.append(_row("Total Indirect Expenses", total_indirect_cur, total_indirect_prev, total_indirect_m, total_indirect_q, total_indirect_y, "subtotal"))

    # ---------- 5. Net Profit ----------
    net_cur = gp_cur - total_indirect_cur
    net_prev = gp_prev - total_indirect_prev
    net_m = gp_m - total_indirect_m
    net_q = gp_q - total_indirect_q
    net_y = gp_y - total_indirect_y
    out.append(_row("Net Profit", net_cur, net_prev, net_m, net_q, net_y, "total"))
    return out


@frappe.whitelist()
def get_balance_sheet(company, from_date, to_date):
    """Balance Sheet with comparative columns (monthly, quarterly, yearly change)."""
    from_date, to_date = _get_dates(company, from_date, to_date)
    prev_to = from_date - timedelta(days=1)
    prev_month_to = getdate(add_to_date(to_date, months=-1))
    prev_quarter_to = getdate(add_to_date(to_date, months=-3))
    prev_year_to = getdate(add_to_date(to_date, months=-12))

    def _bs(as_on_date):
        rows = frappe.db.sql(
            """
            SELECT acc.account_name, acc.root_type,
                SUM(CASE WHEN acc.root_type = 'Asset' THEN gle.debit-gle.credit ELSE gle.credit-gle.debit END) AS balance
            FROM `tabGL Entry` gle INNER JOIN `tabAccount` acc ON gle.account = acc.name
            WHERE gle.company=%s AND gle.posting_date <= %s AND gle.is_cancelled=0
              AND acc.root_type IN ('Asset','Liability','Equity') AND acc.is_group = 0
            GROUP BY acc.name
            """,
            (company, as_on_date),
            as_dict=True,
        )
        return {r["account_name"]: (r["root_type"], r["balance"] or 0) for r in rows}

    cur_map = _bs(to_date)
    prev_map = _bs(prev_to)
    prev_m_map = _bs(prev_month_to)
    prev_q_map = _bs(prev_quarter_to)
    prev_y_map = _bs(prev_year_to)

    out = []
    for root_type, section_label in (("Asset", "Assets"), ("Liability", "Liabilities"), ("Equity", "Equity")):
        out.append({
            "account": section_label,
            "current": 0, "previous": 0, "change": 0,
            "change_monthly": 0, "change_quarterly": 0, "change_yearly": 0,
            "row_type": "section_header",
        })
        total_cur = total_prev = total_m = total_q = total_y = 0
        for name, (rt, cur_val) in cur_map.items():
            if rt != root_type:
                continue
            prev_val = prev_map.get(name, (None, 0))[1]
            val_m = prev_m_map.get(name, (None, 0))[1]
            val_q = prev_q_map.get(name, (None, 0))[1]
            val_y = prev_y_map.get(name, (None, 0))[1]
            total_cur += cur_val
            total_prev += prev_val
            total_m += val_m
            total_q += val_q
            total_y += val_y
            out.append({
                "account": name,
                "current": cur_val, "previous": prev_val,
                "change": _chg(cur_val, prev_val),
                "change_monthly": _chg(cur_val, val_m), "change_quarterly": _chg(cur_val, val_q), "change_yearly": _chg(cur_val, val_y),
                "row_type": "account", "indent": 1,
            })
        out.append({
            "account": "Total " + section_label,
            "current": total_cur, "previous": total_prev,
            "change": _chg(total_cur, total_prev),
            "change_monthly": _chg(total_cur, total_m), "change_quarterly": _chg(total_cur, total_q), "change_yearly": _chg(total_cur, total_y),
            "row_type": "subtotal",
        })
    return out


def _months_in_range(from_date, to_date):
    """Yield (month_start, month_end, month_label) for each month in range."""
    d = getdate(get_first_day(from_date))
    to_date = getdate(to_date)
    while d <= to_date:
        month_end = getdate(get_last_day(d))
        if month_end > to_date:
            month_end = to_date
        # Label e.g. Jan 2025
        try:
            label = d.strftime("%b %Y")
        except Exception:
            label = "{}-{:02d}".format(d.year, d.month)
        yield (d, month_end, label)
        d = getdate(add_to_date(d, months=1))


@frappe.whitelist()
def get_profit_loss_monthly(company, from_date, to_date):
    """P&L with months as columns: Jan, Feb, Mar, ... (one column per month in range)."""
    from_date, to_date = _get_dates(company, from_date, to_date)
    months_list = []
    row_structure = None
    values_by_row = []

    for month_start, month_end, month_label in _months_in_range(from_date, to_date):
        pl = get_profit_loss(company, month_start, month_end)
        months_list.append(month_label)
        if row_structure is None:
            row_structure = [
                {"account": r["account"], "row_type": r.get("row_type", "account"), "indent": r.get("indent") or 0}
                for r in pl
            ]
        for i, r in enumerate(pl):
            if i >= len(values_by_row):
                values_by_row.append([])
            values_by_row[i].append(r.get("current") or 0)

    if not row_structure:
        return {"months": [], "rows": []}
    for i, row in enumerate(row_structure):
        row["values"] = values_by_row[i] if i < len(values_by_row) else []
    return {"months": months_list, "rows": row_structure}


@frappe.whitelist()
def get_balance_sheet_monthly(company, from_date, to_date):
    """Balance Sheet with months as columns: balance as of end of Jan, Feb, Mar, ..."""
    from_date, to_date = _get_dates(company, from_date, to_date)
    months_list = []
    row_structure = None
    values_by_row = []

    for month_start, month_end, month_label in _months_in_range(from_date, to_date):
        # Balance sheet as of month end
        bs = get_balance_sheet(company, month_end, month_end)
        months_list.append(month_label)
        if row_structure is None:
            row_structure = [
                {"account": r["account"], "row_type": r.get("row_type", "account"), "indent": r.get("indent") or 0}
                for r in bs
            ]
        for i, r in enumerate(bs):
            if i >= len(values_by_row):
                values_by_row.append([])
            values_by_row[i].append(r.get("current") or 0)

    if not row_structure:
        return {"months": [], "rows": []}
    for i, row in enumerate(row_structure):
        row["values"] = values_by_row[i] if i < len(values_by_row) else []
    return {"months": months_list, "rows": row_structure}


@frappe.whitelist()
def get_cash_flow_statement(company, from_date, to_date):
    """Cash flow with detail: Operating (Income/Expense by account), Investing, Financing."""
    from_date, to_date = _get_dates(company, from_date, to_date)
    # Income detail by account
    income_rows = frappe.db.sql(
        """
        SELECT acc.account_name, COALESCE(SUM(gle.credit) - SUM(gle.debit), 0) AS amount
        FROM `tabGL Entry` gle INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND acc.root_type = 'Income'
          AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled = 0
        GROUP BY acc.name
        HAVING amount != 0
        ORDER BY amount DESC
        """,
        (company, from_date, to_date),
        as_dict=True,
    )
    # Expense detail by account
    expense_rows = frappe.db.sql(
        """
        SELECT acc.account_name, COALESCE(SUM(gle.debit) - SUM(gle.credit), 0) AS amount
        FROM `tabGL Entry` gle INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND acc.root_type = 'Expense'
          AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled = 0
        GROUP BY acc.name
        HAVING amount != 0
        ORDER BY amount DESC
        """,
        (company, from_date, to_date),
        as_dict=True,
    )
    total_income = sum(r["amount"] or 0 for r in income_rows)
    total_expense = sum(r["amount"] or 0 for r in expense_rows)
    operating = total_income - total_expense

    out = [
        {"activity": "Operating Activities", "amount": 0, "row_type": "section_header"},
        {"activity": "Income", "amount": 0, "row_type": "section_header", "indent": 1},
    ]
    for r in income_rows[:15]:
        out.append({"activity": r["account_name"], "amount": round(r["amount"] or 0, 0), "row_type": "account", "indent": 2})
    out.append({"activity": "Total Income", "amount": round(total_income, 0), "row_type": "subtotal", "indent": 1})
    out.append({"activity": "Expenses", "amount": 0, "row_type": "section_header", "indent": 1})
    for r in expense_rows[:15]:
        out.append({"activity": r["account_name"], "amount": round(-(r["amount"] or 0), 0), "row_type": "account", "indent": 2})
    out.append({"activity": "Total Expenses", "amount": round(-total_expense, 0), "row_type": "subtotal", "indent": 1})
    out.append({"activity": "Net Income (Operating)", "amount": round(operating, 0), "row_type": "subtotal"})
    out.append({"activity": "Total Operating Activities", "amount": round(operating, 0), "row_type": "subtotal"})
    # Investing: Fixed Asset / Capex movement if needed; placeholder
    out.append({"activity": "Investing Activities", "amount": 0, "row_type": "section_header"})
    investing = _cash_flow_investing(company, from_date, to_date)
    out.append({"activity": "Total Investing Activities", "amount": round(investing, 0), "row_type": "subtotal"})
    out.append({"activity": "Financing Activities", "amount": 0, "row_type": "section_header"})
    financing = _cash_flow_financing(company, from_date, to_date)
    out.append({"activity": "Total Financing Activities", "amount": round(financing, 0), "row_type": "subtotal"})
    out.append({"activity": "Net Change in Cash", "amount": round(operating + investing + financing, 0), "row_type": "total"})
    return out


def _cash_flow_investing(company, from_date, to_date):
    """Sum of Fixed Asset account movements (debit - credit) = outflow."""
    r = frappe.db.sql(
        """
        SELECT COALESCE(SUM(gle.debit) - SUM(gle.credit), 0) FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND acc.account_type = 'Fixed Asset'
          AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled = 0
        """,
        (company, from_date, to_date),
    )
    return (r[0][0] or 0) if r else 0


def _cash_flow_financing(company, from_date, to_date):
    """Equity + Loan changes (simplified: equity account credit - debit)."""
    r = frappe.db.sql(
        """
        SELECT COALESCE(SUM(gle.credit) - SUM(gle.debit), 0) FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND acc.root_type IN ('Equity', 'Liability')
          AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled = 0
        """,
        (company, from_date, to_date),
    )
    return (r[0][0] or 0) if r else 0


@frappe.whitelist()
def get_trial_balance(company, from_date, to_date):
    from_date, to_date = _get_dates(company, from_date, to_date)
    rows = frappe.db.sql(
        """
        SELECT acc.account_name,
            SUM(gle.debit) AS debit, SUM(gle.credit) AS credit,
            SUM(gle.debit) - SUM(gle.credit) AS balance
        FROM `tabGL Entry` gle INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled = 0
        GROUP BY acc.name
        ORDER BY acc.account_name
        LIMIT 50
        """,
        (company, from_date, to_date),
        as_dict=True,
    )
    return [{"account": r["account_name"], "debit": r["debit"] or 0, "credit": r["credit"] or 0, "balance": r["balance"] or 0} for r in rows]


# ---------- Aging, Sales, Purchases, Expenses, Vertical/Horizontal/Ratio ----------

@frappe.whitelist()
def get_aging_receivables(company, report_date=None):
    """Aging receivables: total outstanding and by age bucket (0-30, 30-60, 60-90, 90+). Uses GL balance for Receivable accounts."""
    as_on = getdate(report_date or frappe.utils.getdate())
    if not company:
        frappe.throw("Company is required")
    # Total outstanding from Receivable accounts (debit - credit)
    total_row = frappe.db.sql(
        """
        SELECT COALESCE(SUM(gle.debit) - SUM(gle.credit), 0) AS outstanding
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND acc.account_type = 'Receivable' AND gle.is_cancelled = 0
          AND gle.posting_date <= %s
        """,
        (company, as_on),
        as_dict=True,
    )
    total = (total_row[0]["outstanding"] or 0) if total_row else 0
    # Age buckets would require Payment Ledger / invoice due dates; return summary + placeholder buckets
    return {
        "total": total,
        "buckets": [
            {"range": "0-30", "amount": total, "label": "0-30 days"},
            {"range": "30-60", "amount": 0, "label": "31-60 days"},
            {"range": "60-90", "amount": 0, "label": "61-90 days"},
            {"range": "90+", "amount": 0, "label": "90+ days"},
        ],
    }


@frappe.whitelist()
def get_aging_payables(company, report_date=None):
    """Aging payables: total outstanding (Credit - Debit for Payable accounts)."""
    as_on = getdate(report_date or frappe.utils.getdate())
    if not company:
        frappe.throw("Company is required")
    total_row = frappe.db.sql(
        """
        SELECT COALESCE(SUM(gle.credit) - SUM(gle.debit), 0) AS outstanding
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND acc.account_type = 'Payable' AND gle.is_cancelled = 0
          AND gle.posting_date <= %s
        """,
        (company, as_on),
        as_dict=True,
    )
    total = (total_row[0]["outstanding"] or 0) if total_row else 0
    return {
        "total": total,
        "buckets": [
            {"range": "0-30", "amount": total, "label": "0-30 days"},
            {"range": "30-60", "amount": 0, "label": "31-60 days"},
            {"range": "60-90", "amount": 0, "label": "61-90 days"},
            {"range": "90+", "amount": 0, "label": "90+ days"},
        ],
    }


def _period_shift(period_str, group_by, months_delta):
    """Return period key for period_str shifted by months_delta (e.g. -1, -3, -12)."""
    try:
        if group_by == "yearly":
            y = int(period_str)
            d = getdate("{}-06-01".format(y))
            d2 = add_to_date(d, months=months_delta)
            return str(d2.year)
        if group_by == "quarterly":
            # e.g. 2025-Q1 -> 2025-01-01, shift, then format back
            parts = period_str.split("-Q")
            y, q = int(parts[0]), int(parts[1])
            d = getdate("{}-{:02d}-01".format(y, (q - 1) * 3 + 1))
            d2 = add_to_date(d, months=months_delta)
            q2 = (d2.month - 1) // 3 + 1
            return "{}-Q{}".format(d2.year, q2)
        # monthly YYYY-MM
        y, m = int(period_str[:4]), int(period_str[5:7])
        d = getdate("{}-{:02d}-01".format(y, m))
        d2 = add_to_date(d, months=months_delta)
        return "{}-{:02d}".format(d2.year, d2.month)
    except Exception:
        return None


@frappe.whitelist()
def get_sales_summary(company, from_date, to_date, group_by="monthly"):
    """Sales (Income) by period with comparative columns (previous, change %, monthly/quarterly/yearly change)."""
    from_date, to_date = _get_dates(company, from_date, to_date)
    if group_by == "yearly":
        period_expr = "YEAR(gle.posting_date)"
    elif group_by == "quarterly":
        period_expr = "CONCAT(YEAR(gle.posting_date), '-Q', QUARTER(gle.posting_date))"
    else:
        period_expr = "DATE_FORMAT(gle.posting_date, '%%Y-%%m')"
    rows = frappe.db.sql(
        """
        SELECT """ + period_expr + """ AS period,
            COALESCE(SUM(gle.credit) - SUM(gle.debit), 0) AS amount
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND acc.root_type = 'Income'
          AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled = 0
        GROUP BY period ORDER BY period
        """,
        (company, from_date, to_date),
        as_dict=True,
    )
    by_period = {str(r["period"]): r["amount"] or 0 for r in rows}
    result = []
    for r in rows:
        p = str(r["period"])
        amt = r["amount"] or 0
        prev_p = _period_shift(p, group_by, -1)
        prev_m = _period_shift(p, group_by, -1)
        prev_q = _period_shift(p, group_by, -3)
        prev_y = _period_shift(p, group_by, -12)
        prev_amt = by_period.get(prev_p, 0) if prev_p else 0
        amt_m = by_period.get(prev_m, 0) if prev_m else 0
        amt_q = by_period.get(prev_q, 0) if prev_q else 0
        amt_y = by_period.get(prev_y, 0) if prev_y else 0
        result.append({
            "period": p,
            "amount": amt,
            "previous": prev_amt,
            "change": _chg(amt, prev_amt),
            "change_monthly": _chg(amt, amt_m),
            "change_quarterly": _chg(amt, amt_q),
            "change_yearly": _chg(amt, amt_y),
        })
    return result


@frappe.whitelist()
def get_purchases_summary(company, from_date, to_date, group_by="monthly"):
    """Purchases (Expense) by period with comparative columns."""
    from_date, to_date = _get_dates(company, from_date, to_date)
    if group_by == "yearly":
        period_expr = "YEAR(gle.posting_date)"
    elif group_by == "quarterly":
        period_expr = "CONCAT(YEAR(gle.posting_date), '-Q', QUARTER(gle.posting_date))"
    else:
        period_expr = "DATE_FORMAT(gle.posting_date, '%%Y-%%m')"
    rows = frappe.db.sql(
        """
        SELECT """ + period_expr + """ AS period,
            COALESCE(SUM(gle.debit) - SUM(gle.credit), 0) AS amount
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND acc.root_type = 'Expense'
          AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled = 0
        GROUP BY period ORDER BY period
        """,
        (company, from_date, to_date),
        as_dict=True,
    )
    by_period = {str(r["period"]): r["amount"] or 0 for r in rows}
    return [_summary_row(r, group_by, by_period) for r in rows]


def _summary_row(r, group_by, by_period):
    p = str(r["period"])
    amt = r["amount"] or 0
    prev_p = _period_shift(p, group_by, -1)
    prev_m = _period_shift(p, group_by, -1)
    prev_q = _period_shift(p, group_by, -3)
    prev_y = _period_shift(p, group_by, -12)
    prev_amt = by_period.get(prev_p, 0) if prev_p else 0
    amt_m = by_period.get(prev_m, 0) if prev_m else 0
    amt_q = by_period.get(prev_q, 0) if prev_q else 0
    amt_y = by_period.get(prev_y, 0) if prev_y else 0
    return {
        "period": p, "amount": amt, "previous": prev_amt,
        "change": _chg(amt, prev_amt),
        "change_monthly": _chg(amt, amt_m), "change_quarterly": _chg(amt, amt_q), "change_yearly": _chg(amt, amt_y),
    }


@frappe.whitelist()
def get_expenses_summary(company, from_date, to_date, group_by="monthly"):
    """Expenses by period: monthly, quarterly, or yearly."""
    return get_purchases_summary(company, from_date, to_date, group_by)


@frappe.whitelist()
def get_vertical_analysis(company, from_date, to_date, group_by="period"):
    """P&L vertical analysis: each line as % of revenue. group_by=monthly returns { months, rows } with % per month."""
    from_date, to_date = _get_dates(company, from_date, to_date)
    if group_by == "monthly":
        months_list = []
        row_structure = None
        values_by_row = []
        for month_start, month_end, month_label in _months_in_range(from_date, to_date):
            pl = get_profit_loss(company, month_start, month_end)
            total_revenue = 0
            for r in pl:
                if r.get("row_type") == "subtotal" and r.get("account") == "Total Sales":
                    total_revenue = r.get("current") or 0
                    break
            if total_revenue <= 0:
                total_revenue = 1
            months_list.append(month_label)
            if row_structure is None:
                row_structure = [
                    {"account": r.get("account"), "row_type": r.get("row_type", "account"), "indent": r.get("indent") or 0}
                    for r in pl
                ]
            for i, r in enumerate(pl):
                cur = r.get("current") or 0
                pct = round(cur / total_revenue * 100, 1) if total_revenue else 0
                if i >= len(values_by_row):
                    values_by_row.append([])
                values_by_row[i].append(pct)
        if not row_structure:
            return {"months": [], "rows": []}
        for i, row in enumerate(row_structure):
            row["values"] = values_by_row[i] if i < len(values_by_row) else []
        return {"months": months_list, "rows": row_structure}
    pl_rows = get_profit_loss(company, from_date, to_date)
    if not pl_rows:
        return []
    total_revenue = 0
    for r in pl_rows:
        if r.get("row_type") == "subtotal" and r.get("account") == "Total Sales":
            total_revenue = r.get("current") or 0
            break
    if total_revenue <= 0:
        total_revenue = 1
    out = []
    for r in pl_rows:
        cur = r.get("current") or 0
        pct = round(cur / total_revenue * 100, 1) if total_revenue else 0
        out.append({
            "account": r.get("account"),
            "amount": cur,
            "percent_of_revenue": pct,
            "row_type": r.get("row_type", "account"),
        })
    return out


@frappe.whitelist()
def get_horizontal_analysis(company, from_date, to_date, group_by="period"):
    """P&L horizontal analysis: period-over-period % change. group_by=monthly returns { months, rows } with change % per month."""
    from_date, to_date = _get_dates(company, from_date, to_date)
    if group_by == "monthly":
        months_list = []
        row_structure = None
        values_by_row = []
        for month_start, month_end, month_label in _months_in_range(from_date, to_date):
            pl = get_profit_loss(company, month_start, month_end)
            months_list.append(month_label)
            if row_structure is None:
                row_structure = [
                    {"account": r.get("account"), "row_type": r.get("row_type", "account"), "indent": r.get("indent") or 0}
                    for r in pl
                ]
            for i, r in enumerate(pl):
                chg = r.get("change", 0)
                if i >= len(values_by_row):
                    values_by_row.append([])
                values_by_row[i].append(round(chg, 1) if chg is not None else 0)
        if not row_structure:
            return {"months": [], "rows": []}
        for i, row in enumerate(row_structure):
            row["values"] = values_by_row[i] if i < len(values_by_row) else []
        return {"months": months_list, "rows": row_structure}
    pl_rows = get_profit_loss(company, from_date, to_date)
    return [
        {
            "account": r.get("account"),
            "current": r.get("current") or 0,
            "previous": r.get("previous") or 0,
            "change_percent": r.get("change", 0),
            "row_type": r.get("row_type", "account"),
        }
        for r in (pl_rows or [])
    ]


@frappe.whitelist()
def get_ratio_analysis(company, from_date, to_date):
    """Financial ratios: Liquidity, Profitability, Performance/Solvency, Efficiency (1 decimal for %)."""
    from_date, to_date = _get_dates(company, from_date, to_date)
    ta_row = frappe.db.sql("""SELECT COALESCE(SUM(gle.debit - gle.credit), 0) FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND gle.posting_date <= %s AND gle.is_cancelled = 0 AND acc.root_type = 'Asset'""",
        (company, to_date)) or [(0,)]
    tl_row = frappe.db.sql("""SELECT COALESCE(SUM(gle.credit - gle.debit), 0) FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND gle.posting_date <= %s AND gle.is_cancelled = 0 AND acc.root_type = 'Liability'""",
        (company, to_date)) or [(0,)]
    equity_row = frappe.db.sql("""SELECT COALESCE(SUM(gle.credit - gle.debit), 0) FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND gle.posting_date <= %s AND gle.is_cancelled = 0 AND acc.root_type = 'Equity'""",
        (company, to_date)) or [(0,)]
    current_asset_row = frappe.db.sql("""SELECT COALESCE(SUM(gle.debit - gle.credit), 0) FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND gle.posting_date <= %s AND gle.is_cancelled = 0
        AND acc.root_type = 'Asset' AND acc.account_type IN ('Bank', 'Cash', 'Receivable', 'Stock', 'Stock Received But Not Billed')""",
        (company, to_date)) or [(0,)]
    current_liab_row = frappe.db.sql("""SELECT COALESCE(SUM(gle.credit - gle.debit), 0) FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND gle.posting_date <= %s AND gle.is_cancelled = 0 AND acc.root_type = 'Liability'""",
        (company, to_date)) or [(0,)]
    rev_row = frappe.db.sql("""SELECT COALESCE(SUM(gle.credit) - SUM(gle.debit), 0) FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND acc.root_type = 'Income' AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled = 0""",
        (company, from_date, to_date)) or [(0,)]
    exp_row = frappe.db.sql("""SELECT COALESCE(SUM(gle.debit) - SUM(gle.credit), 0) FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND acc.root_type = 'Expense' AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled = 0""",
        (company, from_date, to_date)) or [(0,)]

    ta = float(ta_row[0][0] or 0)
    tl = float(tl_row[0][0] or 0)
    equity = float(equity_row[0][0] or 0)
    ca = float(current_asset_row[0][0] or 0)
    cl = float(current_liab_row[0][0] or 0)
    rev = float(rev_row[0][0] or 0)
    exp = float(exp_row[0][0] or 0)
    profit = rev - exp
    operating_profit = rev - exp

    ratios = []
    # Liquidity
    ratios.append({"category": "Liquidity", "name": "Current Ratio", "value": round(ta / cl, 2) if cl else 0, "description": "Total Assets / Current Liabilities"})
    ratios.append({"category": "Liquidity", "name": "Quick Ratio", "value": round(ca / cl, 2) if cl else 0, "description": "Current Assets / Current Liabilities"})
    # Profitability (1 decimal for %)
    ratios.append({"category": "Profitability", "name": "Profit Margin %", "value": round(profit / rev * 100, 1) if rev else 0, "description": "Net Profit / Revenue"})
    ratios.append({"category": "Profitability", "name": "Operating Margin %", "value": round(operating_profit / rev * 100, 1) if rev else 0, "description": "Operating Profit / Revenue"})
    ratios.append({"category": "Profitability", "name": "ROA %", "value": round(profit / ta * 100, 1) if ta else 0, "description": "Net Profit / Total Assets"})
    ratios.append({"category": "Profitability", "name": "ROE %", "value": round(profit / equity * 100, 1) if equity else 0, "description": "Net Profit / Equity"})
    ratios.append({"category": "Profitability", "name": "Net Profit", "value": round(profit, 0), "description": "Revenue - Expenses"})
    # Solvency / Performance
    ratios.append({"category": "Solvency", "name": "Debt Ratio", "value": round(tl / ta, 2) if ta else 0, "description": "Total Liabilities / Total Assets"})
    ratios.append({"category": "Solvency", "name": "Equity Ratio", "value": round(equity / ta, 2) if ta else 0, "description": "Equity / Total Assets"})
    ratios.append({"category": "Solvency", "name": "Debt to Equity", "value": round(tl / equity, 2) if equity else 0, "description": "Total Liabilities / Equity"})
    # Efficiency
    ratios.append({"category": "Efficiency", "name": "Asset Turnover", "value": round(rev / ta, 2) if ta else 0, "description": "Revenue / Total Assets"})
    return ratios
