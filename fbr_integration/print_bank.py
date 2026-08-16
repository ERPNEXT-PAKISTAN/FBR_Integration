"""Always print the requested Meezan payment details on FBR invoices."""

DEFAULT_BANK = {
	"account_name": "ML 88",
	"iban": "1010122255555",
	"bank": "Meezan Bank",
}


def get_bank_payment_info(company=None):
	return dict(DEFAULT_BANK)
