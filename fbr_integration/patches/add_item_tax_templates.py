import frappe


def _tax_rows(company, sales_rate, further_rate=0, extra_rate=0):
	rows = []
	sales_tax = _ensure_tax_account(company, "FBR Sales Tax")
	if sales_tax:
		rows.append({"tax_type": sales_tax, "tax_rate": sales_rate})

	if further_rate:
		further_tax = _ensure_tax_account(company, "FBR Further Tax")
		if further_tax:
			rows.append({"tax_type": further_tax, "tax_rate": further_rate})

	if extra_rate:
		extra_tax = _ensure_tax_account(company, "FBR Extra Tax")
		if extra_tax:
			rows.append({"tax_type": extra_tax, "tax_rate": extra_rate})

	return rows


def _resolve_company(preferred_name):
	if preferred_name and frappe.db.exists("Company", preferred_name):
		return preferred_name

	companies = frappe.get_all("Company", fields=["name"], order_by="name asc", limit_page_length=1)
	return companies[0].name if companies else preferred_name


def _resolve_tax_group(company):
	group = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": "Duties and Taxes", "is_group": 1},
		"name",
	)
	if group:
		return group

	group = frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Tax", "is_group": 1},
		"name",
	)
	if group:
		return group

	frappe.throw(f"Could not find a tax group account for company {company}")


def _ensure_tax_account(company, account_name):
	existing = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": account_name, "is_group": 0},
		"name",
	)
	if existing:
		return existing

	parent_account = _resolve_tax_group(company)
	currency = frappe.get_cached_value("Company", company, "default_currency")

	account = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": account_name,
			"company": company,
			"parent_account": parent_account,
			"account_type": "Tax",
			"is_group": 0,
			"account_currency": currency,
		}
	)
	account.flags.ignore_mandatory = True
	account.flags.ignore_permissions = True
	account.flags.ignore_links = True
	account.insert(ignore_permissions=True)
	return account.name


ITEM_TAX_TEMPLATE_SPECS = [
	{
		"name": "SN001 - Goods at Standard Rate (Registered Buyer)",
		"title": "Goods at Standard Rate (Registered Buyer)",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 18,
	},
	{
		"name": "SN002 - Goods at Standard Rate (Unregistered Buyer)",
		"title": "Goods at Standard Rate (Unregistered Buyer)",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 18,
	},
	{
		"name": "SN003 - Steel Melting and Re-rolling",
		"title": "Steel Melting and Re-rolling",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 18,
	},
	{
		"name": "SN004 - Ship Breaking",
		"title": "Ship Breaking",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 18,
	},
	{
		"name": "SN005 - Goods at Reduced Rate (Eighth Schedule)",
		"title": "Goods at Reduced Rate (Eighth Schedule)",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 1,
		"further_rate": 12,
	},
	{
		"name": "SN006 - Exempt Goods (Sixth Schedule)",
		"title": "Exempt Goods (Sixth Schedule)",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 0,
		"further_rate": 12,
	},
	{
		"name": "SN007 - Zero-Rated Goods",
		"title": "Zero-Rated Goods",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 0,
	},
	{
		"name": "SN008 - Third Schedule Goods (Retail Price Based)",
		"title": "Third Schedule Goods (Retail Price Based)",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 18,
	},
	{
		"name": "SN009 - Cotton Ginners",
		"title": "Cotton Ginners",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 18,
	},
	{
		"name": "SN010 - Telecommunication Services",
		"title": "Telecommunication Services",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 17,
	},
	{
		"name": "SN011 - Toll Manufacturing",
		"title": "Toll Manufacturing",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 18,
	},
	{
		"name": "SN012 - Petroleum Products",
		"title": "Petroleum Products",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 1.43,
	},
	{
		"name": "SN013 - Electricity Supply to Retailers",
		"title": "Electricity Supply to Retailers",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 5,
	},
	{
		"name": "SN014 - Gas to CNG Stations",
		"title": "Gas to CNG Stations",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 18,
	},
	{
		"name": "SN015 - Mobile Phones",
		"title": "Mobile Phones",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 18,
	},
	{
		"name": "SN016 - Processing/Conversion of Goods",
		"title": "Processing/Conversion of Goods",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 5,
	},
	{
		"name": "SN017 - Goods (FED in ST Mode)",
		"title": "Goods (FED in ST Mode)",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 8,
	},
	{
		"name": "SN018 - Services (FED in ST Mode)",
		"title": "Services (FED in ST Mode)",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 8,
	},
	{
		"name": "SN019 - ICT Services",
		"title": "ICT Services",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 5,
	},
	{
		"name": "SN020 - Electric Vehicles",
		"title": "Electric Vehicles",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 1,
	},
	{
		"name": "SN021 - Cement/Concrete Block",
		"title": "Cement/Concrete Block",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 29.26829268,
	},
	{
		"name": "SN022 - Potassium Chlorate",
		"title": "Potassium Chlorate",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 78,
	},
	{
		"name": "SN023 - CNG Sales",
		"title": "CNG Sales",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 10512.82051282,
	},
	{
		"name": "SN024 - Goods as per SRO.297(I)/2023",
		"title": "Goods as per SRO.297(I)/2023",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 25,
	},
	{
		"name": "SN025 - Non-Adjustable Supplies (Pharmaceuticals)",
		"title": "Non-Adjustable Supplies (Pharmaceuticals)",
		"company": "Logic Layer Pvt Ltd",
		"sales_rate": 0,
	},
	{
		"name": "SN026 - Retailer - Standard Rate Goods",
		"title": "Retailer - Standard Rate Goods",
		"company": "Logic Layer Retail",
		"sales_rate": 18,
	},
	{
		"name": "SN027 - Retailer - Third Schedule Goods",
		"title": "Retailer - Third Schedule Goods",
		"company": "Logic Layer Retail",
		"sales_rate": 18,
	},
	{
		"name": "SN028 - Retailer - Reduced Rate Goods",
		"title": "Retailer - Reduced Rate Goods",
		"company": "Logic Layer Retail",
		"sales_rate": 1,
	},
]


def _upsert_item_tax_template(template):
	company = _resolve_company(template["company"])
	existing = frappe.db.get_value(
		"Item Tax Template",
		{"title": template["title"], "company": company},
		"name",
	)

	if existing:
		item_tax_template = frappe.get_doc("Item Tax Template", existing)
	else:
		item_tax_template = frappe.new_doc("Item Tax Template")

	item_tax_template.title = template["title"]
	item_tax_template.company = company
	item_tax_template.disabled = 0
	item_tax_template.set("taxes", [])

	for row in _tax_rows(
		company,
		template.get("sales_rate", 0),
		further_rate=template.get("further_rate", 0),
		extra_rate=template.get("extra_rate", 0),
	):
		item_tax_template.append(
			"taxes",
			{
				"doctype": "Item Tax Template Detail",
				"tax_type": row["tax_type"],
				"tax_rate": row["tax_rate"],
			},
		)

	item_tax_template.flags.ignore_links = True

	if existing:
		item_tax_template.save(ignore_permissions=True, ignore_version=True)
	else:
		item_tax_template.insert(ignore_permissions=True)


def execute():
	for template in ITEM_TAX_TEMPLATE_SPECS:
		_upsert_item_tax_template(template)

	frappe.clear_cache(doctype="Item Tax Template")
