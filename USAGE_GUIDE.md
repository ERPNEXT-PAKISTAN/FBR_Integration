# FBR Integration - Usage Guide

## Overview

The FBR Integration app provides a complete workflow for managing and applying FBR scenarios to sales invoices. This guide covers all features and troubleshooting.

---

## 1. Quick Start: Using Scenarios on Sales Invoice

### Step 1: Open a Sales Invoice
Navigate to **Selling → Sales Invoice** or search for "Sales Invoice" in the Awesome bar (Ctrl+K).

### Step 2: Click "Scenario Index" Button
On any Sales Invoice form, you'll see a **"Scenario Index"** button in the top right action area.

```
┌─────────────────────────────────────────┐
│  [Scenario Index]  [View Scenario]      │  ← Look for these buttons
│  [FBR]  [Send to FBR]                   │
└─────────────────────────────────────────┘
```

### Step 3: Search for a Scenario
A dialog opens showing all 28 available FBR scenarios:

```
╔════════════════════════════════════════════╗
║         Scenario Index                     ║
╠════════════════════════════════════════════╣
║ Search: [_______________]                  │
║                                            │
║ SN001 - Goods at Standard Rate             │
║ (Registered Buyer)                        │
║ This applies to the sale of goods subject  │
║ to the standard 18% sales tax rate...      │
║  [View]  [Use]                             │
║                                            │
║ SN002 - Goods at Standard Rate             │
║ (Unregistered Buyer)                      │
║ ...                                        │
║  [View]  [Use]                             │
╚════════════════════════════════════════════╝
```

### Step 4: Choose Your Scenario

**Option A: Search for a specific scenario**
- Type in the search box: "steel", "cement", "retail", "export", etc.
- Results filter in real-time by ID, title, and description
- Example searches:
  - Type "standard" → shows SN001, SN002, SN026, SN027, SN028
  - Type "SN024" → shows only SN024 (Goods as per SRO.297)
  - Type "telecom" → shows SN010

**Option B: Browse and click "Use"**
- Scroll through all scenarios
- Click the **[Use]** button on the one you want
- The dialog closes automatically
- The scenario is now set on your invoice

### Step 5: Confirm Selection
After clicking [Use], you'll see:
- Green alert: "Scenario selected: SN001"
- The `custom_scenario_id` field is populated with your choice
- You can now submit the invoice to FBR

---

## 2. Viewing Scenario Details

### From Scenario Index Dialog
While the Scenario Index dialog is open:
1. Find a scenario
2. Click **[View]** button
3. A new popup opens showing the **full scenario details**:

```
╔════════════════════════════════════════════╗
║  Scenario Detail: SN001                    ║
╠════════════════════════════════════════════╣
║  [SN001] Goods at Standard Rate            ║
║                                            ║
║  This applies to the sale of goods...      ║
║                                            ║
║  Sample Payload                            ║
║  ┌──────────────────────────────────────┐  │
║  │{                                      │  │
║  │  "invoiceType": "Sale Invoice",      │  │
║  │  "invoiceDate": "2026-05-10",        │  │
║  │  "scenarioId": "SN001",              │  │
║  │  "buyerRegistrationType": "Regist..} │  │
║  └──────────────────────────────────────┘  │
╚════════════════════════════════════════════╝
```

### Direct View (After Selection)
Once a scenario is selected on the invoice:
1. The **[View Scenario]** button appears
2. Click it to see the same detail popup
3. Use this to verify your selection

---

## 3. All 28 Scenarios at a Glance

| ID | Title | Use Case |
|-------|-------|----------|
| **SN001** | Goods at Standard Rate (Registered) | Standard 18% to registered buyer |
| **SN002** | Goods at Standard Rate (Unregistered) | Standard 18% to end consumer |
| **SN003** | Steel Melting and Re-rolling | Steel sector sales |
| **SN004** | Ship Breaking | Scrap steel from ship breaking |
| **SN005** | Goods at Reduced Rate (8th Schedule) | Essential items at reduced rate |
| **SN006** | Exempt Goods (6th Schedule) | Medical, books, etc. |
| **SN007** | Zero-Rated Goods | Exports at 0% |
| **SN008** | 3rd Schedule Goods (Retail Price) | Tax on MRP not transaction value |
| **SN009** | Cotton Ginners | Cotton trade specific |
| **SN010** | Telecom Services | Mobile/telecom services |
| **SN011** | Toll Manufacturing | Third-party processing services |
| **SN012** | Petroleum Products | Petrol, diesel, etc. |
| **SN013** | Electricity Supply to Retailers | Power distribution |
| **SN014** | Gas to CNG Stations | CNG fuel sales |
| **SN015** | Mobile Phones | Handset sales |
| **SN016** | Processing/Conversion of Goods | Manufacturing services |
| **SN017** | Goods (FED in ST Mode) | Federal excise collected via ST |
| **SN018** | Services (FED in ST Mode) | Consulting, franchise, ads |
| **SN019** | ICT Services | Software, IT services |
| **SN020** | Electric Vehicles | EV incentive at 1% |
| **SN021** | Cement/Concrete Blocks | Construction materials |
| **SN022** | Potassium Chlorate | Chemical for matchsticks |
| **SN023** | CNG Sales | CNG retail sales |
| **SN024** | Goods as per SRO.297(I)/2023 | Special regulated goods |
| **SN025** | Pharmaceuticals (Non-Adjustable) | Fixed-rate medicines |
| **SN026** | Retailer - Standard Rate Goods | POS integrated retailer |
| **SN027** | Retailer - 3rd Schedule Goods | Retail with MRP tax |
| **SN028** | Retailer - Reduced Rate Goods | Essential goods retail |

---

## 4. Troubleshooting

### Problem: "Scenario Index" button is missing
**Cause:** App not installed or cache not cleared

**Solution:**
```bash
cd ~/frappe-bench
bench --site site1.local clear-cache
bench restart
# Reload browser page: Ctrl+Shift+R (hard refresh)
```

### Problem: Dialog shows "Scenario Index Not Available"
**Cause:** Scenario catalog failed to load

**Steps:**
1. **Check browser console (F12):**
   - Look for lines starting with `[FBR]`
   - Note any error messages

2. **Rebuild scenarios:**
   ```bash
   cd ~/frappe-bench/apps/fbr_integration
   fbr-build-scenarios
   # Or: python3 fbr_integration/scenario_data/build_scenario_docs.py
   ```

3. **Rebuild assets:**
   ```bash
   cd ~/frappe-bench
   bench build --app fbr_integration
   ```

4. **Clear cache and restart:**
   ```bash
   bench --site site1.local clear-cache
   bench restart
   ```

5. **Hard refresh browser:**
   - Press Ctrl+Shift+R (not just F5)

### Problem: No scenarios appear in search results
**Solution:**
1. Clear search box and try again
2. Use browser console:
   ```javascript
   clear_fbr_scenario_cache()
   // Then reload the form
   ```

### Problem: "View Scenario" shows wrong scenario
**Solution:**
1. Clear the cache:
   ```javascript
   // In browser console (F12):
   clear_fbr_scenario_cache()
   ```
2. Close and reopen the form

---

## 5. For Administrators: Rebuilding Scenarios

### When to Rebuild
- After editing the scenario source file
- After updating the app from GitHub
- After migration to a new server

### Rebuild Command
```bash
cd ~/frappe-bench/apps/fbr_integration
fbr-build-scenarios
```

**Output (success):**
```
Building FBR scenario catalog...
Source file size: 33576 bytes
✓ Parsed 28 scenarios
✓ Wrote 28 scenario documents
✓ Generated index catalog

Build successful: 28 FBR scenarios ready for deployment
```

**If there's an error:**
```bash
# Use verbose Python command to see details
python3 fbr_integration/scenario_data/build_scenario_docs.py
```

### After Rebuild
```bash
cd ~/frappe-bench
bench build --app fbr_integration
bench --site site1.local clear-cache
bench restart
```

---

## 6. Advanced: Browser Console Commands

Open browser console with **F12** and run:

### Refresh Scenario Cache
```javascript
clear_fbr_scenario_cache()
console.log("Cache cleared. Reload the form.")
```

### Check What's Cached
```javascript
console.log(fbrScenarioIndexCache)
```

### Check If There Was an Error
```javascript
console.log(fbrScenarioIndexError)
```

### Manual Scenario Load
```javascript
load_scenario_index().then(scenarios => {
  console.log("Loaded scenarios:", scenarios)
}).catch(err => {
  console.error("Failed to load:", err)
})
```

---

## 7. Updating the App

### Pull Latest Changes
```bash
cd ~/frappe-bench
bench get-app fbr_integration https://github.com/ERPNEXT-PAKISTAN/FBR_Integration.git --branch main
# Or if already installed:
cd ~/frappe-bench/apps/fbr_integration
git pull origin main
```

### Deploy
```bash
cd ~/frappe-bench
bench --site site1.local migrate
bench build --app fbr_integration
bench --site site1.local clear-cache
bench restart
```

### Verify
Open Sales Invoice form → click "Scenario Index" → check that all 28 scenarios load.

---

## 8. Common Workflows

### Workflow 1: New Sales Invoice (Standard Rate)
1. Create new Sales Invoice
2. Enter customer and items
3. Click **[Scenario Index]**
4. Search: "standard registered" → Click [Use] on SN001
5. Fill remaining FBR fields
6. Submit
7. Click **[Send to FBR]** button

### Workflow 2: Export Sale
1. Create Sales Invoice with export items
2. Click **[Scenario Index]**
3. Type "zero" in search → Select SN007
4. Complete invoice details
5. Submit and send to FBR

### Workflow 3: Retail POS Sale
1. Create Sales Invoice
2. Click **[Scenario Index]**
3. Filter: "retailer" → Choose SN026 (standard) or SN027 (FMCG with MRP) or SN028 (reduced rate)
4. Submit

### Workflow 4: Service Invoice (IT/Software)
1. Create Sales Invoice with service items
2. Click **[Scenario Index]**
3. Search: "ICT" or "software" → Select SN019
4. Submit and send to FBR

---

## 9. File Structure Reference

**Source files:**
```
fbr_integration/scenario_data/source/
├── DI_Scenarios_Summary.txt          # Authoritative source (28 scenarios)
```

**Generated files:**
```
fbr_integration/public/scenario_docs/
├── index.json                         # Searchable catalog
├── SN001.json                         # Individual scenario details
├── SN002.json
├── ... (SN003-SN028)
```

**Build utility:**
```
fbr_integration/scenario_data/
├── build_scenario_docs.py             # Rebuild script (run: fbr-build-scenarios)
```

---

## 10. Support & Debugging Checklist

Use this if scenarios aren't working:

- [ ] Scenario Index button appears on Sales Invoice form
- [ ] Clicking it opens a dialog (not an error)
- [ ] At least one scenario shows in the list
- [ ] Search box filters scenarios in real-time
- [ ] Clicking [View] shows scenario details
- [ ] Clicking [Use] sets the custom_scenario_id field
- [ ] After reload, [View Scenario] button appears when scenario is selected
- [ ] Browser console (F12) has no red errors starting with `[FBR]`
- [ ] `fbr-build-scenarios` command runs without errors
- [ ] `fbr-build-scenarios` output shows "✓ Parsed 28 scenarios"

If any fails:
1. Run rebuild: `fbr-build-scenarios`
2. Rebuild assets: `bench build --app fbr_integration`
3. Clear cache: `bench --site site1.local clear-cache`
4. Restart: `bench restart`
5. Hard refresh: Ctrl+Shift+R

---

## Quick Reference Card

| Task | Command |
|------|---------|
| Use scenario on invoice | Click [Scenario Index] → Search → Click [Use] |
| View scenario details | Click [View Scenario] or [View] in dialog |
| Clear cache | Press F12, run: `clear_fbr_scenario_cache()` |
| Rebuild scenarios | Run: `fbr-build-scenarios` |
| Deploy rebuild | `bench build --app fbr_integration` |
| Verify app works | Open Sales Invoice → click [Scenario Index] |
| Check for errors | Press F12 → look for `[FBR]` in console |

---

**Happy invoicing! 🚀**
