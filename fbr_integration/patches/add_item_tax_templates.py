import frappe


VALID_TAX_ACCOUNT_TYPES = {
	"Tax",
	"Chargeable",
	"Income Account",
	"Expense Account",
	"Expenses Included In Valuation",
}

TAX_ACCOUNT_PARENT_CANDIDATES = (
	"Duties and Taxes",
	"Tax Payables",
	"Current Liabilities",
	"Liabilities",
)

GST_ACCOUNT_CANDIDATES = (
	"GST",
	"General Sales Tax",
	"Sales Tax",
	"Output Tax",
	"VAT",
)

FURTHER_TAX_ACCOUNT_CANDIDATES = ("Further Tax",)
EXTRA_TAX_ACCOUNT_CANDIDATES = ("Extra Tax",)


def _resolve_company(preferred_name):
	if preferred_name and frappe.db.exists("Company", preferred_name):
		return preferred_name

	companies = frappe.get_all("Company", fields=["name"], order_by="name asc", limit_page_length=1)
	return companies[0].name if companies else preferred_name


def _format_rate(rate):
	if rate is None:
		return "0"

	try:
		rate_value = float(rate)
	except (TypeError, ValueError):
		return str(rate)

	if rate_value.is_integer():
		return str(int(rate_value))

	return f"{rate_value:.8f}".rstrip("0").rstrip(".")


def _get_company_abbr(company):
	return frappe.get_cached_value("Company", company, "abbr") or ""


def _desired_name(title, company):
	abbr = _get_company_abbr(company)
	return f"{title} - {abbr}" if abbr else title


def _find_group_account(company, account_name):
	rows = frappe.get_all(
		"Account",
		filters={"company": company, "account_name": account_name, "is_group": 1},
		fields=["name"],
		limit_page_length=1,
	)
	return rows[0].name if rows else ""


def _resolve_tax_parent(company):
	for parent_name in TAX_ACCOUNT_PARENT_CANDIDATES:
		parent = _find_group_account(company, parent_name)
		if parent:
			return parent

	rows = frappe.get_all(
		"Account",
		filters={"company": company, "root_type": "Liability", "is_group": 1},
		fields=["name"],
		order_by="lft asc",
		limit_page_length=1,
	)
	if rows:
		return rows[0].name

	rows = frappe.get_all(
		"Account",
		filters={"company": company, "is_group": 1},
		fields=["name"],
		order_by="lft asc",
		limit_page_length=1,
	)
	return rows[0].name if rows else ""


def _find_account(company, candidates):
	for account_name in candidates:
		rows = frappe.get_all(
			"Account",
			filters={"company": company, "account_name": account_name},
			fields=["name", "account_type"],
			limit_page_length=1,
		)
		if rows:
			return rows[0].name, rows[0].account_type

		rows = frappe.get_all(
			"Account",
			filters={"company": company, "name": account_name},
			fields=["name", "account_type"],
			limit_page_length=1,
		)
		if rows:
			return rows[0].name, rows[0].account_type

	return "", ""


def _normalize_tax_account(account_name):
	account_type = frappe.db.get_value("Account", account_name, "account_type")
	if account_type in VALID_TAX_ACCOUNT_TYPES:
		return

	frappe.db.set_value("Account", account_name, "account_type", "Tax", update_modified=False)


def _create_tax_account(company, account_name):
	parent_account = _resolve_tax_parent(company)
	if not parent_account:
		frappe.throw(f"Unable to find a liability parent account for {company}")

	doc = frappe.new_doc("Account")
	doc.account_name = account_name
	doc.company = company
	doc.parent_account = parent_account
	doc.account_type = "Tax"
	doc.is_group = 0
	doc.disabled = 0
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return doc.name


def _resolve_tax_account(company, candidates, create_name=None):
	account_name, account_type = _find_account(company, candidates)
	if account_name:
		if account_type not in VALID_TAX_ACCOUNT_TYPES:
			_normalize_tax_account(account_name)
		return account_name

	if create_name:
		return _create_tax_account(company, create_name)

	return ""


def _tax_rows(company, sales_rate, further_rate=0, extra_rate=0):
	rows = []
	sales_tax = _resolve_tax_account(company, GST_ACCOUNT_CANDIDATES, create_name="GST")
	if sales_tax:
		rows.append({"tax_type": sales_tax, "tax_rate": sales_rate})

	if further_rate:
		further_tax = _resolve_tax_account(
			company,
			FURTHER_TAX_ACCOUNT_CANDIDATES,
			create_name="Further Tax",
		)
		if further_tax:
			rows.append({"tax_type": further_tax, "tax_rate": further_rate})

	if extra_rate:
		extra_tax = _resolve_tax_account(
			company,
			EXTRA_TAX_ACCOUNT_CANDIDATES,
			create_name="Extra Tax",
		)
		if extra_tax:
			rows.append({"tax_type": extra_tax, "tax_rate": extra_rate})

	return rows


def _template_spec(
	sn,
	description,
	company,
	sales_rate,
	aliases=None,
	legacy_titles=None,
	further_rate=0,
	extra_rate=0,
):
	rate_label = _format_rate(sales_rate)
	title = f"{sn} - {rate_label}% {description}"
	return {
		"title": title,
		"company": company,
		"sales_rate": sales_rate,
		"further_rate": further_rate,
		"extra_rate": extra_rate,
		"aliases": [title, *(aliases or []), *(legacy_titles or [])],
	}


ITEM_TAX_TEMPLATE_SPECS = [
	_template_spec(
		"SN001",
		"Goods at Standard Rate to Registered Buyers",
		"Logic Layer Pvt Ltd",
		18,
		aliases=["SN001 - Goods at Standard Rate (Registered Buyer)"],
		legacy_titles=["Goods at Standard Rate (Registered Buyer)"],
	),
	_template_spec(
		"SN002",
		"Goods at Standard Rate to Unregistered Buyers",
		"Logic Layer Pvt Ltd",
		18,
		aliases=["SN002 - Goods at Standard Rate (Unregistered Buyer)"],
		legacy_titles=["Goods at Standard Rate (Unregistered Buyer)"],
	),
	_template_spec(
		"SN003",
		"Steel Melting and Re-rolling",
		"Logic Layer Pvt Ltd",
		18,
		legacy_titles=["Steel Melting and Re-rolling"],
	),
	_template_spec(
		"SN004",
		"Ship Breaking",
		"Logic Layer Pvt Ltd",
		18,
		legacy_titles=["Ship Breaking"],
	),
	_template_spec(
		"SN005",
		"Goods at Reduced Rate (Eighth Schedule)",
		"Logic Layer Pvt Ltd",
		1,
		legacy_titles=["Goods at Reduced Rate (Eighth Schedule)"],
		further_rate=12,
	),
	_template_spec(
		"SN006",
		"Exempt Goods (Sixth Schedule)",
		"Logic Layer Pvt Ltd",
		0,
		legacy_titles=["Exempt Goods (Sixth Schedule)"],
		further_rate=12,
	),
	_template_spec(
		"SN007",
		"Zero-Rated Goods",
		"Logic Layer Pvt Ltd",
		0,
		legacy_titles=["Zero-Rated Goods"],
	),
	_template_spec(
		"SN008",
		"Third Schedule Goods (Retail Price Based)",
		"Logic Layer Pvt Ltd",
		18,
		legacy_titles=["Third Schedule Goods (Retail Price Based)"],
	),
	_template_spec("SN009", "Cotton Ginners", "Logic Layer Pvt Ltd", 18, legacy_titles=["Cotton Ginners"]),
	_template_spec(
		"SN010",
		"Telecommunication Services",
		"Logic Layer Pvt Ltd",
		17,
		legacy_titles=["Telecommunication Services"],
	),
	_template_spec("SN011", "Toll Manufacturing", "Logic Layer Pvt Ltd", 18, legacy_titles=["Toll Manufacturing"]),
	_template_spec("SN012", "Petroleum Products", "Logic Layer Pvt Ltd", 1.43, legacy_titles=["Petroleum Products"]),
	_template_spec(
		"SN013",
		"Electricity Supply to Retailers",
		"Logic Layer Pvt Ltd",
		5,
		legacy_titles=["Electricity Supply to Retailers"],
	),
	_template_spec("SN014", "Gas to CNG Stations", "Logic Layer Pvt Ltd", 18, legacy_titles=["Gas to CNG Stations"]),
	_template_spec("SN015", "Mobile Phones", "Logic Layer Pvt Ltd", 18, legacy_titles=["Mobile Phones"]),
	_template_spec(
		"SN016",
		"Processing/Conversion of Goods",
		"Logic Layer Pvt Ltd",
		5,
		legacy_titles=["Processing/Conversion of Goods"],
	),
	_template_spec("SN017", "Goods (FED in ST Mode)", "Logic Layer Pvt Ltd", 8, legacy_titles=["Goods (FED in ST Mode)"]),
	_template_spec(
		"SN018",
		"Services (FED in ST Mode)",
		"Logic Layer Pvt Ltd",
		8,
		legacy_titles=["Services (FED in ST Mode)"],
	),
	_template_spec("SN019", "ICT Services", "Logic Layer Pvt Ltd", 5, legacy_titles=["ICT Services"]),
	_template_spec("SN020", "Electric Vehicles", "Logic Layer Pvt Ltd", 1, legacy_titles=["Electric Vehicles"]),
	_template_spec(
		"SN021",
		"Cement/Concrete Block",
		"Logic Layer Pvt Ltd",
		29.26829268,
		legacy_titles=["Cement/Concrete Block"],
	),
	_template_spec("SN022", "Potassium Chlorate", "Logic Layer Pvt Ltd", 78, legacy_titles=["Potassium Chlorate"]),
	_template_spec("SN023", "CNG Sales", "Logic Layer Pvt Ltd", 10512.82051282, legacy_titles=["CNG Sales"]),
	_template_spec(
		"SN024",
		"Goods as per SRO.297(I)/2023",
		"Logic Layer Pvt Ltd",
		25,
		legacy_titles=["Goods as per SRO.297(I)/2023"],
	),
	_template_spec(
		"SN025",
		"Non-Adjustable Supplies (Pharmaceuticals)",
		"Logic Layer Pvt Ltd",
		0,
		legacy_titles=["Non-Adjustable Supplies (Pharmaceuticals)"],
	),
	_template_spec(
		"SN026",
		"Retailer - Standard Rate Goods",
		"Logic Layer Retail",
		18,
		legacy_titles=["Retailer - Standard Rate Goods"],
	),
	_template_spec(
		"SN027",
		"Retailer - Third Schedule Goods",
		"Logic Layer Retail",
		18,
		legacy_titles=["Retailer - Third Schedule Goods"],
	),
	_template_spec(
		"SN028",
		"Retailer - Reduced Rate Goods",
		"Logic Layer Retail",
		1,
		legacy_titles=["Retailer - Reduced Rate Goods"],
	),
]


def _canonical_titles():
	return {template["title"] for template in ITEM_TAX_TEMPLATE_SPECS}


def _delete_all_item_tax_templates(company):
	for row in frappe.get_all(
		"Item Tax Template",
		filters={"company": company},
		fields=["name"],
		limit_page_length=0,
	):
		if frappe.db.exists("Item Tax Template", row.name):
			frappe.delete_doc("Item Tax Template", row.name, ignore_permissions=True, force=1)


def _create_item_tax_template(company, template):
	doc = frappe.new_doc("Item Tax Template")
	doc.title = template["title"]
	doc.company = company
	doc.disabled = 0

	for row in _tax_rows(
		company,
		template.get("sales_rate", 0),
		further_rate=template.get("further_rate", 0),
		extra_rate=template.get("extra_rate", 0),
	):
		doc.append(
			"taxes",
			{
				"doctype": "Item Tax Template Detail",
				"tax_type": row["tax_type"],
				"tax_rate": row["tax_rate"],
			},
		)

	doc.flags.ignore_permissions = True
	doc.flags.ignore_links = True
	doc.insert(ignore_permissions=True)


def execute():
	company_names = [row.name for row in frappe.get_all("Company", fields=["name"], limit_page_length=0)]

	for company in company_names:
		_delete_all_item_tax_templates(company)

		for template in ITEM_TAX_TEMPLATE_SPECS:
			_create_item_tax_template(company, template)

	frappe.clear_cache(doctype="Item Tax Template")
	frappe.clear_cache(doctype="Account")
