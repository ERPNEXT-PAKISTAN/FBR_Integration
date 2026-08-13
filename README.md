### FBR Integration

FBR Integration for ERPNext — integrates with FBR's Digital Invoicing (DI) system to submit sales invoices directly to FBR.

Works on **Frappe / ERPNext v15 and v16** with one install command. On v16, migrate also creates the Desktop Icon and Workspace Sidebar.

### Requirements

- Frappe + ERPNext (v15 or v16)
- HRMS optional (not required for FBR)

### Installation

Same commands on v15 and v16:

```bash
cd ~/frappe-bench
bench get-app fbr_integration https://github.com/ERPNEXT-PAKISTAN/FBR_Integration.git --branch main
bench --site site1.local install-app fbr_integration
bench --site site1.local migrate
bench build --app fbr_integration
bench restart
```

Then open:

- v15: `/app/fbr-pakistan`
- v16: `/desk/fbr-pakistan` (Desktop Icon is also created)

### Updating an Existing Installation

```bash
cd ~/frappe-bench/apps/fbr_integration
git fetch upstream
git checkout main
git pull upstream main

cd ~/frappe-bench
bench --site site1.local migrate
bench build --app fbr_integration
bench --site site1.local clear-cache
bench restart
```

Important notes:

- Do not run `bench get-app` for an app that is already installed in `apps/fbr_integration`.
- If your repo uses `origin` instead of `upstream`, replace accordingly.
- After API/Python changes on gunicorn `--preload`, use a full `bench restart`.

### Dual version desk notes

| Feature | v15 | v16 |
| --- | --- | --- |
| Workspace | Fixture / module JSON | Same + `type` / `app` / `module` |
| Workspace Sidebar | Not used | Created by `compat.ensure_desk_navigation` |
| Desktop Icon | If schema supports | App icon → FBR workspace |
| In-app links | `/app/...` | Rewritten via `frappe.fbr.desk_path` |

CI runs a matrix against Frappe/ERPNext **version-15** and **version-16**.

Public verification: `/fbr_verify?invoice=<FBR Invoice No>` looks up Sales Invoice by `custom_fbr_invoice_no`.

### Old app ``fbr_e_invoicing`` (removed)

This site previously used **`fbr_e_invoicing`**. That app is **uninstalled and not on disk**.
Its patch `setup_pakistan_tax_accounts_and_item_templates` created ~40 regional
Sales/Purchases Service Tax Item Tax Templates.

**Current `fbr_integration` does not create those.** It only syncs **SN001–SN028**
scenario Item Tax Templates. Migrate patches:

- `cleanup_legacy_item_tax_templates` — delete/disable non-SN leftovers
- `purge_fbr_e_invoicing_remnants` — clear Patch Log / desktop icons / modules from the old app

Do **not** reinstall `fbr_e_invoicing`. Use only `fbr_integration`.

### Sales Tax Withheld at Source

- Optional via **Consider for Tax Withholding** (`apply_tds`) on:
  - **Sales Invoice** (parent) — master switch; off = no WHT / no FBR ST withheld auto-charge
  - **Sales Invoice Item** (child) — per-line switch (now editable); off = skip that line
- Parent is auto-checked on new invoices when Customer has Tax Withholding Category/Group (ERPNext core). Uncheck to skip WHT on that invoice.
- When parent + item are checked: category rate and/or `tax_withholding_entries` fill item `ST Withheld at Source`
- When either is unchecked: that line’s FBR ST withheld fields stay / clear to zero
- Item fields map to FBR `salesTaxWithheldAtSource`
- Install/migrate seeds Tax Withholding Groups/Categories and Chart of Accounts

### Sales Return / Credit Note (FBR fields)

ERPNext `is_return` maps to FBR as follows (DI API):

| FBR JSON field | Value |
| --- | --- |
| `invoiceType` | `Credit Note` (retry as `Debit Note` if gateway rejects type) |
| `invoiceRefNo` | **Original FBR Invoice No** from Return Against / `custom_fbr_source_invoice_no` |
| `reason` | FBR Return Reason / Remarks |

Do **not** put the ERP Sales Invoice name in `invoiceRefNo` — FBR errors `0026` / `0057` mean the reference is missing or not a real FBR invoice number.

### POS → FBR (Digital Invoice)

Desk POS and **X POS** create **Sales Invoice** (`is_pos` + `pos_profile`). **Each POS order = one SI = one FBR DI send.**

1. Complete order → SI submit → auto-send when **FBR Invoice Settings** allow
2. Desk POS shows an FBR dialog (invoice no + QR) and a summary card with **FBR Details** / **Send to FBR**
3. Failures never block checkout; retry from the POS summary / Sales Invoice **Send to FBR**
4. Optional: **Auto Send All Sales Invoices on Submit** for non-POS invoices

### Two different FBR setting places (do not confuse)

| Location | App | Purpose | Turn ON for DI? |
| --- | --- | --- | --- |
| **FBR Invoice Settings** (+ POS Credentials) | `fbr_integration` | FBR **Digital Invoice** (DI) API — `custom_fbr_invoice_no` | **Yes** |
| **POS Profile → FBR / POS Settings tab** (`enable_fbr_integration`, `fbr_pos_id`, token, …) | `xpos` | X POS built-in **IMS** fiscalization — `fbr_invoice_number` | **No** (keep OFF when using this DI app) |

Using **both ON** at once is not recommended: X POS may fiscalize with the old IMS API first, and DI auto-send is skipped when `fbr_invoice_number` is already set.

### FBR Invoice Settings (required for DI)

Path: **FBR Pakistan → FBR Invoice Settings** (or search *FBR Invoice Settings*).

**A) Company / default settings (always configure and keep Enabled ON)**

| Field | Meaning |
| --- | --- |
| **Enabled** | Master switch for DI integration |
| **Integration Type** | `Sandbox` or `Production` |
| **Sandbox / Production API URL** | DI endpoint for that environment |
| **Sandbox / Production Security Token** | Default Bearer token (fallback when a POS has no credential row) |
| **SSL Applied** | When checked, HTTPS certificate verification is on |
| **Auto Send POS Invoices on Submit** | ON = auto-send after POS SI submit (desk POS + X POS) |
| **Auto Send All Sales Invoices on Submit** | Optional for non-POS invoices |

**B) POS Credentials table (required when you have more than one POS)**

Each physical / logical POS needs its **own** FBR registration ID and usually its own token. Add one row per **POS Profile**:

| Column | Meaning |
| --- | --- |
| **Enabled** | ON for that POS |
| **POS Profile** | ERPNext / X POS profile name (e.g. `Model Town`, `Branch 2`) — must match invoice `pos_profile` |
| **FBR POS ID** | Unique FBR POS Registration / POS ID for that terminal |
| **Sandbox Security Token** | Token for this POS in Sandbox |
| **Production Security Token** | Token for this POS in Production |
| **Sandbox / Production API URL** | Optional overrides; blank = use company default URLs above |

Resolution on send:

1. Read `Sales Invoice.pos_profile`
2. If an **enabled** POS Credentials row matches → use that row’s POS ID + token (+ URL if set)
3. Else → fall back to company default token/URL
4. Store used POS ID on the invoice in **FBR POS ID** (`custom_fbr_pos_id`)

Button **Import from POS Profiles** (System Manager): copies `fbr_pos_id` / bearer token from X POS Profile fields into this table (does not overwrite existing rows). After import, turn **OFF** `enable_fbr_integration` on those POS Profiles if you use DI only.

### POS Profile FBR tab (X POS only — optional / separate)

On **POS Profile**, X POS adds fields such as:

| Field | Meaning |
| --- | --- |
| `enable_fbr_integration` | Enables X POS’s own FBR send (IMS API), not this DI app |
| `fbr_environment` | Sandbox / Production for X POS IMS |
| `fbr_pos_id` | POS ID sent as `POSID` in X POS IMS payload |
| `fbr_bearer_token` | Token for X POS IMS API |
| `fbr_api_url` / `fbr_local_service_url` | Cloud / local fiscal service URLs |

**Recommended setup for Digital Invoice + multi POS**

1. **FBR Invoice Settings**: Enabled ON, URLs + default token set, Auto Send POS ON  
2. **POS Credentials**: one enabled row per POS Profile (`Model Town`, …) with unique **FBR POS ID** + tokens  
3. **POS Profile** `enable_fbr_integration`: **OFF** for every profile used with DI  
4. Ensure each sale’s invoice has the correct **POS Profile** name so the matching credential row is selected  

### Scenario Files

The authoritative FBR scenario source is kept in `fbr_integration/scenario_data/source/`:

- `DI_Scenarios_Summary.txt` — JSON payloads with scenario descriptions

Rebuild:

```bash
cd ~/frappe-bench/apps/fbr_integration
python3 fbr_integration/scenario_data/build_scenario_docs.py
# or: fbr-build-scenarios
```

### Contributing

This app uses `pre-commit` for code formatting and linting:

```bash
cd apps/fbr_integration
pre-commit install
```

### License

mit
