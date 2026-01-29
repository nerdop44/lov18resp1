# Version Control Safeguards

- [x] Establish Version Integrity Workflow
    - [x] Create `check_env.sh` script to verify environment before work
    - [x] Update `README.md` with version-specific markers
    - [x] Set up git hooks (optional/advanced)
- [x] Document repository layout and purposes in an artifact

- [x] Module Dependency and Integrity Audit
    - [x] Map internal and external dependencies for all modules
    - [x] Generate installation order (Dependency Graph)
    - [x] Audit manifests for Odoo 18 compatibility
    - [x] Check for common Odoo 18 breaking changes (digits, XPaths)
    - [x] Report findings and required corrections

- [x] Apply Odoo 18 Compatibility Fixes
    - [x] Fix installation errors in Prueba1
    - [x] Comment out `crossovered.budget.lines` (temporary)
    - [x] Comment out total_paid XPath in POS report
    - [x] Resolve `res_groups` unique constraint conflicts across all modules
    - [x] Replace string-based `digits` with numeric tuples
    - [x] Update deprecated `track_visibility` to `tracking`
    - [x] Fix `KeyError`: Define `igtf_divisa_porcentage` in `res.company`
    - [x] Fix `ParseError`: Update XPaths in `pos_igtf_tax` and `pos_fiscal_printer`
    - [x] Resolve `res_groups` unique constraint conflicts across all modules
    - [x] Verify changes across all modules
- [x] Push all fixes to `Dep3` (Commit `593863f`)
- [x] Update submodule on `Prueba1` server and commit update to parent repo
- [x] Trigger Odoo.sh rebuild on `Prueba1` (Push parent repo)
- [x] Fix `ParseError`: Update XPath (div -> field) and fix deprecated domains in `hr_leave.xml` (Odoo 18)
- [x] Fix `ParseError`: Replace deprecated domain syntax for `invisible`/`readonly` in `hr_employee_loan.xml` (Odoo 18)
- [x] Comprehensive Health Check: Scan for `attrs`, `states`, `digits` (All Clean)

## Documentation & Manuals
- [x] Create **Installation Guide for Odoo.sh** (Detailed steps for clients)
- [x] Create **Configuration Manual** (Setup guide for admins/consultants)
- [x] Create **Functional Manual** (Usage guide for end-users)
- [ ] Enhace **Technical/General Manual** (Make it more robust)
- [ ] Create `documentation` folder in `LocVe18v2` and move manuals
- [ ] Convert manuals to PDF and DOC (if tools available)
- [ ] Push changes to `nerdop44/LocVe18v2` branch `Dep3`
- [x] Fix `ParseError`: Update XPaths in `report_payslip.xml` to match Odoo 18 QWeb structure (Round 2) (Odoo 18)
- [x] Fix `ParseError`: Remove invalid `active_id` context in `hr_employee.xml` (Odoo 18)
- [x] Fix `ParseError`: Replace invalid `active_id` with `employee_id` in domain of `hr_contract.xml` (Odoo 18)
- [x] Fix `ParseError`: Rename `yearly_advantages` to `yearly_benefits` in `hr_contract.xml` (Odoo 18)
- [x] Fix `ParseError`: Replace deprecate `attrs` with python expressions in `hr_payslip.xml` (Odoo 18)
- [x] Fix `ValueError`: Update `mail.template` to use `report_template_ids` instead of `report_name`/`report_template` (Odoo 18)
- [x] Fix `ValueError`: Update `allocation_validation_type` from `officer` to `hr` in `hr_holidays_data.xml` (Odoo 18)
- [x] Fix `ValueError`: Update `responsible_id` to `responsible_ids` in `hr_holidays_data.xml` (Odoo 18)
- [x] Fix `ValueError`: Replace `figure_type="none"` with `string` in `l10n_ve_payroll_report.xml` (Odoo 18)
- [x] Fix `KeyError`: Remove invalid `related` fields in `hr.employee` (Odoo 18)
- [x] Fix `ModuleNotFoundError`: Update `resource` utility imports in `hr_leave.py` (Odoo 18)
- [x] Fix `ModuleNotFoundError`: Remove obsolete `browsable_object` import in `hr_payroll` (Odoo 18)
- [x] Fix `KeyError`: Migrate `mail.channel` to `discuss.channel` (Odoo 18 change)
- [x] Fix `ValueError`: Invalid field `numbercall` in `ir.cron` (Removed in Odoo 18)
- [x] Fix `ParseError`: Update account journal dashboard (Update `t-esc` to `t-out` and fix Python queries)
- [x] Fix `ParseError`: Update product template kanban (Replace missing `div` with `list_price` parent)
- [x] Fix `ParseError`: Update account payment register (Remove `group3`, replace `attrs` with `invisible`)
- [x] Fix `ParseError`: Resolve missing `account_reports.search_template` (Obsolete in Odoo 18)
- [/] Verify build success on Odoo.sh `Prueba1`

## Phase 2: Post-Installation Functional Audit & Re-linking
- [ ] Audit removed/modified components to identify Odoo 18 "evolutions"
- [ ] Re-link Reconciliation Widget logic (refactored to `bank_rec_widget` in Odoo 18)
- [ ] Migrate Report Filters (from `search_template` to new OWL/init_options mechanism)
- [ ] Fix Journal Dashboard Queries (Migrate to Odoo 18 `SQL` and new query methods)
- [ ] Verify Dual Currency display in all primary views (Invoices, Payments, Reports)
- [ ] Restore Budget functionality (Check `account_budget` compatibility)
- [ ] Validate IGTF calculation and posting workflow

- [/] Verify build success on Odoo.sh
    - [x] Inspect submodules layout in Odoo.sh
    - [x] Update submodules to track `Dep3` branch or latest commit
    - [x] Trigger Odoo module update/restart
    - [x] Trigger Odoo.sh formal rebuild (Troubleshooting permissions)

- [x] Establish Multi-Client Odoo.sh Update Methodology
    - [x] Create `tools/update_odoosh.sh` automation script
    - [x] Document the update process for multiple clients in `walkthrough.md`
    - [x] Define management strategy for client-specific Deploy Keys
- [x] Fix Indentation and Migration Errors
    - [x] Identify root cause of `IndentationError` in `account_fiscalyear_closing.py`
    - [x] Develop/Improve `fix_migration_errors.py` script
    - [x] Remove orphaned `_valid_field_parameter` methods
    - [x] Clean up truncated or broken Python files
    - [x] Verify XML attribute consistency (invisible/readonly/required)
