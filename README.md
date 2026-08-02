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

### Sales Tax Withheld at Source

- Item fields `ST Withheld Rate %` / `ST Withheld at Source` map to FBR `salesTaxWithheldAtSource`
- Install/migrate seeds Tax Withholding Groups/Categories and Chart of Accounts:
  - `ST Withheld - X% (FBR)` under group **FBR Sales Tax Withheld at Source**
  - `WH TAX - X% (Sales)` and `Withholding Tax - X% (Purchases)`
- Assign an `ST Withheld - X% (FBR)` category on Customer (or item row) to auto-fill rates

### POS → FBR

This site’s POS Settings create **Sales Invoice** (`is_pos`). Best path (implemented):

1. POS completes order → SI submit (`is_pos` kept on)
2. **FBR Invoice Settings → Auto Send POS Invoices on Submit** (default on) sends to FBR
3. Failures never block checkout; use **Send to FBR** to retry
4. Optional: **Auto Send All Sales Invoices on Submit** for non-POS invoices

Do **not** send only from consolidated POS Invoice merge logs if you later switch POS Settings to POS Invoice mode — each fiscal sale needs its own FBR invoice.

### FBR Invoice Settings

- Enable integration and choose Sandbox or Production
- Set API URL + security token
- **SSL Applied**: when checked, HTTPS certificate verification is enabled for FBR calls

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
