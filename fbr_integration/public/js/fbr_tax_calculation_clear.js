frappe.ui.form.on("Sales Invoice Item", {
  qty(frm, cdt, cdn) { recalc(frm, cdt, cdn); },
  rate(frm, cdt, cdn) { recalc(frm, cdt, cdn); },
  item_tax_template(frm, cdt, cdn) { recalc(frm, cdt, cdn); },
});

function setv(cdt, cdn, field, value) {
  frappe.model.set_value(cdt, cdn, field, value || 0);
}

function matches(tt, keys) {
  return keys.some(k => tt.includes(k));
}

function recalc(frm, cdt, cdn) {
  const row = locals[cdt][cdn];
  const qty = parseFloat(row.qty) || 0;
  const rate = parseFloat(row.rate) || 0;
  const amount = qty * rate;

  setv(cdt, cdn, "amount", amount);

  setv(cdt, cdn, "custom_sales_tax_rate", 0);
  setv(cdt, cdn, "custom_further_tax_rate", 0);
  setv(cdt, cdn, "custom_extra_tax_rate", 0);

  setv(cdt, cdn, "custom_sales_tax", 0);
  setv(cdt, cdn, "custom_further_tax", 0);
  setv(cdt, cdn, "custom_extra_tax", 0);

  setv(cdt, cdn, "custom_total_tax_amount", 0);
  setv(cdt, cdn, "custom_tax_inclusive_amount", amount);

  if (!row.item_tax_template) {
    frm.refresh_field("items");
    return;
  }

  frappe.call({
    method: "fbr_integration.api.get_item_tax_template_rates",
    args: { template_name: row.item_tax_template },
    callback: function (r) {
      const res = r.message || [];
      if (!res.length) {
        frm.refresh_field("items");
        return;
      }

      let salesRate = 0, furtherRate = 0, extraRate = 0;

      res.forEach(tax => {
        const tt = (tax.tax_type || "").toLowerCase();
        const rr = tax.tax_rate || 0;

        if (matches(tt, ["general sales tax", "sales tax", "gst", "output tax", "vat"])) salesRate = rr;
        else if (matches(tt, ["further tax"])) furtherRate = rr;
        else if (matches(tt, ["extra tax"])) extraRate = rr;
      });

      if (res.length === 1 && salesRate === 0) salesRate = res[0].tax_rate || 0;

      const sales = (amount * salesRate) / 100;
      const further = (amount * furtherRate) / 100;
      const extra = (amount * extraRate) / 100;

      setv(cdt, cdn, "custom_sales_tax_rate", salesRate);
      setv(cdt, cdn, "custom_further_tax_rate", furtherRate);
      setv(cdt, cdn, "custom_extra_tax_rate", extraRate);

      setv(cdt, cdn, "custom_sales_tax", sales);
      setv(cdt, cdn, "custom_further_tax", further);
      setv(cdt, cdn, "custom_extra_tax", extra);

      const totalTax = sales + further + extra;
      setv(cdt, cdn, "custom_total_tax_amount", totalTax);
      setv(cdt, cdn, "custom_tax_inclusive_amount", amount + totalTax);

      frm.refresh_field("items");
    }
  });
}