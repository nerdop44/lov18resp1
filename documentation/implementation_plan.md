# Tagging Modules for Better Grouping

The goal is to add a common identifier `[LocVe]` to all localization modules to facilitate searching and grouping within Odoo's "Apps" menu.

## Proposed Changes

### [Component] [pos_show_dual_currency](file:///home/nerdop/laboratorio/LocVe18v2/pos_show_dual_currency)

#### [MODIFY] [res_config_settings.xml](file:///home/nerdop/laboratorio/LocVe18v2/pos_show_dual_currency/views/res_config_settings.xml)
- Update fragile XPath to a more robust one targeting the `pos_set_maximum_difference` field. [DONE]

#### [MODIFY] [report_saledetails.xml](file:///home/nerdop/laboratorio/LocVe18v2/pos_show_dual_currency/views/report_saledetails.xml)
- Update `inherit_id` to `point_of_sale.pos_session_sales_details`.
- Adjust XPaths to target the new nested structure (grouping by category).
- Update `t-esc` to `t-out` to match Odoo 18 standard.
- Restore the dual currency display for products, payments, taxes, and totals.

#### [MODIFY] [pos_order.py](file:///home/nerdop/laboratorio/LocVe18v2/pos_show_dual_currency/reports/pos_order.py) [NEW PHASE]
- Refactor `update_key_values_data` to return products grouped by category, matching the Odoo 18 structure.
- Update `get_sale_details` to recursively add `price_unit_ref` to nested product lists.
- Ensure `total_paid_ref`, `symbol_ref`, and `rate_today` are correctly injected.

### [Component] [account_dual_currency](file:///home/nerdop/laboratorio/LocVe18v2/account_dual_currency)

#### [MODIFY] [account_move_view.xml](file:///home/nerdop/laboratorio/LocVe18v2/account_dual_currency/views/account_move_view.xml)
- Update subtotal footer XPath: Use `//field[@name='tax_totals']/..` instead of fragile class list.

#### [MODIFY] [stock_landed_cost.xml](file:///home/nerdop/laboratorio/LocVe18v2/account_dual_currency/views/stock_landed_cost.xml)
- Update subtotal footer XPath: Use `//field[@name='amount_total']/..` instead of fragile class list.

#### [MODIFY] [account_move.py](file:///home/nerdop/laboratorio/LocVe18v2/account_dual_currency/models/account_move.py)
- Fixed `payment_id` to `origin_payment_id` renaming.

#### [MODIFY] [models/__init__.py](file:///home/nerdop/laboratorio/LocVe18v2/account_dual_currency/models/__init__.py)
- Comment out `reconciliation_widget` import (removed model in Odoo 18). [DONE]
- Re-enable `crossovered_budget_lines` import (model still exists in Odoo 18). [DONE]

#### [MODIFY] [__manifest__.py](file:///home/nerdop/laboratorio/LocVe18v2/account_dual_currency/__manifest__.py)
- Re-enable `views/crossovered_budget_lines.xml` in data list. [DONE]

#### [DELETE] [reconciliation_widget.py](file:///home/nerdop/laboratorio/LocVe18v2/account_dual_currency/models/reconciliation_widget.py)
- Remove the file as it's no longer compatible with Odoo 18. [DONE]

#### [RESTORE] [crossovered_budget_lines.py](file:///home/nerdop/laboratorio/LocVe18v2/account_dual_currency/models/crossovered_budget_lines.py)
- Restore the file with dual currency support for budget lines.
- The `crossovered.budget.lines` model still exists in Odoo 18's `account_budget` module.

---

### Automation Script (Existing)
Create a new script `tools/tag_modules.py` to automate the following changes across all 19 modules:

#### [MODIFY] `__manifest__.py` (All Modules)
- **Prefix `name`**: Add `[LocVe]` prefix to the module name.
  - Example: `"name": "Binaural Base"` -> `"name": "[LocVe] Binaural Base"`
- **Update `category`**: Set category to `LocVe [Localization]` to allow grouping by category in the Apps filter.

## Verification Plan

### Automated Tests
- Run `grep` to verify that all `__manifest__.py` files contain the `[LocVe]` string in the `name` and `category` fields.
- Check that no syntax errors were introduced in the manifest files.

### Manual Verification
- The user can search for "LocVe" in the Odoo Apps menu and should see all 19 modules.
- The user can filter by category "LocVe [Localization]" to see the grouped modules.
