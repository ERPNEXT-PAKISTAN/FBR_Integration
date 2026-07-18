import frappe
from frappe.utils import add_to_date, getdate, nowdate


@frappe.whitelist()
def customer_supplier_details_dashboard_api(
	from_date=None, to_date=None, chart_of_accounts=None, party=None, party_type=None, account=None
):
	# customer_supplier_details_dashboard_api (Customer & Supplier Trial Balance by Party)
	# Script Type: API
	# API Method: customer_supplier_details_dashboard_api

	args = frappe._dict(
		{
			"from_date": from_date,
			"to_date": to_date,
			"chart_of_accounts": chart_of_accounts,
			"party": party,
			"party_type": party_type,
			"account": account,
		}
	)

	from_date = args.get("from_date")
	to_date = args.get("to_date")
	chart_of_accounts = args.get("chart_of_accounts")
	party = args.get("party")
	party_type = args.get("party_type")
	account = args.get("account")

	# ---- Build Account Filters ----
	# Filter only for Customer (Receivable) and Supplier (Payable) accounts
	account_filters = {"account_type": ["in", ["Receivable", "Payable"]]}

	if chart_of_accounts:
		account_filters["company"] = chart_of_accounts

	# ---- Fetch Accounts ----
	accounts_list = frappe.get_all(
		"Account",
		filters=account_filters,
		fields=["name", "account_name", "parent_account", "root_type", "account_type", "company"],
		limit_page_length=10000,
	)

	# Build account name map
	account_name_map = {}
	for acc in accounts_list:
		account_name_map[acc["name"]] = acc.get("account_name", "")

	# Get account names for filtering
	account_names = [a["name"] for a in accounts_list]

	if account:
		if account in account_names:
			account_names = [account]
		else:
			account_names = []

	# If no accounts match, set to empty list
	if not account_names:
		account_names = []

	# ---- Build GL Entry Filters ----
	gl_filters = {
		"docstatus": 1,
		"is_cancelled": 0,
		"account": ["in", account_names],
		"party_type": ["in", ["Customer", "Supplier"]],
	}

	if party:
		gl_filters["party"] = party

	if party_type:
		if party_type in ["Customer", "Supplier"]:
			gl_filters["party_type"] = party_type

	if chart_of_accounts:
		gl_filters["company"] = chart_of_accounts

	# ---- Fetch Opening Balances (before from_date) ----
	opening_balances = {}  # {party: {"party_type": "", "opening_debit": 0, "opening_credit": 0, "account": ""}}

	if from_date and account_names:
		opening_filters = gl_filters.copy()
		opening_filters["posting_date"] = ["<", from_date]

		opening_entries = frappe.get_all(
			"GL Entry",
			filters=opening_filters,
			fields=["party", "party_type", "account", "debit", "credit"],
			limit_page_length=100000,
		)

		for entry in opening_entries:
			party_name = entry.get("party")
			if party_name:
				if party_name not in opening_balances:
					opening_balances[party_name] = {
						"party_type": entry.get("party_type", ""),
						"opening_debit": 0,
						"opening_credit": 0,
						"account": entry.get("account", ""),
					}
				opening_balances[party_name]["opening_debit"] = opening_balances[party_name][
					"opening_debit"
				] + float(entry.get("debit") or 0)
				opening_balances[party_name]["opening_credit"] = opening_balances[party_name][
					"opening_credit"
				] + float(entry.get("credit") or 0)

	# ---- Fetch Period GL Entries (from_date to to_date) ----
	period_balances = {}  # {party: {"debit": 0, "credit": 0}}

	if from_date and to_date and account_names:
		period_filters = gl_filters.copy()
		period_filters["posting_date"] = ["between", [from_date, to_date]]

		period_entries = frappe.get_all(
			"GL Entry",
			filters=period_filters,
			fields=["party", "party_type", "account", "debit", "credit"],
			limit_page_length=100000,
		)

		for entry in period_entries:
			party_name = entry.get("party")
			if party_name:
				if party_name not in period_balances:
					period_balances[party_name] = {
						"party_type": entry.get("party_type", ""),
						"debit": 0,
						"credit": 0,
						"account": entry.get("account", ""),
					}
				period_balances[party_name]["debit"] = period_balances[party_name]["debit"] + float(
					entry.get("debit") or 0
				)
				period_balances[party_name]["credit"] = period_balances[party_name]["credit"] + float(
					entry.get("credit") or 0
				)

	# ---- Build Trial Balance Data by Party ----
	# Get all parties that have transactions
	all_parties = set()
	all_parties.update(opening_balances.keys())
	all_parties.update(period_balances.keys())

	trial_balance_detail = []  # For detail party table
	trial_balance_parent = {}  # For parent party type table {party_type: {...}}

	for party_name in sorted(all_parties):
		# Get opening balance data
		opening_data = opening_balances.get(party_name, {})
		opening_debit = float(opening_data.get("opening_debit", 0) or 0)
		opening_credit = float(opening_data.get("opening_credit", 0) or 0)
		party_type = opening_data.get("party_type", period_balances.get(party_name, {}).get("party_type", ""))
		account = opening_data.get("account", period_balances.get(party_name, {}).get("account", ""))

		# Get period balance data
		period_data = period_balances.get(party_name, {})
		period_debit = float(period_data.get("debit", 0) or 0)
		period_credit = float(period_data.get("credit", 0) or 0)

		# Calculate closing balances
		closing_debit = opening_debit + period_debit
		closing_credit = opening_credit + period_credit

		# If closing balances are both zero, skip
		if closing_debit == 0 and closing_credit == 0:
			continue

		# Calculate net balances and split into debit/credit
		opening_balance = opening_debit - opening_credit
		closing_balance = closing_debit - closing_credit

		# Split balances: if positive -> debit, if negative -> credit (absolute value)
		opening_balance_debit = opening_balance if opening_balance > 0 else 0.0
		opening_balance_credit = abs(opening_balance) if opening_balance < 0 else 0.0
		closing_balance_debit = closing_balance if closing_balance > 0 else 0.0
		closing_balance_credit = abs(closing_balance) if closing_balance < 0 else 0.0

		detail_row = {
			"party": party_name,
			"party_type": party_type,
			"account": account,
			"account_name": account_name_map.get(account, account),
			"opening_debit": float(opening_debit),
			"opening_credit": float(opening_credit),
			"opening_balance_debit": float(opening_balance_debit),
			"opening_balance_credit": float(opening_balance_credit),
			"debit": float(period_debit),
			"credit": float(period_credit),
			"closing_debit": float(closing_debit),
			"closing_credit": float(closing_credit),
			"closing_balance_debit": float(closing_balance_debit),
			"closing_balance_credit": float(closing_balance_credit),
		}

		trial_balance_detail.append(detail_row)

		# Aggregate by party type (Customer/Supplier)
		if party_type:
			if party_type not in trial_balance_parent:
				trial_balance_parent[party_type] = {
					"party_type": party_type,
					"opening_debit": 0.0,
					"opening_credit": 0.0,
					"opening_balance_debit": 0.0,
					"opening_balance_credit": 0.0,
					"debit": 0.0,
					"credit": 0.0,
					"closing_debit": 0.0,
					"closing_credit": 0.0,
					"closing_balance_debit": 0.0,
					"closing_balance_credit": 0.0,
				}

			trial_balance_parent[party_type]["opening_debit"] = float(
				trial_balance_parent[party_type]["opening_debit"]
			) + float(opening_debit)
			trial_balance_parent[party_type]["opening_credit"] = float(
				trial_balance_parent[party_type]["opening_credit"]
			) + float(opening_credit)
			trial_balance_parent[party_type]["opening_balance_debit"] = float(
				trial_balance_parent[party_type]["opening_balance_debit"]
			) + float(opening_balance_debit)
			trial_balance_parent[party_type]["opening_balance_credit"] = float(
				trial_balance_parent[party_type]["opening_balance_credit"]
			) + float(opening_balance_credit)
			trial_balance_parent[party_type]["debit"] = float(
				trial_balance_parent[party_type]["debit"]
			) + float(period_debit)
			trial_balance_parent[party_type]["credit"] = float(
				trial_balance_parent[party_type]["credit"]
			) + float(period_credit)
			trial_balance_parent[party_type]["closing_debit"] = float(
				trial_balance_parent[party_type]["closing_debit"]
			) + float(closing_debit)
			trial_balance_parent[party_type]["closing_credit"] = float(
				trial_balance_parent[party_type]["closing_credit"]
			) + float(closing_credit)
			trial_balance_parent[party_type]["closing_balance_debit"] = float(
				trial_balance_parent[party_type]["closing_balance_debit"]
			) + float(closing_balance_debit)
			trial_balance_parent[party_type]["closing_balance_credit"] = float(
				trial_balance_parent[party_type]["closing_balance_credit"]
			) + float(closing_balance_credit)

	# Convert parent party type dict to sorted list
	trial_balance_parent_list = sorted(trial_balance_parent.values(), key=lambda x: x.get("party_type", ""))

	# ---- Build Distinct Value Sets ----
	company_set = set()
	party_set = set()
	party_type_set = set()
	account_set = set()

	# Get distinct values from GL Entries
	if account_names:
		distinct_gl_filters = {
			"docstatus": 1,
			"is_cancelled": 0,
			"account": ["in", account_names],
			"party_type": ["in", ["Customer", "Supplier"]],
		}
		if chart_of_accounts:
			distinct_gl_filters["company"] = chart_of_accounts

		distinct_entries = frappe.get_all(
			"GL Entry",
			filters=distinct_gl_filters,
			fields=["party", "party_type", "account", "company"],
			limit_page_length=100000,
		)

		for entry in distinct_entries:
			if entry.get("party"):
				party_set.add(entry["party"])
			if entry.get("party_type"):
				party_type_set.add(entry["party_type"])
			if entry.get("account"):
				account_set.add(entry["account"])
			if entry.get("company"):
				company_set.add(entry["company"])

	# Also add from accounts list
	for acc in accounts_list:
		if acc.get("company"):
			company_set.add(acc["company"])
		if acc.get("name"):
			account_set.add(acc["name"])

	# ---- Return Response ----
	return {
		"trial_balance_detail": trial_balance_detail,
		"trial_balance_parent": trial_balance_parent_list,
		"distinct_values": {
			"companies": sorted(company_set),
			"parties": sorted(party_set),
			"party_types": sorted(party_type_set),
			"accounts": sorted(account_set),
		},
	}


def _current_pakistan_tax_year():
	today = getdate(nowdate())
	start_year = today.year if today.month >= 7 else today.year - 1
	return getdate(f"{start_year}-07-01"), getdate(f"{start_year + 1}-06-30")


def _pct_change(current, previous):
	if not previous:
		return 0
	return round((current - previous) / previous * 100, 1)


def _company_currency(company):
	return frappe.get_cached_value("Company", company, "default_currency") or frappe.db.get_default(
		"currency"
	)


def _first_company(company=None):
	if company:
		return company
	return (
		frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.get_all("Company", pluck="name", limit=1)[0]
	)


def _income_expense_summary(company, from_date, to_date):
	rows = frappe.db.sql(
		"""
		SELECT
			acc.root_type,
			COALESCE(SUM(gle.credit) - SUM(gle.debit), 0) AS income,
			COALESCE(SUM(gle.debit) - SUM(gle.credit), 0) AS expense
		FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` acc ON gle.account = acc.name
		WHERE gle.company = %s
		  AND gle.posting_date BETWEEN %s AND %s
		  AND gle.is_cancelled = 0
		  AND acc.root_type IN ('Income', 'Expense')
		GROUP BY acc.root_type
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	revenue = sum(row.income or 0 for row in rows if row.root_type == "Income")
	expenses = sum(row.expense or 0 for row in rows if row.root_type == "Expense")
	profit = revenue - expenses
	margin = (profit / revenue * 100) if revenue else 0
	return {
		"revenue": round(revenue, 0),
		"expenses": round(expenses, 0),
		"profit": round(profit, 0),
		"margin": round(margin, 1),
	}


def _sales_invoice_totals(company, from_date, to_date):
	return frappe.db.sql(
		"""
		SELECT
			COUNT(*) AS invoice_count,
			SUM(CASE WHEN docstatus = 1 AND is_return = 1 THEN 1 ELSE 0 END) AS return_count,
			SUM(CASE WHEN docstatus = 0 THEN 1 ELSE 0 END) AS draft_count,
			SUM(CASE WHEN docstatus = 1 THEN 1 ELSE 0 END) AS submitted_count,
			SUM(CASE WHEN docstatus = 1 AND COALESCE(custom_fbr_invoice_no, '') != '' THEN 1 ELSE 0 END) AS fbr_success_count,
			SUM(CASE WHEN docstatus = 1 AND COALESCE(custom_fbr_invoice_no, '') = '' THEN 1 ELSE 0 END) AS fbr_pending_count,
			COALESCE(SUM(CASE WHEN docstatus = 1 THEN base_net_total ELSE 0 END), 0) AS exclusive,
			COALESCE(SUM(CASE WHEN docstatus = 1 THEN base_total_taxes_and_charges ELSE 0 END), 0) AS tax,
			COALESCE(SUM(CASE WHEN docstatus = 1 THEN base_grand_total ELSE 0 END), 0) AS inclusive
		FROM `tabSales Invoice`
		WHERE company = %s
		  AND posting_date BETWEEN %s AND %s
		  AND docstatus IN (0, 1)
		""",
		(company, from_date, to_date),
		as_dict=True,
	)[0]


def _expense_main_group_totals(company, from_date, to_date):
	groups = frappe.db.sql(
		"""
		SELECT account_name, lft, rgt
		FROM `tabAccount`
		WHERE company = %s
		  AND root_type = 'Expense'
		  AND is_group = 1
		  AND LOWER(account_name) IN ('direct expenses', 'indirect expenses')
		""",
		(company,),
		as_dict=True,
	)
	totals = {"direct": 0, "indirect": 0}
	for group in groups:
		row = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(gle.debit) - SUM(gle.credit), 0) AS amount
			FROM `tabGL Entry` gle
			INNER JOIN `tabAccount` account ON gle.account = account.name
			WHERE gle.company = %s
			  AND gle.posting_date BETWEEN %s AND %s
			  AND gle.is_cancelled = 0
			  AND account.lft BETWEEN %s AND %s
			""",
			(company, from_date, to_date, group.lft, group.rgt),
			as_dict=True,
		)[0]
		key = "direct" if (group.account_name or "").lower() == "direct expenses" else "indirect"
		totals[key] = round(row.amount or 0, 0)
	total = totals["direct"] + totals["indirect"]
	totals["direct_pct"] = round((totals["direct"] / total * 100) if total else 0, 1)
	totals["indirect_pct"] = round((totals["indirect"] / total * 100) if total else 0, 1)
	return totals


def _purchase_totals(company, from_date, to_date):
	return frappe.db.sql(
		"""
		SELECT
			COUNT(*) AS purchase_count,
			COALESCE(SUM(base_net_total), 0) AS purchase_exclusive,
			COALESCE(SUM(base_total_taxes_and_charges), 0) AS purchase_tax,
			COALESCE(SUM(base_grand_total), 0) AS purchase_total
		FROM `tabPurchase Invoice`
		WHERE company = %s
		  AND posting_date BETWEEN %s AND %s
		  AND docstatus = 1
		""",
		(company, from_date, to_date),
		as_dict=True,
	)[0]


def _sales_purchase_trend(company, from_date, to_date):
	sales_rows = frappe.db.sql(
		"""
		SELECT DATE_FORMAT(posting_date, '%%Y-%%m') AS period,
			COALESCE(SUM(base_grand_total), 0) AS amount
		FROM `tabSales Invoice`
		WHERE company = %s
		  AND posting_date BETWEEN %s AND %s
		  AND docstatus = 1
		GROUP BY period
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	purchase_rows = frappe.db.sql(
		"""
		SELECT DATE_FORMAT(posting_date, '%%Y-%%m') AS period,
			COALESCE(SUM(base_grand_total), 0) AS amount
		FROM `tabPurchase Invoice`
		WHERE company = %s
		  AND posting_date BETWEEN %s AND %s
		  AND docstatus = 1
		GROUP BY period
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	sales_by_period = {row.period: row.amount or 0 for row in sales_rows}
	purchase_by_period = {row.period: row.amount or 0 for row in purchase_rows}
	periods = []
	cursor = getdate(from_date)
	while cursor <= to_date:
		periods.append(cursor.strftime("%Y-%m"))
		cursor = add_to_date(cursor, months=1)
	return {
		"labels": periods,
		"sales": [round(sales_by_period.get(period, 0), 0) for period in periods],
		"purchases": [round(purchase_by_period.get(period, 0), 0) for period in periods],
	}


@frappe.whitelist()
def fiscal_year_kpi_block_data(company=None):
	company = _first_company(company)
	from_date, to_date = _current_pakistan_tax_year()
	prev_from = add_to_date(from_date, years=-1)
	prev_to = add_to_date(to_date, years=-1)
	current_summary = _income_expense_summary(company, from_date, to_date)
	previous_summary = _income_expense_summary(company, prev_from, prev_to)
	sales = _sales_invoice_totals(company, from_date, to_date)
	expense_groups = _expense_main_group_totals(company, from_date, to_date)
	purchases = _purchase_totals(company, from_date, to_date)

	return {
		"company": company,
		"currency": _company_currency(company),
		"from_date": str(from_date),
		"to_date": str(to_date),
		"period_label": f"{from_date.strftime('%d-%m-%Y')} to {to_date.strftime('%d-%m-%Y')}",
		"summary": {
			**current_summary,
			"direct_expenses": expense_groups["direct"],
			"indirect_expenses": expense_groups["indirect"],
			"direct_expenses_pct": expense_groups["direct_pct"],
			"indirect_expenses_pct": expense_groups["indirect_pct"],
			"revenue_change": _pct_change(current_summary["revenue"], previous_summary["revenue"]),
			"expenses_change": _pct_change(current_summary["expenses"], previous_summary["expenses"]),
			"profit_change": _pct_change(current_summary["profit"], previous_summary["profit"]),
			"margin_change": round(current_summary["margin"] - previous_summary["margin"], 1),
		},
		"sales": {
			"invoice_count": int(sales.invoice_count or 0),
			"return_count": int(sales.return_count or 0),
			"draft_count": int(sales.draft_count or 0),
			"submitted_count": int(sales.submitted_count or 0),
			"fbr_success_count": int(sales.fbr_success_count or 0),
			"fbr_pending_count": int(sales.fbr_pending_count or 0),
			"exclusive": round(sales.exclusive or 0, 0),
			"tax": round(sales.tax or 0, 0),
			"inclusive": round(sales.inclusive or 0, 0),
		},
		"purchases": {
			"purchase_count": int(purchases.purchase_count or 0),
			"purchase_exclusive": round(purchases.purchase_exclusive or 0, 0),
			"purchase_tax": round(purchases.purchase_tax or 0, 0),
			"purchase_total": round(purchases.purchase_total or 0, 0),
		},
		"trend": _sales_purchase_trend(company, from_date, to_date),
	}


@frappe.whitelist()
def account_details_dashboard_api(
	from_date=None,
	to_date=None,
	chart_of_accounts=None,
	account=None,
	parent_account=None,
	account_type=None,
	root_type=None,
):
	# account_details_dashboard_api (Trial Balance)
	# Script Type: API
	# API Method: account_details_dashboard_api

	args = frappe._dict(
		{
			"from_date": from_date,
			"to_date": to_date,
			"chart_of_accounts": chart_of_accounts,
			"account": account,
			"parent_account": parent_account,
			"account_type": account_type,
			"root_type": root_type,
		}
	)

	from_date = args.get("from_date")
	to_date = args.get("to_date")
	chart_of_accounts = args.get("chart_of_accounts")
	account = args.get("account")
	parent_account = args.get("parent_account")
	account_type = args.get("account_type")
	root_type = args.get("root_type")

	# ---- Build Account Filters ----
	account_filters = {}

	if chart_of_accounts:
		account_filters["company"] = chart_of_accounts

	if root_type:
		account_filters["root_type"] = root_type

	if account_type:
		account_filters["account_type"] = account_type

	# ---- Fetch Accounts ----
	accounts_list = frappe.get_all(
		"Account",
		filters=account_filters,
		fields=["name", "account_name", "parent_account", "root_type", "account_type", "company"],
		limit_page_length=10000,
	)

	# Build account name map and parent account map
	account_name_map = {}
	parent_account_map = {}
	for acc in accounts_list:
		account_name_map[acc["name"]] = acc.get("account_name", "")
		if acc.get("parent_account"):
			parent_account_map[acc["name"]] = acc["parent_account"]

	# Filter accounts if specific account or parent_account is selected
	account_names = [a["name"] for a in accounts_list]

	if account:
		if account in account_names:
			account_names = [account]
		else:
			account_names = []

	if parent_account:
		# Get all child accounts under this parent
		child_accounts = [a["name"] for a in accounts_list if a.get("parent_account") == parent_account]
		if account_names:
			# Intersect with already filtered accounts
			account_names = [acc for acc in account_names if acc in child_accounts]
		else:
			account_names = child_accounts

	# If no accounts match, set to empty list
	if not account_names:
		account_names = []

	# ---- Fetch Opening Balances (before from_date) ----
	opening_balances = {}  # {account: {"opening_debit": 0, "opening_credit": 0}}

	if from_date and account_names:
		opening_filters = {
			"docstatus": 1,
			"is_cancelled": 0,
			"posting_date": ["<", from_date],
			"account": ["in", account_names],
		}

		opening_entries = frappe.get_all(
			"GL Entry",
			filters=opening_filters,
			fields=["account", "debit", "credit"],
			limit_page_length=100000,
		)

		for entry in opening_entries:
			acc = entry.get("account")
			if acc:
				if acc not in opening_balances:
					opening_balances[acc] = {"opening_debit": 0, "opening_credit": 0}
				opening_balances[acc]["opening_debit"] = opening_balances[acc]["opening_debit"] + float(
					entry.get("debit") or 0
				)
				opening_balances[acc]["opening_credit"] = opening_balances[acc]["opening_credit"] + float(
					entry.get("credit") or 0
				)

	# ---- Fetch Period GL Entries (from_date to to_date) ----
	period_balances = {}  # {account: {"debit": 0, "credit": 0}}

	if from_date and to_date and account_names:
		period_filters = {
			"docstatus": 1,
			"is_cancelled": 0,
			"posting_date": ["between", [from_date, to_date]],
			"account": ["in", account_names],
		}

		period_entries = frappe.get_all(
			"GL Entry",
			filters=period_filters,
			fields=["account", "debit", "credit"],
			limit_page_length=100000,
		)

		for entry in period_entries:
			acc = entry.get("account")
			if acc:
				if acc not in period_balances:
					period_balances[acc] = {"debit": 0, "credit": 0}
				period_balances[acc]["debit"] = period_balances[acc]["debit"] + float(entry.get("debit") or 0)
				period_balances[acc]["credit"] = period_balances[acc]["credit"] + float(
					entry.get("credit") or 0
				)

	# ---- Build Trial Balance Data ----
	# Get all accounts that have transactions or are in the filtered list
	all_accounts_in_tb = set(account_names)
	all_accounts_in_tb.update(opening_balances.keys())
	all_accounts_in_tb.update(period_balances.keys())

	trial_balance_detail = []  # For detail account table
	trial_balance_parent = {}  # For parent account table {parent_account: {...}}

	for acc_name in sorted(all_accounts_in_tb):
		# Ensure all values are floats, not None
		opening_debit = float(opening_balances.get(acc_name, {}).get("opening_debit", 0) or 0)
		opening_credit = float(opening_balances.get(acc_name, {}).get("opening_credit", 0) or 0)
		period_debit = float(period_balances.get(acc_name, {}).get("debit", 0) or 0)
		period_credit = float(period_balances.get(acc_name, {}).get("credit", 0) or 0)

		# Calculate closing balances
		# Closing = Opening + Period (for separate debit/credit columns)
		closing_debit = opening_debit + period_debit
		closing_credit = opening_credit + period_credit

		# If closing balances are both zero, skip (unless account is explicitly selected)
		if closing_debit == 0 and closing_credit == 0 and acc_name not in account_names:
			continue

		parent_acc = parent_account_map.get(acc_name, "")
		parent_name = account_name_map.get(parent_acc, parent_acc) if parent_acc else ""

		# Calculate net balances and split into debit/credit
		opening_balance = opening_debit - opening_credit
		closing_balance = closing_debit - closing_credit

		# Split balances: if positive -> debit, if negative -> credit (absolute value)
		opening_balance_debit = opening_balance if opening_balance > 0 else 0.0
		opening_balance_credit = abs(opening_balance) if opening_balance < 0 else 0.0
		closing_balance_debit = closing_balance if closing_balance > 0 else 0.0
		closing_balance_credit = abs(closing_balance) if closing_balance < 0 else 0.0

		detail_row = {
			"account": acc_name,
			"account_name": account_name_map.get(acc_name, acc_name),
			"parent_account": parent_acc,
			"parent_account_name": parent_name,
			"opening_debit": float(opening_debit),
			"opening_credit": float(opening_credit),
			"opening_balance_debit": float(opening_balance_debit),
			"opening_balance_credit": float(opening_balance_credit),
			"debit": float(period_debit),
			"credit": float(period_credit),
			"closing_debit": float(closing_debit),
			"closing_credit": float(closing_credit),
			"closing_balance_debit": float(closing_balance_debit),
			"closing_balance_credit": float(closing_balance_credit),
		}

		trial_balance_detail.append(detail_row)

		# Aggregate by parent account
		if parent_acc:
			if parent_acc not in trial_balance_parent:
				trial_balance_parent[parent_acc] = {
					"parent_account": parent_acc,
					"parent_account_name": parent_name,
					"opening_debit": 0.0,
					"opening_credit": 0.0,
					"opening_balance_debit": 0.0,
					"opening_balance_credit": 0.0,
					"debit": 0.0,
					"credit": 0.0,
					"closing_debit": 0.0,
					"closing_credit": 0.0,
					"closing_balance_debit": 0.0,
					"closing_balance_credit": 0.0,
				}

			trial_balance_parent[parent_acc]["opening_debit"] = float(
				trial_balance_parent[parent_acc]["opening_debit"]
			) + float(opening_debit)
			trial_balance_parent[parent_acc]["opening_credit"] = float(
				trial_balance_parent[parent_acc]["opening_credit"]
			) + float(opening_credit)
			trial_balance_parent[parent_acc]["opening_balance_debit"] = float(
				trial_balance_parent[parent_acc]["opening_balance_debit"]
			) + float(opening_balance_debit)
			trial_balance_parent[parent_acc]["opening_balance_credit"] = float(
				trial_balance_parent[parent_acc]["opening_balance_credit"]
			) + float(opening_balance_credit)
			trial_balance_parent[parent_acc]["debit"] = float(
				trial_balance_parent[parent_acc]["debit"]
			) + float(period_debit)
			trial_balance_parent[parent_acc]["credit"] = float(
				trial_balance_parent[parent_acc]["credit"]
			) + float(period_credit)
			trial_balance_parent[parent_acc]["closing_debit"] = float(
				trial_balance_parent[parent_acc]["closing_debit"]
			) + float(closing_debit)
			trial_balance_parent[parent_acc]["closing_credit"] = float(
				trial_balance_parent[parent_acc]["closing_credit"]
			) + float(closing_credit)
			trial_balance_parent[parent_acc]["closing_balance_debit"] = float(
				trial_balance_parent[parent_acc]["closing_balance_debit"]
			) + float(closing_balance_debit)
			trial_balance_parent[parent_acc]["closing_balance_credit"] = float(
				trial_balance_parent[parent_acc]["closing_balance_credit"]
			) + float(closing_balance_credit)

	# Convert parent account dict to sorted list
	trial_balance_parent_list = sorted(
		trial_balance_parent.values(), key=lambda x: x.get("parent_account_name", "")
	)

	# ---- Build Distinct Value Sets ----
	company_set = set()
	account_set = set()
	parent_account_set = set()
	root_type_set = set()
	account_type_set = set()

	for acc in accounts_list:
		if acc.get("company"):
			company_set.add(acc["company"])
		if acc.get("name"):
			account_set.add(acc["name"])
		if acc.get("parent_account"):
			parent_account_set.add(acc["parent_account"])
		if acc.get("root_type"):
			root_type_set.add(acc["root_type"])
		if acc.get("account_type"):
			account_type_set.add(acc["account_type"])

	# ---- Return Response ----
	return {
		"trial_balance_detail": trial_balance_detail,
		"trial_balance_parent": trial_balance_parent_list,
		"distinct_values": {
			"companies": sorted(company_set),
			"accounts": sorted(account_set),
			"parent_accounts": sorted(parent_account_set),
			"root_types": sorted(root_type_set),
			"account_types": sorted(account_type_set),
		},
	}
