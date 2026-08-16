TAX_BASIS_SALES_VALUE = "Sales Value"
TAX_BASIS_RETAIL_PRICE = "Retail Price / MRP"
TAX_BASIS_FIXED_NOTIFIED = "Fixed / Notified Value"
TAX_BASIS_MANUAL = "Manual Taxable Value"

TAX_CALCULATION_BASES = (
	TAX_BASIS_SALES_VALUE,
	TAX_BASIS_RETAIL_PRICE,
	TAX_BASIS_FIXED_NOTIFIED,
	TAX_BASIS_MANUAL,
)

DEFAULT_RETAIL_PRICE_LIST = "FBR Retail Price"

SALE_TYPE_THIRD_SCHEDULE = "3rd Schedule Goods"
SALE_TYPE_STANDARD = "Goods at standard rate (default)"
SALE_TYPE_ZERO_RATE = "Goods at Zero-Rate"
SALE_TYPE_EXEMPT = "Exempt goods"
SALE_TYPE_REDUCED = "Goods at Reduced Rate"
SALE_TYPE_FIXED_NOTIFIED = "Fixed or Notified Value or Retail Price"

COMPONENT_SALES_TAX = "sales_tax"
COMPONENT_FURTHER_TAX = "further_tax"
COMPONENT_EXTRA_TAX = "extra_tax"
COMPONENT_FED = "fed"

SNAPSHOT_FIELDS = (
	"custom_fbr_tax_profile",
	"custom_fbr_tax_calculation_basis",
	"custom_fbr_retail_price",
	"custom_fbr_fixed_notified_value",
	"custom_fbr_taxable_value",
)

PROFILE_COPY_FIELDS = (
	"custom_sale_type",
	"custom_sro_schedule_no",
	"custom_sro_item_sno",
)
