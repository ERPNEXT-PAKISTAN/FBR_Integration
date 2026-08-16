# Changelog

## Unreleased

### Universal FBR Tax Profiles

- Added **FBR Tax Profile** so tax treatment is per item, not per company.
- Third Schedule goods charge GST on printed retail price / MRP × quantity while ERPNext `rate` and `amount` stay the commercial sale.
- FBR JSON `fixedNotifiedValueOrRetailPrice` for Third Schedule is the **line** MRP (unit × qty) so sandbox error 0102 matches `field × rate`.
- Added print formats **FBR Sales Invoice 3rd Schedule** and **FBR Letterhead-2 3rd Schedule** (MRP and FBR taxable columns).
- All FBR invoice print formats show Bank Account for Payment on one line per field: Account Name ML 88, IBAN 1010122255555, Bank Name Meezan Bank.
- Mixed invoices (standard, Third Schedule, zero-rated, exempt, reduced-rate, fixed/notified value) calculate each row independently.
- MRP is read from the **FBR Retail Price** Item Price list, then Item fallback, and snapshotted on Sales Invoice Item / POS Invoice Item so history does not change when masters change.
- Sales Invoice, POS Invoice, and returns share one server-side tax engine. POS selling price is not replaced with MRP.
- Returns copy the original snapshot (including the MRP used on the source invoice).
- Existing installs with no tax profile keep previous tax and FBR JSON behavior.

