# Provenance of the real-world invoice formats

Every document in the real-world split is printed through one of seven invoice print formats published by real accounting or billing software under an open-source licence.
None of them comes from this repo's Jinja templates (`gst_recon/render/templates/`).
The upstream files are vendored unchanged in `formats/vendor/` (checksums in `formats/vendor/SHA256SUMS`); their licences (GPL-3.0, LGPL-3.0, MIT) allow copying, modification and redistribution, and this repo is published under GPL-3.0 (`LICENSE` at the root), which is compatible with all three; upstream copyright and licence notices are kept.

## Formats used

| Format id | Upstream project | Licence | Upstream file @ commit | Method | Docs |
|---|---|---|---|---|---|
| `ic_e_invoice` | [resilient-tech/india-compliance](https://github.com/resilient-tech/india-compliance) (the GST app for ERPNext/Frappe) | GPL-3.0 | `india_compliance/gst_india/print_format/e_invoice/e_invoice.html` + `.css` @ `f0c6bec` | original | 6 |
| `ic_pos_invoice` | resilient-tech/india-compliance | GPL-3.0 | `india_compliance/gst_india/print_format/gst_pos_invoice/gst_pos_invoice.json` (field `html`) @ `f0c6bec` | original | 3 |
| `ic_gst_tax_invoice` | resilient-tech/india-compliance | GPL-3.0 | `india_compliance/gst_india/print_format/gst_tax_invoice/gst_tax_invoice.json` (Print Format Builder) @ `f0c6bec` | port | 5 |
| `odoo_l10n_in_invoice` | [odoo/odoo](https://github.com/odoo/odoo) 18.0, `l10n_in` (Indian localisation) | LGPL-3.0 | `addons/l10n_in/views/report_invoice.xml` @ `60fdb53` | port | 10 |
| `billgst_invoice` | [ghoshbishakh/billgst](https://github.com/ghoshbishakh/billgst) (Django GST billing app) | GPL-3.0 | `gstbillingapp/templates/gstbillingapp/invoice_printer.html` @ `9a45e01` | port | 3 |
| `technodweep_tax_invoice` | [technodweep/gst-invoice](https://github.com/technodweep/gst-invoice) (Yii2 GST invoicing app) | MIT | `views/invoice-order/print.php` @ `dcce9b6` | port | 4 |
| `fgb_classic` | [IamRamgarhia/Free-GST-Billing-Software](https://github.com/IamRamgarhia/Free-GST-Billing-Software) (actively maintained desktop GST billing app) | MIT | `src/components/InvoicePreview.jsx` (classic A4 layout) @ `f96be46` | port | 5 |

Methods:
- **original**: the upstream template file itself is rendered with Jinja; only the framework objects it calls are shimmed (`frappe.db.get_value` returns the e-invoice JSON, `doc.get_formatted`, `frappe.utils.fmt_money`, `get_qr_code`, the field-label maps copied from `india_compliance/gst_india/utils/jinja.py`). Frappe's print stylesheet is approximated in `formats/_frappe_print.css` and `_frappe_pos.css`.
- **port**: the upstream markup, labels, field order and inline CSS re-expressed as a standalone Jinja template in `formats/<id>.html.j2` (Django, QWeb, PHP and JSX syntax translated; framework CSS approximated). Each template's header comment lists what was kept and what was changed.

Format quirks kept on purpose, because real documents have them:
- The e-invoice print shows the IRN, Ack No and Ack Date but not the invoice date, and no per-line tax amounts.
- The POS receipt prints no buyer details below Rs 50,000, no place of supply, and the item rate and quantity as raw floats ("@ 280.0").
- The ERPNext tax invoice prints the supplier GSTIN only at the foot ("Our GSTIN"), and no supplier address.
- The technodweep invoice prints the supplier GSTIN and PAN only in the footer, always prints all three "Add CGST/SGST/IGST (x%)" rows, and draws a fully ruled item table.
- The Free-GST-Billing interstate header row has only "#, Description, Amt" while the body rows keep all their cells (an upstream rendering quirk at that commit).
- Odoo prints "Reversal of: <invoice>" as the credit note reference and an HSN Summary table.
- The rupee sign is rendered from the bundled Kalam font (the bundled Liberation fonts lack U+20B9); Tesseract reads it as `¥`, `F`, `%` or a leading `2`, as it does on real scans.

Changes made to every format: all parties are synthetic (`parties.json`), so no real GSTIN, PAN, name or address appears.
The technodweep upstream view hardcodes one firm's name in its signature block ("For ... rubber products"); it is replaced by the synthetic supplier, and a one-line letterhead is added because the upstream view expects pre-printed stationery.
The e-invoice QR is a JWT-shaped string whose issuer reads `SYNTHETIC (not NIC)` and whose signature is `SYNTHETIC-UNSIGNED`; it does not validate on the NIC verifier app.

## Sources evaluated and not used

| Source | Why not used |
|---|---|
| Vendor sample invoices and templates (TaxHeal sample pages, Zoho Invoice / Zoho Books format pages, Vyapar format pages) | TaxHeal pages say "All rights reserved" with no reuse grant; the Zoho and Vyapar format URLs returned 404 at fetch time and no reuse licence was found. Tally, ClearTax and myBillBook samples were not pursued for the same reason (marketing content, no reuse licence). |
| `certtest.bart.gov/download/simple-invoice-india/*` (claims "CC BY 4.0, TemplateNest Media") | Spam mirror on an unrelated domain; the licence cannot be verified. |
| NIC e-invoice sample QR (`einvoice1-trial.nic.in/Documents/Qr`) | No reuse terms found; our own synthetic QR is generated instead. |
| Wikimedia Commons, Hugging Face datasets | No GST invoice images or datasets with a usable licence found (Commons search returned court judgments only). |
| jino-shaji/jsPDF-GST-Invoice | No licence. |
| yogendra-08/LocalBill-GST-Invoice-Maker (MIT) | Its PDF has no GSTIN, invoice number or HSN, so it is not a GST tax invoice. |
| prithwirajbose/gst-invoice (GPL-3.0) | The print view is assembled client-side across PHP partials; not isolated in the time available. |
| india-compliance `gst_purchase_invoice` | A buyer-side document, not a supplier invoice. |
