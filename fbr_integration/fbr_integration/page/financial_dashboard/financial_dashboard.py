from datetime import timedelta

import frappe
from frappe.utils import add_to_date, cint, get_first_day, get_last_day, getdate, nowdate


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

	currency = frappe.get_cached_value("Company", company, "default_currency") or frappe.db.get_default(
		"currency"
	)

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
            """
		+ period_expr
		+ """ AS period,
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
	groups = frappe.db.sql(
		"""
		SELECT name, account_name, lft, rgt
		FROM `tabAccount`
		WHERE company = %s
		  AND root_type = 'Expense'
		  AND is_group = 1
		  AND LOWER(account_name) IN ('direct expenses', 'indirect expenses')
		ORDER BY lft
		""",
		(company,),
		as_dict=True,
	)

	rows = []
	for group in groups:
		row = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(gle.debit) - SUM(gle.credit), 0) AS value
			FROM `tabGL Entry` gle
			INNER JOIN `tabAccount` acc ON gle.account = acc.name
			WHERE gle.company = %s
			  AND acc.root_type = 'Expense'
			  AND acc.is_group = 0
			  AND acc.lft > %s
			  AND acc.rgt < %s
			  AND gle.posting_date BETWEEN %s AND %s
			  AND gle.is_cancelled = 0
			""",
			(company, group.lft, group.rgt, from_date, to_date),
			as_dict=True,
		)[0]
		value = row.value or 0
		if value > 0:
			rows.append({"label": group.account_name, "value": value})

	rows.sort(key=lambda row: row["value"], reverse=True)
	labels = [r["label"] for r in rows]
	values = [round(r["value"] or 0, 0) for r in rows]
	return {"labels": labels, "values": values}


@frappe.whitelist()
def get_expense_hierarchy(company, from_date, to_date):
	"""Expense hierarchy from Chart of Accounts with period values."""
	from_date, to_date = _get_dates(company, from_date, to_date)
	accounts = frappe.db.sql(
		"""
		SELECT name, account_name, parent_account, is_group, lft, rgt
		FROM `tabAccount`
		WHERE company = %s
		  AND root_type = 'Expense'
		  AND disabled = 0
		ORDER BY lft
		""",
		(company,),
		as_dict=True,
	)
	values = frappe.db.sql(
		"""
		SELECT acc.name, COALESCE(SUM(gle.debit) - SUM(gle.credit), 0) AS value
		FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` acc ON gle.account = acc.name
		WHERE gle.company = %s
		  AND acc.root_type = 'Expense'
		  AND acc.is_group = 0
		  AND gle.posting_date BETWEEN %s AND %s
		  AND gle.is_cancelled = 0
		GROUP BY acc.name
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	value_map = {row.name: row.value or 0 for row in values}
	account_map = {account.name: account for account in accounts}
	for account in accounts:
		account.value = value_map.get(account.name, 0)

	for account in reversed(accounts):
		parent = account_map.get(account.parent_account)
		if parent:
			parent.value = (parent.get("value") or 0) + (account.get("value") or 0)

	root = next((account for account in accounts if not account.parent_account), None)
	rows = []
	for account in accounts:
		if root and account.name == root.name:
			continue
		value = account.get("value") or 0
		if value <= 0:
			continue
		indent = 0
		parent = account_map.get(account.parent_account)
		while parent and (not root or parent.name != root.name):
			indent += 1
			parent = account_map.get(parent.parent_account)
		rows.append(
			{
				"account": account.account_name,
				"value": round(value, 0),
				"is_group": account.is_group,
				"indent": indent,
			}
		)
	return rows


@frappe.whitelist()
def get_warehouses(company):
	if not company:
		frappe.throw("Company is required")

	return frappe.get_all(
		"Warehouse",
		filters={"company": company, "is_group": 0, "disabled": 0},
		pluck="name",
		order_by="name",
	)


@frappe.whitelist()
def get_stock_by_item_group(company, warehouse=None):
	if not company:
		frappe.throw("Company is required")

	conditions = ["wh.company = %s", "bin.actual_qty <> 0"]
	params = [company]
	if warehouse:
		conditions.append("bin.warehouse = %s")
		params.append(warehouse)

	return frappe.db.sql(
		f"""
		SELECT
			COALESCE(NULLIF(item.item_group, ''), 'No Item Group') AS item_group,
			SUM(bin.actual_qty) AS closing_qty,
			SUM(bin.stock_value) AS closing_value
		FROM `tabBin` bin
		INNER JOIN `tabItem` item ON bin.item_code = item.name
		INNER JOIN `tabWarehouse` wh ON bin.warehouse = wh.name
		WHERE {" AND ".join(conditions)}
		GROUP BY item.item_group
		HAVING closing_qty <> 0 OR closing_value <> 0
		ORDER BY closing_value DESC
		LIMIT 30
		""",
		params,
		as_dict=True,
	)


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
        SELECT COALESCE(SUM(sii.base_net_amount), 0) AS total
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON sii.parent = si.name
        WHERE si.company = %s
          AND si.docstatus = 1
          AND si.posting_date BETWEEN %s AND %s
        """,
		(company, from_date, to_date),
		as_dict=True,
	)
	total = (total_row[0]["total"] or 0) if total_row else 0
	rows = frappe.db.sql(
		"""
        SELECT COALESCE(NULLIF(sii.item_group, ''), item.item_group, 'No Item Group') AS item_group,
               COALESCE(SUM(sii.base_net_amount), 0) AS amount
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON sii.parent = si.name
        LEFT JOIN `tabItem` item ON sii.item_code = item.name
        WHERE si.company = %s
          AND si.docstatus = 1
          AND si.posting_date BETWEEN %s AND %s
        GROUP BY item_group
        HAVING amount <> 0
        ORDER BY amount DESC
        LIMIT 10
        """,
		(company, from_date, to_date),
		as_dict=True,
	)
	result = []
	for r in rows:
		pct = round(r["amount"] / total * 100, 1) if total else 0
		result.append({"item_group": r["item_group"], "amount": r["amount"], "percent": pct})
	return result


@frappe.whitelist()
def get_customer_group_sales(company, from_date, to_date):
	from_date, to_date = _get_dates(company, from_date, to_date)
	customer_group_expr = (
		"COALESCE(NULLIF(si.customer_group, ''), NULLIF(customer.customer_group, ''), 'No Customer Group')"
		if frappe.db.has_column("Sales Invoice", "customer_group")
		else "COALESCE(NULLIF(customer.customer_group, ''), 'No Customer Group')"
	)
	return frappe.db.sql(
		f"""
		SELECT
			{customer_group_expr} AS customer_group,
			COALESCE(SUM(si.base_net_total), 0) AS amount,
			COUNT(si.name) AS invoice_count
		FROM `tabSales Invoice` si
		LEFT JOIN `tabCustomer` customer ON si.customer = customer.name
		WHERE si.company = %s
		  AND si.docstatus = 1
		  AND si.posting_date BETWEEN %s AND %s
		GROUP BY customer_group
		HAVING amount <> 0
		ORDER BY amount DESC
		LIMIT 15
		""",
		(company, from_date, to_date),
		as_dict=True,
	)


@frappe.whitelist()
def get_supplier_group_purchases(company, from_date, to_date):
	from_date, to_date = _get_dates(company, from_date, to_date)
	supplier_group_expr = (
		"COALESCE(NULLIF(pi.supplier_group, ''), NULLIF(supplier.supplier_group, ''), 'No Supplier Group')"
		if frappe.db.has_column("Purchase Invoice", "supplier_group")
		else "COALESCE(NULLIF(supplier.supplier_group, ''), 'No Supplier Group')"
	)
	return frappe.db.sql(
		f"""
		SELECT
			{supplier_group_expr} AS supplier_group,
			COALESCE(SUM(pi.base_net_total), 0) AS amount,
			COUNT(pi.name) AS invoice_count
		FROM `tabPurchase Invoice` pi
		LEFT JOIN `tabSupplier` supplier ON pi.supplier = supplier.name
		WHERE pi.company = %s
		  AND pi.docstatus = 1
		  AND pi.posting_date BETWEEN %s AND %s
		GROUP BY supplier_group
		HAVING amount <> 0
		ORDER BY amount DESC
		LIMIT 15
		""",
		(company, from_date, to_date),
		as_dict=True,
	)


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


def _rollup_balances(
	accounts, gl_cur, gl_prev, root_type, gl_prev_month=None, gl_prev_quarter=None, gl_prev_year=None
):
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
		out.append(
			{
				"account": a["account_name"],
				"current": cur,
				"previous": prev,
				"change": _chg(cur, prev),
				"change_monthly": _chg(cur, prev_m),
				"change_quarterly": _chg(cur, prev_q),
				"change_yearly": _chg(cur, prev_y),
				"row_type": row_type_account,
				"indent": indent,
			}
		)
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
	_rollup_balances(
		expense_accounts, gl_cur, gl_prev, "Expense", gl_prev_month, gl_prev_quarter, gl_prev_year
	)

	def _row(account, cur, prev, prev_m, prev_q, prev_y, row_type):
		return {
			"account": account,
			"current": cur,
			"previous": prev,
			"change": _chg(cur, prev),
			"change_monthly": _chg(cur, prev_m),
			"change_quarterly": _chg(cur, prev_q),
			"change_yearly": _chg(cur, prev_y),
			"row_type": row_type,
		}

	out = []
	# ---------- 1. Sales ----------
	out.append(_row("Sales", 0, 0, 0, 0, 0, "section_header"))
	total_sales_cur, total_sales_prev, total_sales_m, total_sales_q, total_sales_y = 0.0, 0.0, 0.0, 0.0, 0.0
	income_root = next((a["name"] for a in income_accounts if not a.get("parent_account")), None)
	if income_root:
		total_sales_cur, total_sales_prev, total_sales_m, total_sales_q, total_sales_y = _tree_total(
			income_accounts, income_root
		)
		_append_tree_rows(out, income_accounts, income_root, 1)
	out.append(
		_row(
			"Total Sales",
			total_sales_cur,
			total_sales_prev,
			total_sales_m,
			total_sales_q,
			total_sales_y,
			"subtotal",
		)
	)

	# ---------- 2. Direct Expenses ----------
	out.append(_row("Direct Expenses", 0, 0, 0, 0, 0, "section_header"))
	expense_root = next((a["name"] for a in expense_accounts if not a.get("parent_account")), None)
	direct_group = indirect_group = None
	expense_children = (
		[a for a in expense_accounts if a.get("parent_account") == expense_root] if expense_root else []
	)
	expense_children.sort(key=lambda x: x.get("lft") or 0)
	for a in expense_children:
		an = (a.get("account_name") or "").lower()
		if "direct" in an and "indirect" not in an:
			direct_group = a["name"]
		elif "indirect" in an:
			indirect_group = a["name"]
	total_direct_cur, total_direct_prev, total_direct_m, total_direct_q, total_direct_y = (
		0.0,
		0.0,
		0.0,
		0.0,
		0.0,
	)
	if direct_group:
		total_direct_cur, total_direct_prev, total_direct_m, total_direct_q, total_direct_y = _tree_total(
			expense_accounts, direct_group
		)
		_append_tree_rows(out, expense_accounts, direct_group, 1)
	out.append(
		_row(
			"Total Direct Expenses",
			total_direct_cur,
			total_direct_prev,
			total_direct_m,
			total_direct_q,
			total_direct_y,
			"subtotal",
		)
	)

	# ---------- 3. Gross Profit ----------
	gp_cur = total_sales_cur - total_direct_cur
	gp_prev = total_sales_prev - total_direct_prev
	gp_m = total_sales_m - total_direct_m
	gp_q = total_sales_q - total_direct_q
	gp_y = total_sales_y - total_direct_y
	out.append(_row("Gross Profit", gp_cur, gp_prev, gp_m, gp_q, gp_y, "subtotal"))

	# ---------- 4. Indirect Expenses ----------
	out.append(_row("Indirect Expenses", 0, 0, 0, 0, 0, "section_header"))
	total_indirect_cur, total_indirect_prev, total_indirect_m, total_indirect_q, total_indirect_y = (
		0.0,
		0.0,
		0.0,
		0.0,
		0.0,
	)
	if indirect_group:
		total_indirect_cur, total_indirect_prev, total_indirect_m, total_indirect_q, total_indirect_y = (
			_tree_total(expense_accounts, indirect_group)
		)
		_append_tree_rows(out, expense_accounts, indirect_group, 1)
	out.append(
		_row(
			"Total Indirect Expenses",
			total_indirect_cur,
			total_indirect_prev,
			total_indirect_m,
			total_indirect_q,
			total_indirect_y,
			"subtotal",
		)
	)

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
		out.append(
			{
				"account": section_label,
				"current": 0,
				"previous": 0,
				"change": 0,
				"change_monthly": 0,
				"change_quarterly": 0,
				"change_yearly": 0,
				"row_type": "section_header",
			}
		)
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
			out.append(
				{
					"account": name,
					"current": cur_val,
					"previous": prev_val,
					"change": _chg(cur_val, prev_val),
					"change_monthly": _chg(cur_val, val_m),
					"change_quarterly": _chg(cur_val, val_q),
					"change_yearly": _chg(cur_val, val_y),
					"row_type": "account",
					"indent": 1,
				}
			)
		out.append(
			{
				"account": "Total " + section_label,
				"current": total_cur,
				"previous": total_prev,
				"change": _chg(total_cur, total_prev),
				"change_monthly": _chg(total_cur, total_m),
				"change_quarterly": _chg(total_cur, total_q),
				"change_yearly": _chg(total_cur, total_y),
				"row_type": "subtotal",
			}
		)
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
			label = f"{d.year}-{d.month:02d}"
		yield (d, month_end, label)
		d = getdate(add_to_date(d, months=1))


@frappe.whitelist()
def get_profit_loss_monthly(company, from_date, to_date):
	"""P&L with months as columns: Jan, Feb, Mar, ... (one column per month in range)."""
	from_date, to_date = _get_dates(company, from_date, to_date)
	months_list = []
	row_structure = None
	values_by_row = []

	for _month_start, month_end, month_label in _months_in_range(from_date, to_date):
		pl = get_profit_loss(company, _month_start, month_end)
		months_list.append(month_label)
		if row_structure is None:
			row_structure = [
				{
					"account": r["account"],
					"row_type": r.get("row_type", "account"),
					"indent": r.get("indent") or 0,
				}
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

	for _month_start, month_end, month_label in _months_in_range(from_date, to_date):
		# Balance sheet as of month end
		bs = get_balance_sheet(company, month_end, month_end)
		months_list.append(month_label)
		if row_structure is None:
			row_structure = [
				{
					"account": r["account"],
					"row_type": r.get("row_type", "account"),
					"indent": r.get("indent") or 0,
				}
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
		out.append(
			{
				"activity": r["account_name"],
				"amount": round(r["amount"] or 0, 0),
				"row_type": "account",
				"indent": 2,
			}
		)
	out.append(
		{"activity": "Total Income", "amount": round(total_income, 0), "row_type": "subtotal", "indent": 1}
	)
	out.append({"activity": "Expenses", "amount": 0, "row_type": "section_header", "indent": 1})
	for r in expense_rows[:15]:
		out.append(
			{
				"activity": r["account_name"],
				"amount": round(-(r["amount"] or 0), 0),
				"row_type": "account",
				"indent": 2,
			}
		)
	out.append(
		{
			"activity": "Total Expenses",
			"amount": round(-total_expense, 0),
			"row_type": "subtotal",
			"indent": 1,
		}
	)
	out.append({"activity": "Net Income (Operating)", "amount": round(operating, 0), "row_type": "subtotal"})
	out.append(
		{"activity": "Total Operating Activities", "amount": round(operating, 0), "row_type": "subtotal"}
	)
	# Investing: Fixed Asset / Capex movement if needed; placeholder
	out.append({"activity": "Investing Activities", "amount": 0, "row_type": "section_header"})
	investing = _cash_flow_investing(company, from_date, to_date)
	out.append(
		{"activity": "Total Investing Activities", "amount": round(investing, 0), "row_type": "subtotal"}
	)
	out.append({"activity": "Financing Activities", "amount": 0, "row_type": "section_header"})
	financing = _cash_flow_financing(company, from_date, to_date)
	out.append(
		{"activity": "Total Financing Activities", "amount": round(financing, 0), "row_type": "subtotal"}
	)
	out.append(
		{
			"activity": "Net Change in Cash",
			"amount": round(operating + investing + financing, 0),
			"row_type": "total",
		}
	)
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
	return [
		{
			"account": r["account_name"],
			"debit": r["debit"] or 0,
			"credit": r["credit"] or 0,
			"balance": r["balance"] or 0,
		}
		for r in rows
	]


# ---------- Aging, Sales, Purchases, Expenses, Vertical/Horizontal/Ratio ----------


@frappe.whitelist()
def get_aging_receivables(company, report_date=None):
	"""Customer receivable closing balances from GL."""
	as_on = getdate(report_date or frappe.utils.getdate())
	if not company:
		frappe.throw("Company is required")

	return frappe.db.sql(
		"""
		SELECT
			gle.party AS customer,
			COALESCE(c.customer_name, gle.party) AS customer_name,
			SUM(gle.debit) - SUM(gle.credit) AS outstanding,
			MIN(DATEDIFF(%s, gle.posting_date)) AS age
		FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` acc ON gle.account = acc.name
		LEFT JOIN `tabCustomer` c ON gle.party = c.name
		WHERE gle.company = %s
		  AND gle.party_type = 'Customer'
		  AND gle.party IS NOT NULL
		  AND acc.account_type = 'Receivable'
		  AND gle.posting_date <= %s
		  AND gle.is_cancelled = 0
		GROUP BY gle.party, c.customer_name
		HAVING outstanding > 0
		ORDER BY outstanding DESC
		LIMIT 10
		""",
		(as_on, company, as_on),
		as_dict=True,
	)


@frappe.whitelist()
def get_aging_payables(company, report_date=None):
	"""Supplier payable closing balances from GL."""
	as_on = getdate(report_date or frappe.utils.getdate())
	if not company:
		frappe.throw("Company is required")

	return frappe.db.sql(
		"""
		SELECT
			gle.party AS supplier,
			COALESCE(s.supplier_name, gle.party) AS supplier_name,
			SUM(gle.credit) - SUM(gle.debit) AS outstanding,
			MIN(DATEDIFF(%s, gle.posting_date)) AS age
		FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` acc ON gle.account = acc.name
		LEFT JOIN `tabSupplier` s ON gle.party = s.name
		WHERE gle.company = %s
		  AND gle.party_type = 'Supplier'
		  AND gle.party IS NOT NULL
		  AND acc.account_type = 'Payable'
		  AND gle.posting_date <= %s
		  AND gle.is_cancelled = 0
		GROUP BY gle.party, s.supplier_name
		HAVING outstanding > 0
		ORDER BY outstanding DESC
		LIMIT 10
		""",
		(as_on, company, as_on),
		as_dict=True,
	)


@frappe.whitelist()
def get_aging_receivables_summary(company, report_date=None):
	"""Receivable age buckets for standalone calls."""
	as_on = getdate(report_date or frappe.utils.getdate())
	if not company:
		frappe.throw("Company is required")
	rows = frappe.db.sql(
		"""
		SELECT
			CASE
				WHEN DATEDIFF(%s, COALESCE(due_date, posting_date)) <= 30 THEN '0-30'
				WHEN DATEDIFF(%s, COALESCE(due_date, posting_date)) <= 60 THEN '31-60'
				WHEN DATEDIFF(%s, COALESCE(due_date, posting_date)) <= 90 THEN '61-90'
				ELSE '90+'
			END AS bucket,
			SUM(outstanding_amount) AS amount
		FROM `tabSales Invoice`
		WHERE company = %s
		  AND docstatus = 1
		  AND posting_date <= %s
		  AND outstanding_amount > 0
		GROUP BY bucket
		""",
		(as_on, as_on, as_on, company, as_on),
		as_dict=True,
	)
	bucket_map = {r.bucket: r.amount or 0 for r in rows}
	return {
		"total": sum(bucket_map.values()),
		"buckets": [
			{"range": "0-30", "amount": bucket_map.get("0-30", 0), "label": "0-30 days"},
			{"range": "31-60", "amount": bucket_map.get("31-60", 0), "label": "31-60 days"},
			{"range": "61-90", "amount": bucket_map.get("61-90", 0), "label": "61-90 days"},
			{"range": "90+", "amount": bucket_map.get("90+", 0), "label": "90+ days"},
		],
	}


@frappe.whitelist()
def get_aging_payables_summary(company, report_date=None):
	"""Payable age buckets for standalone calls."""
	as_on = getdate(report_date or frappe.utils.getdate())
	if not company:
		frappe.throw("Company is required")
	rows = frappe.db.sql(
		"""
		SELECT
			CASE
				WHEN DATEDIFF(%s, COALESCE(due_date, posting_date)) <= 30 THEN '0-30'
				WHEN DATEDIFF(%s, COALESCE(due_date, posting_date)) <= 60 THEN '31-60'
				WHEN DATEDIFF(%s, COALESCE(due_date, posting_date)) <= 90 THEN '61-90'
				ELSE '90+'
			END AS bucket,
			SUM(outstanding_amount) AS amount
		FROM `tabPurchase Invoice`
		WHERE company = %s
		  AND docstatus = 1
		  AND posting_date <= %s
		  AND outstanding_amount > 0
		GROUP BY bucket
		""",
		(as_on, as_on, as_on, company, as_on),
		as_dict=True,
	)
	bucket_map = {r.bucket: r.amount or 0 for r in rows}
	return {
		"total": sum(bucket_map.values()),
		"buckets": [
			{"range": "0-30", "amount": bucket_map.get("0-30", 0), "label": "0-30 days"},
			{"range": "31-60", "amount": bucket_map.get("31-60", 0), "label": "31-60 days"},
			{"range": "61-90", "amount": bucket_map.get("61-90", 0), "label": "61-90 days"},
			{"range": "90+", "amount": bucket_map.get("90+", 0), "label": "90+ days"},
		],
	}


def _period_shift(period_str, group_by, months_delta):
	"""Return period key for period_str shifted by months_delta (e.g. -1, -3, -12)."""
	try:
		if group_by == "yearly":
			y = int(period_str)
			d = getdate(f"{y}-06-01")
			d2 = add_to_date(d, months=months_delta)
			return str(d2.year)
		if group_by == "quarterly":
			# e.g. 2025-Q1 -> 2025-01-01, shift, then format back
			parts = period_str.split("-Q")
			y, q = int(parts[0]), int(parts[1])
			d = getdate(f"{y}-{((q - 1) * 3 + 1):02d}-01")
			d2 = add_to_date(d, months=months_delta)
			q2 = (d2.month - 1) // 3 + 1
			return f"{d2.year}-Q{q2}"
		# monthly YYYY-MM
		y, m = int(period_str[:4]), int(period_str[5:7])
		d = getdate(f"{y}-{m:02d}-01")
		d2 = add_to_date(d, months=months_delta)
		return f"{d2.year}-{d2.month:02d}"
	except Exception:
		return None


def _period_expr(date_field, group_by):
	if group_by == "yearly":
		return f"YEAR({date_field})"
	if group_by == "quarterly":
		return f"CONCAT(YEAR({date_field}), '-Q', QUARTER({date_field}))"
	return f"DATE_FORMAT({date_field}, '%%Y-%%m')"


@frappe.whitelist()
def get_sales_summary(company, from_date, to_date, group_by="monthly"):
	"""Sales invoices by period with exclusive, tax, inclusive and change columns."""
	from_date, to_date = _get_dates(company, from_date, to_date)
	return _invoice_period_summary(company, from_date, to_date, group_by, "Sales Invoice", "base_net_total")


@frappe.whitelist()
def get_sales_return_invoices(company, from_date, to_date):
	from_date, to_date = _get_dates(company, from_date, to_date)
	return frappe.db.sql(
		"""
		SELECT
			si.name,
			si.posting_date,
			si.customer_name,
			COALESCE(si.return_against, '') AS return_against,
			COALESCE(
				NULLIF(si.custom_fbr_source_invoice_no, ''),
				NULLIF(source.custom_fbr_invoice_no, ''),
				''
			) AS custom_fbr_source_invoice_no,
			COALESCE(si.custom_fbr_invoice_no, '') AS custom_fbr_invoice_no,
			COALESCE(si.base_net_total, 0) AS exclusive,
			COALESCE(si.base_total_taxes_and_charges, 0) AS tax,
			COALESCE(si.base_grand_total, 0) AS inclusive
		FROM `tabSales Invoice` si
		LEFT JOIN `tabSales Invoice` source ON source.name = si.return_against
		WHERE si.company = %s
		  AND si.docstatus = 1
		  AND si.is_return = 1
		  AND si.posting_date BETWEEN %s AND %s
		ORDER BY si.posting_date DESC, si.modified DESC
		LIMIT 50
		""",
		(company, from_date, to_date),
		as_dict=True,
	)


@frappe.whitelist()
def get_purchases_summary(company, from_date, to_date, group_by="monthly"):
	"""Purchase invoices by period with exclusive, tax, inclusive and change columns."""
	from_date, to_date = _get_dates(company, from_date, to_date)
	return _invoice_period_summary(
		company, from_date, to_date, group_by, "Purchase Invoice", "base_net_total"
	)


def _invoice_period_summary(company, from_date, to_date, group_by, doctype, exclusive_field):
	period_expr = _period_expr("posting_date", group_by)
	rows = frappe.db.sql(
		f"""
		SELECT {period_expr} AS period,
			COALESCE(SUM({exclusive_field}), 0) AS exclusive,
			COALESCE(SUM(base_total_taxes_and_charges), 0) AS tax,
			COALESCE(SUM(base_grand_total), 0) AS inclusive
		FROM `tab{doctype}`
		WHERE company = %s
		  AND docstatus = 1
		  AND posting_date BETWEEN %s AND %s
		GROUP BY period
		ORDER BY period
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	by_period = {str(row.period): row.inclusive or 0 for row in rows}
	result = []
	for row in rows:
		period = str(row.period)
		inclusive = row.inclusive or 0
		prev_period = _period_shift(period, group_by, -1)
		prev_inclusive = by_period.get(prev_period, 0) if prev_period else 0
		result.append(
			{
				"period": period,
				"exclusive": round(row.exclusive or 0, 0),
				"tax": round(row.tax or 0, 0),
				"inclusive": round(inclusive, 0),
				"amount": round(inclusive, 0),
				"previous": round(prev_inclusive, 0),
				"change": _chg(inclusive, prev_inclusive),
			}
		)
	return result


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
		"period": p,
		"amount": amt,
		"previous": prev_amt,
		"change": _chg(amt, prev_amt),
		"change_monthly": _chg(amt, amt_m),
		"change_quarterly": _chg(amt, amt_q),
		"change_yearly": _chg(amt, amt_y),
	}


@frappe.whitelist()
def get_expenses_summary(company, from_date, to_date, group_by="monthly"):
	"""Expenses by period: monthly, quarterly, or yearly."""
	return get_purchases_summary(company, from_date, to_date, group_by)


def _invoice_tax_rows(company, from_date, to_date, parent_doctype, tax_doctype):
	parent_table = f"`tab{parent_doctype}`"
	tax_table = f"`tab{tax_doctype}`"
	return frappe.db.sql(
		f"""
		SELECT
			COALESCE(NULLIF(tax.account_head, ''), 'No Tax Account') AS account_head,
			COALESCE(NULLIF(tax.description, ''), NULLIF(tax.account_head, ''), 'No Description') AS description,
			COALESCE(tax.rate, 0) AS rate,
			COALESCE(SUM(tax.base_tax_amount_after_discount_amount), 0) AS tax_amount,
			COUNT(DISTINCT parent.name) AS invoice_count
		FROM {tax_table} tax
		INNER JOIN {parent_table} parent ON tax.parent = parent.name
		WHERE parent.company = %s
		  AND parent.docstatus = 1
		  AND parent.posting_date BETWEEN %s AND %s
		GROUP BY account_head, description, rate
		HAVING tax_amount <> 0
		ORDER BY ABS(tax_amount) DESC
		""",
		(company, from_date, to_date),
		as_dict=True,
	)


@frappe.whitelist()
def get_sales_tax_summary(company, from_date, to_date):
	from_date, to_date = _get_dates(company, from_date, to_date)
	return _invoice_tax_rows(company, from_date, to_date, "Sales Invoice", "Sales Taxes and Charges")


@frappe.whitelist()
def get_purchase_tax_summary(company, from_date, to_date):
	from_date, to_date = _get_dates(company, from_date, to_date)
	return _invoice_tax_rows(company, from_date, to_date, "Purchase Invoice", "Purchase Taxes and Charges")


@frappe.whitelist()
def get_tax_period_summary(company, from_date, to_date, group_by="monthly"):
	from_date, to_date = _get_dates(company, from_date, to_date)
	sales_period_expr = _period_expr("si.posting_date", group_by)
	purchase_period_expr = _period_expr("pi.posting_date", group_by)
	sales_rows = frappe.db.sql(
		f"""
		SELECT {sales_period_expr} AS period,
			COALESCE(SUM(stc.base_tax_amount_after_discount_amount), 0) AS amount
		FROM `tabSales Taxes and Charges` stc
		INNER JOIN `tabSales Invoice` si ON stc.parent = si.name
		WHERE si.company = %s
		  AND si.docstatus = 1
		  AND si.posting_date BETWEEN %s AND %s
		GROUP BY period
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	purchase_rows = frappe.db.sql(
		f"""
		SELECT {purchase_period_expr} AS period,
			COALESCE(SUM(ptc.base_tax_amount_after_discount_amount), 0) AS amount
		FROM `tabPurchase Taxes and Charges` ptc
		INNER JOIN `tabPurchase Invoice` pi ON ptc.parent = pi.name
		WHERE pi.company = %s
		  AND pi.docstatus = 1
		  AND pi.posting_date BETWEEN %s AND %s
		GROUP BY period
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	sales_by_period = {str(row.period): row.amount or 0 for row in sales_rows}
	purchases_by_period = {str(row.period): row.amount or 0 for row in purchase_rows}
	periods = sorted(set(sales_by_period) | set(purchases_by_period))
	return [
		{
			"period": period,
			"sales_tax": round(sales_by_period.get(period, 0), 0),
			"purchase_tax": round(purchases_by_period.get(period, 0), 0),
			"net_tax": round(sales_by_period.get(period, 0) - purchases_by_period.get(period, 0), 0),
		}
		for period in periods
	]


def _tax_account_tree(company, from_date, to_date, account_name, root_type):
	from_date, to_date = _get_dates(company, from_date, to_date)
	root = frappe.db.sql(
		"""
		SELECT name, account_name, lft, rgt
		FROM `tabAccount`
		WHERE company = %s
		  AND root_type = %s
		  AND LOWER(account_name) = LOWER(%s)
		  AND disabled = 0
		ORDER BY lft
		LIMIT 1
		""",
		(company, root_type, account_name),
		as_dict=True,
	)
	if not root:
		return []

	root = root[0]
	accounts = frappe.db.sql(
		"""
		SELECT name, account_name, parent_account, is_group, lft, rgt
		FROM `tabAccount`
		WHERE company = %s
		  AND lft >= %s
		  AND rgt <= %s
		  AND disabled = 0
		ORDER BY lft
		""",
		(company, root.lft, root.rgt),
		as_dict=True,
	)
	movements = frappe.db.sql(
		"""
		SELECT account,
			COALESCE(SUM(debit), 0) AS debit,
			COALESCE(SUM(credit), 0) AS credit
		FROM `tabGL Entry`
		WHERE company = %s
		  AND posting_date BETWEEN %s AND %s
		  AND is_cancelled = 0
		GROUP BY account
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	movement_map = {row.account: row for row in movements}
	account_map = {account.name: account for account in accounts}
	for account in accounts:
		movement = movement_map.get(account.name, {})
		account.debit = movement.get("debit") or 0
		account.credit = movement.get("credit") or 0

	for account in reversed(accounts):
		parent = account_map.get(account.parent_account)
		if parent:
			parent.debit = (parent.get("debit") or 0) + (account.get("debit") or 0)
			parent.credit = (parent.get("credit") or 0) + (account.get("credit") or 0)

	rows = []
	for account in accounts:
		debit = account.get("debit") or 0
		credit = account.get("credit") or 0
		if account.name != root.name and not debit and not credit and not account.is_group:
			continue
		indent = 0
		parent = account_map.get(account.parent_account)
		while parent and parent.name != root.name:
			indent += 1
			parent = account_map.get(parent.parent_account)
		balance = credit - debit if root_type == "Liability" else debit - credit
		rows.append(
			{
				"account": account.account_name,
				"debit": round(debit, 0),
				"credit": round(credit, 0),
				"balance": round(balance, 0),
				"is_group": account.is_group,
				"indent": indent,
			}
		)
	return rows


@frappe.whitelist()
def get_tax_account_reports(company, from_date, to_date):
	return {
		"withholding_income_taxes": _tax_account_tree(
			company, from_date, to_date, "Withholding Income Taxes", "Asset"
		),
		"duties_and_taxes": _tax_account_tree(company, from_date, to_date, "Duties and Taxes", "Liability"),
	}


@frappe.whitelist()
def get_vertical_analysis(company, from_date, to_date, group_by="period"):
	"""P&L vertical analysis: each line as % of revenue. group_by=monthly returns { months, rows } with % per month."""
	from_date, to_date = _get_dates(company, from_date, to_date)
	if group_by == "monthly":
		months_list = []
		row_structure = None
		values_by_row = []
		for _month_start, month_end, month_label in _months_in_range(from_date, to_date):
			pl = get_profit_loss(company, _month_start, month_end)
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
					{
						"account": r.get("account"),
						"row_type": r.get("row_type", "account"),
						"indent": r.get("indent") or 0,
					}
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
		out.append(
			{
				"account": r.get("account"),
				"amount": cur,
				"percent_of_revenue": pct,
				"row_type": r.get("row_type", "account"),
			}
		)
	return out


@frappe.whitelist()
def get_horizontal_analysis(company, from_date, to_date, group_by="period"):
	"""P&L horizontal analysis: period-over-period % change. group_by=monthly returns { months, rows } with change % per month."""
	from_date, to_date = _get_dates(company, from_date, to_date)
	if group_by == "monthly":
		months_list = []
		row_structure = None
		values_by_row = []
		for _month_start, month_end, month_label in _months_in_range(from_date, to_date):
			pl = get_profit_loss(company, _month_start, month_end)
			months_list.append(month_label)
			if row_structure is None:
				row_structure = [
					{
						"account": r.get("account"),
						"row_type": r.get("row_type", "account"),
						"indent": r.get("indent") or 0,
					}
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
	ta_row = frappe.db.sql(
		"""SELECT COALESCE(SUM(gle.debit - gle.credit), 0) FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND gle.posting_date <= %s AND gle.is_cancelled = 0 AND acc.root_type = 'Asset'""",
		(company, to_date),
	) or [(0,)]
	tl_row = frappe.db.sql(
		"""SELECT COALESCE(SUM(gle.credit - gle.debit), 0) FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND gle.posting_date <= %s AND gle.is_cancelled = 0 AND acc.root_type = 'Liability'""",
		(company, to_date),
	) or [(0,)]
	equity_row = frappe.db.sql(
		"""SELECT COALESCE(SUM(gle.credit - gle.debit), 0) FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND gle.posting_date <= %s AND gle.is_cancelled = 0 AND acc.root_type = 'Equity'""",
		(company, to_date),
	) or [(0,)]
	current_asset_row = frappe.db.sql(
		"""SELECT COALESCE(SUM(gle.debit - gle.credit), 0) FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND gle.posting_date <= %s AND gle.is_cancelled = 0
        AND acc.root_type = 'Asset' AND acc.account_type IN ('Bank', 'Cash', 'Receivable', 'Stock', 'Stock Received But Not Billed')""",
		(company, to_date),
	) or [(0,)]
	current_liab_row = frappe.db.sql(
		"""SELECT COALESCE(SUM(gle.credit - gle.debit), 0) FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND gle.posting_date <= %s AND gle.is_cancelled = 0 AND acc.root_type = 'Liability'""",
		(company, to_date),
	) or [(0,)]
	rev_row = frappe.db.sql(
		"""SELECT COALESCE(SUM(gle.credit) - SUM(gle.debit), 0) FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND acc.root_type = 'Income' AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled = 0""",
		(company, from_date, to_date),
	) or [(0,)]
	exp_row = frappe.db.sql(
		"""SELECT COALESCE(SUM(gle.debit) - SUM(gle.credit), 0) FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company = %s AND acc.root_type = 'Expense' AND gle.posting_date BETWEEN %s AND %s AND gle.is_cancelled = 0""",
		(company, from_date, to_date),
	) or [(0,)]

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
	ratios.append(
		{
			"category": "Liquidity",
			"name": "Current Ratio",
			"value": round(ta / cl, 2) if cl else 0,
			"description": "Total Assets / Current Liabilities",
		}
	)
	ratios.append(
		{
			"category": "Liquidity",
			"name": "Quick Ratio",
			"value": round(ca / cl, 2) if cl else 0,
			"description": "Current Assets / Current Liabilities",
		}
	)
	# Profitability (1 decimal for %)
	ratios.append(
		{
			"category": "Profitability",
			"name": "Profit Margin %",
			"value": round(profit / rev * 100, 1) if rev else 0,
			"description": "Net Profit / Revenue",
		}
	)
	ratios.append(
		{
			"category": "Profitability",
			"name": "Operating Margin %",
			"value": round(operating_profit / rev * 100, 1) if rev else 0,
			"description": "Operating Profit / Revenue",
		}
	)
	ratios.append(
		{
			"category": "Profitability",
			"name": "ROA %",
			"value": round(profit / ta * 100, 1) if ta else 0,
			"description": "Net Profit / Total Assets",
		}
	)
	ratios.append(
		{
			"category": "Profitability",
			"name": "ROE %",
			"value": round(profit / equity * 100, 1) if equity else 0,
			"description": "Net Profit / Equity",
		}
	)
	ratios.append(
		{
			"category": "Profitability",
			"name": "Net Profit",
			"value": round(profit, 0),
			"description": "Revenue - Expenses",
		}
	)
	# Solvency / Performance
	ratios.append(
		{
			"category": "Solvency",
			"name": "Debt Ratio",
			"value": round(tl / ta, 2) if ta else 0,
			"description": "Total Liabilities / Total Assets",
		}
	)
	ratios.append(
		{
			"category": "Solvency",
			"name": "Equity Ratio",
			"value": round(equity / ta, 2) if ta else 0,
			"description": "Equity / Total Assets",
		}
	)
	ratios.append(
		{
			"category": "Solvency",
			"name": "Debt to Equity",
			"value": round(tl / equity, 2) if equity else 0,
			"description": "Total Liabilities / Equity",
		}
	)
	# Efficiency
	ratios.append(
		{
			"category": "Efficiency",
			"name": "Asset Turnover",
			"value": round(rev / ta, 2) if ta else 0,
			"description": "Revenue / Total Assets",
		}
	)
	return ratios


@frappe.whitelist()
def get_tax_year_dates(reference_date=None):
	"""Pakistan tax year: 1 July to 30 June."""
	reference = getdate(reference_date or nowdate())
	start_year = reference.year if reference.month >= 7 else reference.year - 1
	return {
		"from_date": f"{start_year}-07-01",
		"to_date": f"{start_year + 1}-06-30",
		"label": f"Tax Year {start_year}-{start_year + 1}",
	}


def _period_bounds_for_previous(from_date, to_date):
	period_days = (to_date - from_date).days + 1
	prev_to = from_date - timedelta(days=1)
	prev_from = prev_to - timedelta(days=period_days - 1)
	return prev_from, prev_to


@frappe.whitelist()
def get_invoice_activity(company, from_date, to_date):
	from_date, to_date = _get_dates(company, from_date, to_date)

	def invoice_row(doctype, date_field="posting_date"):
		return frappe.db.sql(
			f"""
			SELECT COUNT(*) AS count, COALESCE(SUM(grand_total), 0) AS total
			FROM `tab{doctype}`
			WHERE company = %s
			  AND docstatus = 1
			  AND {date_field} BETWEEN %s AND %s
			""",
			(company, from_date, to_date),
			as_dict=True,
		)[0]

	sales = invoice_row("Sales Invoice")
	purchase_invoices = invoice_row("Purchase Invoice")
	purchase_receipts = invoice_row("Purchase Receipt")

	return {
		"sales_count": sales.count or 0,
		"sales_total": sales.total or 0,
		"purchase_invoice_count": purchase_invoices.count or 0,
		"purchase_invoice_total": purchase_invoices.total or 0,
		"purchase_receipt_count": purchase_receipts.count or 0,
		"purchase_receipt_total": purchase_receipts.total or 0,
	}


def _status_group_rows(company, from_date, to_date, fieldname, item_field=False, limit=20):
	table = "`tabSales Invoice Item` sii" if item_field else "`tabSales Invoice` si"
	join = "INNER JOIN `tabSales Invoice` si ON sii.parent = si.name" if item_field else ""
	label_expr = f"COALESCE(NULLIF({fieldname}, ''), 'Not Set')"
	return frappe.db.sql(
		f"""
		SELECT
			{label_expr} AS label,
			COUNT(DISTINCT si.name) AS invoice_count,
			COALESCE(SUM({"sii.base_net_amount" if item_field else "si.base_net_total"}), 0) AS exclusive,
			COALESCE(SUM({"COALESCE(sii.custom_total_tax_amount, 0)" if item_field else "si.base_total_taxes_and_charges"}), 0) AS tax,
			COALESCE(SUM({"CASE WHEN COALESCE(sii.custom_tax_inclusive_amount, 0) > 0 THEN sii.custom_tax_inclusive_amount ELSE sii.base_net_amount + COALESCE(sii.custom_total_tax_amount, 0) END" if item_field else "si.base_grand_total"}), 0) AS inclusive
		FROM {table}
		{join}
		WHERE si.company = %s
		  AND si.posting_date BETWEEN %s AND %s
		  AND si.docstatus IN (0, 1)
		GROUP BY label
		ORDER BY inclusive DESC
		LIMIT {cint(limit)}
		""",
		(company, from_date, to_date),
		as_dict=True,
	)


def _item_tax_template_status_rows(company, from_date, to_date):
	rows = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(sii.item_tax_template, ''), 'Not Set') AS item_tax_template,
			COALESCE(accounts.account_head, 'No GL Account') AS account_head,
			COUNT(DISTINCT si.name) AS invoice_count,
			COALESCE(SUM(sii.base_net_amount), 0) AS exclusive,
			COALESCE(SUM(COALESCE(sii.custom_total_tax_amount, 0)), 0) AS tax,
			COALESCE(SUM(
				CASE
					WHEN COALESCE(sii.custom_tax_inclusive_amount, 0) > 0
					THEN sii.custom_tax_inclusive_amount
					ELSE sii.base_net_amount + COALESCE(sii.custom_total_tax_amount, 0)
				END
			), 0) AS inclusive
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON sii.parent = si.name
		LEFT JOIN (
			SELECT parent, GROUP_CONCAT(DISTINCT tax_type ORDER BY idx SEPARATOR ', ') AS account_head
			FROM `tabItem Tax Template Detail`
			WHERE parenttype = 'Item Tax Template'
			GROUP BY parent
		) accounts ON accounts.parent = sii.item_tax_template
		WHERE si.company = %s
		  AND si.posting_date BETWEEN %s AND %s
		  AND si.docstatus IN (0, 1)
		GROUP BY item_tax_template, account_head
		HAVING exclusive <> 0 OR tax <> 0 OR inclusive <> 0
		ORDER BY tax DESC, inclusive DESC
		LIMIT 20
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	for row in rows:
		row.percentage = round((row.tax or 0) / (row.exclusive or 1) * 100, 2) if row.exclusive else 0
	return rows


@frappe.whitelist()
def get_sales_invoice_status_report(company, from_date, to_date):
	from_date, to_date = _get_dates(company, from_date, to_date)
	summary = frappe.db.sql(
		"""
		SELECT
			COUNT(*) AS total_invoices,
			SUM(CASE WHEN docstatus = 0 THEN 1 ELSE 0 END) AS draft_count,
			SUM(CASE WHEN docstatus = 1 THEN 1 ELSE 0 END) AS submitted_count,
			SUM(CASE WHEN docstatus = 1 AND COALESCE(custom_fbr_invoice_no, '') != '' THEN 1 ELSE 0 END) AS fbr_submitted_count,
			SUM(CASE WHEN docstatus = 1 AND COALESCE(custom_fbr_invoice_no, '') = '' THEN 1 ELSE 0 END) AS fbr_pending_count,
			SUM(CASE WHEN docstatus = 1 AND LOWER(COALESCE(custom_fbr_invoice_status, '')) LIKE '%%fail%%' THEN 1 ELSE 0 END) AS fbr_failed_count,
			COALESCE(SUM(CASE WHEN docstatus = 1 THEN base_net_total ELSE 0 END), 0) AS exclusive_sales,
			COALESCE(SUM(CASE WHEN docstatus = 1 THEN base_total_taxes_and_charges ELSE 0 END), 0) AS taxes,
			COALESCE(SUM(CASE WHEN docstatus = 1 THEN base_grand_total ELSE 0 END), 0) AS inclusive_sales
		FROM `tabSales Invoice`
		WHERE company = %s
		  AND posting_date BETWEEN %s AND %s
		  AND docstatus IN (0, 1)
		""",
		(company, from_date, to_date),
		as_dict=True,
	)[0]

	status_mix = frappe.db.sql(
		"""
		SELECT COALESCE(NULLIF(status, ''), 'No Status') AS label,
			COUNT(*) AS value
		FROM `tabSales Invoice`
		WHERE company = %s
		  AND posting_date BETWEEN %s AND %s
		  AND docstatus IN (0, 1)
		GROUP BY label
		ORDER BY value DESC
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	fbr_status_mix = frappe.db.sql(
		"""
		SELECT
			CASE
				WHEN docstatus = 0 THEN 'Draft'
				WHEN COALESCE(custom_fbr_invoice_no, '') != '' THEN 'Submitted to FBR'
				WHEN LOWER(COALESCE(custom_fbr_invoice_status, '')) LIKE '%%fail%%' THEN 'Failed'
				ELSE 'Pending FBR'
			END AS label,
			COUNT(*) AS value
		FROM `tabSales Invoice`
		WHERE company = %s
		  AND posting_date BETWEEN %s AND %s
		  AND docstatus IN (0, 1)
		GROUP BY label
		ORDER BY value DESC
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	recent_invoices = frappe.db.sql(
		"""
		SELECT
			name,
			posting_date,
			customer_name,
			status,
			COALESCE(custom_fbr_invoice_status, '') AS fbr_status,
			COALESCE(custom_fbr_responsed, '') AS custom_fbr_responsed,
			COALESCE(custom_fbr_invoice_no, '') AS fbr_invoice_no,
			COALESCE(base_net_total, 0) AS exclusive,
			COALESCE(base_total_taxes_and_charges, 0) AS taxes,
			COALESCE(base_grand_total, 0) AS inclusive,
			COALESCE(custom_tax_payer_type, '') AS custom_tax_payer_type,
			COALESCE(custom_buyer_province, '') AS custom_buyer_province,
			COALESCE(custom_scenario_detail, '') AS custom_scenario_detail
		FROM `tabSales Invoice`
		WHERE company = %s
		  AND posting_date BETWEEN %s AND %s
		  AND docstatus IN (0, 1)
		ORDER BY posting_date DESC, modified DESC
		LIMIT 20
		""",
		(company, from_date, to_date),
		as_dict=True,
	)

	return {
		"summary": {
			"total_invoices": cint(summary.total_invoices),
			"draft_count": cint(summary.draft_count),
			"submitted_count": cint(summary.submitted_count),
			"cancelled_count": 0,
			"fbr_submitted_count": cint(summary.fbr_submitted_count),
			"fbr_pending_count": cint(summary.fbr_pending_count),
			"fbr_failed_count": cint(summary.fbr_failed_count),
			"exclusive_sales": round(summary.exclusive_sales or 0, 0),
			"taxes": round(summary.taxes or 0, 0),
			"inclusive_sales": round(summary.inclusive_sales or 0, 0),
		},
		"generated_on": nowdate(),
		"status_mix": status_mix,
		"fbr_status_mix": fbr_status_mix,
		"tax_payer_type": _status_group_rows(company, from_date, to_date, "si.custom_tax_payer_type"),
		"buyer_province": _status_group_rows(company, from_date, to_date, "si.custom_buyer_province"),
		"scenario_detail": _status_group_rows(company, from_date, to_date, "si.custom_scenario_detail"),
		"sale_type": _status_group_rows(company, from_date, to_date, "sii.custom_sale_type", item_field=True),
		"sro_schedule": _status_group_rows(
			company, from_date, to_date, "sii.custom_sro_schedule_no", item_field=True
		),
		"item_tax_template": _item_tax_template_status_rows(company, from_date, to_date),
		"recent_invoices": recent_invoices,
	}


@frappe.whitelist()
def get_dashboard_data(company, from_date=None, to_date=None, group_by="monthly"):
	if not from_date or not to_date:
		tax_year = get_tax_year_dates()
		from_date = from_date or tax_year["from_date"]
		to_date = to_date or tax_year["to_date"]

	from_date, to_date = _get_dates(company, from_date, to_date)
	currency = frappe.get_cached_value("Company", company, "default_currency") or frappe.db.get_default(
		"currency"
	)
	prev_from, prev_to = _period_bounds_for_previous(from_date, to_date)

	summary = get_financial_summary(company, from_date, to_date)
	previous_summary = get_financial_summary(company, prev_from, prev_to)
	trend = get_trend_data(company, from_date, to_date, group_by)
	cash_flow = get_cash_flow(company, from_date, to_date)
	expense_breakdown = get_expense_breakdown(company, from_date, to_date)
	expense_hierarchy = get_expense_hierarchy(company, from_date, to_date)
	stock_by_item_group = get_stock_by_item_group(company)
	warehouses = get_warehouses(company)
	revenue_sources = get_revenue_sources(company, from_date, to_date)
	customer_group_sales = get_customer_group_sales(company, from_date, to_date)
	supplier_group_purchases = get_supplier_group_purchases(company, from_date, to_date)
	sales_summary = get_sales_summary(company, from_date, to_date, group_by)
	sales_returns = get_sales_return_invoices(company, from_date, to_date)
	purchases_summary = get_purchases_summary(company, from_date, to_date, group_by)
	tax_period_summary = get_tax_period_summary(company, from_date, to_date, group_by)
	sales_tax_summary = get_sales_tax_summary(company, from_date, to_date)
	purchase_tax_summary = get_purchase_tax_summary(company, from_date, to_date)
	tax_account_reports = get_tax_account_reports(company, from_date, to_date)
	ratios = get_ratio_analysis(company, from_date, to_date)
	activity = get_invoice_activity(company, from_date, to_date)
	sales_invoice_status = get_sales_invoice_status_report(company, from_date, to_date)
	receivables = get_aging_receivables(company, to_date)
	payables = get_aging_payables(company, to_date)

	return {
		"company": company,
		"currency": currency,
		"from_date": str(from_date),
		"to_date": str(to_date),
		"tax_year": get_tax_year_dates(to_date),
		"period_label": f"{from_date.strftime('%d-%m-%Y')} to {to_date.strftime('%d-%m-%Y')}",
		"previous_period_label": f"{prev_from.strftime('%d-%m-%Y')} to {prev_to.strftime('%d-%m-%Y')}",
		"summary": summary,
		"previous_summary": previous_summary,
		"trend": trend,
		"cash_flow": cash_flow,
		"expense_breakdown": expense_breakdown,
		"expense_hierarchy": expense_hierarchy,
		"stock_by_item_group": stock_by_item_group,
		"warehouses": warehouses,
		"revenue_sources": revenue_sources,
		"customer_group_sales": customer_group_sales,
		"supplier_group_purchases": supplier_group_purchases,
		"sales_summary": sales_summary,
		"sales_returns": sales_returns,
		"purchases_summary": purchases_summary,
		"tax_period_summary": tax_period_summary,
		"sales_tax_summary": sales_tax_summary,
		"purchase_tax_summary": purchase_tax_summary,
		"tax_account_reports": tax_account_reports,
		"ratios": ratios,
		"activity": activity,
		"sales_invoice_status": sales_invoice_status,
		"receivables": receivables[:8] if isinstance(receivables, list) else [],
		"payables": payables[:8] if isinstance(payables, list) else [],
	}
