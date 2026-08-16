from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError, ValidationError, AccessError, RedirectWarning
from odoo.tools import (
    date_utils,
    email_split,
    float_compare,
    float_is_zero,
    format_amount,
    format_date,
    formatLang,
    frozendict,
    get_lang,
    is_html_empty,
    sql,
    SQL
)
import json


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Campos de compatibilidad (Alias para evitar errores de validación de vista)
    foreign_rate = fields.Float(related='tax_today', readonly=False, string="Tasa (Alias)")
    foreign_inverse_rate = fields.Float(string="Tasa Inversa (Alias)", compute="_compute_foreign_inverse_rate")

    @api.depends('tax_today')
    def _compute_foreign_inverse_rate(self):
        for rec in self:
            rec.foreign_inverse_rate = (1 / rec.tax_today) if rec.tax_today else 0



    def _valid_field_parameter(self, field_name, parameter):
        return super()._valid_field_parameter(field_name, parameter)


    currency_id_dif = fields.Many2one("res.currency",
                                      string="Moneda Dual Ref.",
                                      default=lambda self: self.env['res.currency'].search([('name', '=', 'USD')],
                                                                                           limit=1), )

    # Campos de compatibilidad (Alias para evitar errores de validación de vista)
    currency_vef_id = fields.Many2one("res.currency", related="currency_id_dif", string="Moneda VEF (Compatibilidad)")
    vef_currency_id = fields.Many2one("res.currency", related="currency_id_dif", string="Moneda VEF (Compatibilidad 2)")

    currency_id_dif_resolved = fields.Many2one("res.currency",
                                               string="Moneda Dual Ref. Resuelta",
                                               compute="_compute_currency_id_dif_resolved",
                                               store=True)

    @api.depends('company_id.currency_id_dif', 'currency_id_dif')
    def _compute_currency_id_dif_resolved(self):
        for rec in self:
            rec.currency_id_dif_resolved = rec.company_id.currency_id_dif or rec.currency_id_dif

    acuerdo_moneda = fields.Boolean(string="Acuerdo de Factura Bs.", default=False)

    tax_today = fields.Float(string="Tasa de Factura", store=True,
                             default=lambda self: self.env.company.currency_id_dif.inverse_rate,
                             tracking=True)

    tax_today_edited = fields.Boolean(string="Tasa Manual", default=False)

    edit_trm = fields.Boolean(string="Editar tasa", compute='_edit_trm')

    name_rate = fields.Char(store=True, readonly=True, compute='_name_ref')
    amount_untaxed_usd = fields.Monetary(currency_field='currency_id_dif', string="Base imponible Ref.", store=True,
                                         compute="_amount_all_usd", copy=False)
    amount_tax_usd = fields.Monetary(currency_field='currency_id_dif', string="Impuestos Ref.", store=True,
                                     readonly=True, compute="_amount_all_usd", copy=False)
    amount_total_usd = fields.Monetary(currency_field='currency_id_dif', string='Total Ref.', store=True, readonly=True,
                                       compute='_amount_all_usd',
                                       tracking=True)

    amount_residual_usd = fields.Monetary(currency_field='currency_id_dif', compute='_compute_amount', string='Adeudado Ref.',
                                          readonly=True, store=True, copy=False)
    invoice_payments_widget_usd = fields.Binary(groups="account.group_account_invoice,account.group_account_readonly",
                                               compute='_compute_payments_widget_reconciled_info_USD')

    amount_untaxed_bs = fields.Monetary(currency_field='company_currency_id', string="Base imponible Bs.", store=True, copy=False,
                                        compute="_amount_all_usd")
    amount_tax_bs = fields.Monetary(currency_field='company_currency_id', string="Impuestos Bs.", store=True, copy=False,
                                    readonly=True)
    amount_total_bs = fields.Monetary(currency_field='company_currency_id', string='Total Bs.', store=True,
                                      readonly=True,
                                      compute='_amount_all_usd', copy=False)

    amount_total_signed_usd = fields.Monetary(
        string='Total Signed Ref.',
        compute='_compute_amount', store=True, readonly=True,
        currency_field='currency_id_dif', copy=False
    )

    invoice_payments_widget_bs = fields.Text(groups="account.group_account_invoice", copy=False)

    same_currency = fields.Boolean(string="Mismo tipo de moneda", compute='_same_currency')

    verificar_pagos = fields.Boolean(string="Verificar pagos", compute='_verificar_pagos')

    asset_remaining_value_ref = fields.Monetary(currency_field='currency_id_dif', string='Valor depreciable Ref.', copy=False, compute='_compute_depreciation_cumulative_value_ref')
    asset_depreciated_value_ref = fields.Monetary(currency_field='currency_id_dif', string='Depreciación Acu. Ref.', copy=False, compute='_compute_depreciation_cumulative_value_ref')

    move_igtf_id = fields.Many2one('account.move', string='Asiento Retención IGTF', copy=False)

    depreciation_value_ref = fields.Monetary(
        string="Depreciation Ref.",
        compute="_compute_depreciation_value_ref", inverse="_inverse_depreciation_value_ref", store=True, copy=False
    )

    def _post(self, soft=True):
        res = super(AccountMove, self)._post(soft=soft)
        for move in self:
            move._verificar_pagos()
        return res

    @api.depends('asset_id', 'depreciation_value', 'asset_id.total_depreciable_value', 'asset_id.already_depreciated_amount_import')
    def _compute_depreciation_cumulative_value(self):
        super(AccountMove, self)._compute_depreciation_cumulative_value()
        for move in self:
            if move.asset_id:
                move.asset_remaining_value_ref = (move.asset_remaining_value / move.tax_today) if move.tax_today != 0 else 0
                move.asset_depreciated_value_ref = (move.asset_depreciated_value / move.tax_today) if move.tax_today != 0 else 0

    @api.depends('line_ids.balance_usd')
    def _compute_depreciation_value_ref(self):
        for move in self:
            asset = move.asset_id or move.reversed_entry_id.asset_id  # reversed moves are created before being assigned to the asset
            if asset:
                asset_type = getattr(asset, 'asset_type', 'purchase')
                account = asset.account_depreciation_expense_id if asset_type != 'sale' else asset.account_depreciation_id
                asset_depreciation = sum(
                    move.line_ids.filtered(lambda l: l.account_id == account).mapped('balance_usd')
                )
                # Special case of closing entry - only disposed assets of type 'purchase' should match this condition
                if any(
                        line.account_id == asset.account_asset_id
                        and float_compare(-line.balance_usd, asset.original_value_ref,
                                          precision_rounding=asset.currency_id.rounding) == 0
                        for line in move.line_ids
                ):
                    account = asset.account_depreciation_id
                    asset_depreciation = (
                            asset.original_value_ref
                            - asset.salvage_value_ref
                            - sum(
                        move.line_ids.filtered(lambda l: l.account_id == account).mapped(
                            'debit_usd' if asset.original_value_ref > 0 else 'credit_usd'
                        )
                    ) * (-1 if asset.original_value_ref < 0 else 1)
                    )
            else:
                asset_depreciation = 0
            move.depreciation_value_ref = asset_depreciation

    # -------------------------------------------------------------------------
    # INVERSE METHODS
    # -------------------------------------------------------------------------
    def _inverse_depreciation_value(self):
        for move in self:
            asset = move.asset_id
            amount = abs(move.depreciation_value_ref)
            asset_type = getattr(asset, 'asset_type', 'purchase')
            account = asset.account_depreciation_expense_id if asset_type != 'sale' else asset.account_depreciation_id
            move.write({'line_ids': [
                Command.update(line.id, {
                    'balance_usd': amount if line.account_id == account else -amount,
                })
                for line in move.line_ids
            ]})

    def _verificar_pagos(self):
        for rec in self:
            for line in rec.line_ids:
                if line.balance_usd == 0:
                    line._compute_balance_usd()
                line._compute_amount_residual_usd()
            rec.verificar_pagos = True

    @api.depends('invoice_date', 'date', 'company_id')
    def _compute_date(self):
        res = super(AccountMove, self)._compute_date()
        for rec in self:
            if rec.state == 'posted':
                continue
            if rec.company_id.currency_id_dif and not rec.tax_today_edited:
                if rec.tax_today > 0.0:
                    continue
                date_to_use = rec.invoice_date or rec.date or fields.Date.context_today(rec)
                new_rate_ids = rec.company_id.currency_id_dif._get_rates(rec.company_id, date_to_use)
                if new_rate_ids and rec.company_id.currency_id_dif.id in new_rate_ids:
                    new_rate = 1 / new_rate_ids[rec.company_id.currency_id_dif.id]
                    rec.tax_today = new_rate
                else:
                    # No hay tasa registrada para la fecha historica: usar la tasa actual como fallback
                    fallback_rate = rec.company_id.currency_id_dif.inverse_rate if rec.company_id.currency_id_dif else 0.0
                    if fallback_rate and fallback_rate > 0:
                        rec.tax_today = fallback_rate


    @api.onchange('tax_today_edited')
    def _onchange_tax_today_edited(self):
        for rec in self:
            if not rec.tax_today_edited:
                date_to_use = rec.invoice_date or rec.date or fields.Date.context_today(rec)
                new_rate_ids = rec.company_id.currency_id_dif._get_rates(rec.company_id, date_to_use)
                if new_rate_ids and rec.company_id.currency_id_dif.id in new_rate_ids:
                    rec.tax_today = 1 / new_rate_ids[rec.company_id.currency_id_dif.id]
                else:
                    rec.tax_today = rec.company_id.currency_id_dif.inverse_rate if rec.company_id.currency_id_dif else 1.0


    @api.model_create_multi
    def create(self, values):
        #print('Valores de la factura', values)
        #verificar si viene asiento de diferencia
        diferencia = False
        line_ids = []
        if 'Diferencia en tasa de cambio' in str(values):
            diferencia = True
        for val in values:
            if 'line_ids' in val:
                if val['line_ids']:
                    for idx, l in enumerate(val['line_ids']):
                        if diferencia:
                            #verifica si el texto l[2]['name'] contiene la palabra diferencia
                            if 'name' in l[2] and 'Diferencia en tasa' in l[2]['name']:
                                #elimina la linea de diferencia
                                val['line_ids'].pop(idx)
                            else:
                                #cambia la moneda a Bs
                                journal_id = self.env['account.journal'].search([('id', '=', val['journal_id'])])
                                company_id = journal_id.company_id
                                l[2]['currency_id'] = company_id.currency_id.id
                                l[2]['debit'] = l[2]['balance'] if l[2]['balance'] > 0 else 0
                                l[2]['credit'] = abs(l[2]['balance']) if l[2]['balance'] < 0 else 0
                                l[2]['partner_id'] = None
                                l[2]['amount_currency'] = l[2]['balance']
                                line_ids.append(l)
            if diferencia:
                val['line_ids'] = line_ids


        if values:
            for val in values:
                if not 'tax_today' in val and not diferencia:
                    module_dual_currency = self.env['ir.module.module'].sudo().search(
                        [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
                    if module_dual_currency:
                        currency_dif = self.env.company.currency_id_dif
                        move_currency_id = val.get('currency_id')
                        # If the invoice currency is the same as the dual reference currency (e.g. USD invoice),
                        # tax_today must be 1.0 to avoid double currency conversion in the accounting lines.
                        if move_currency_id and currency_dif and move_currency_id == currency_dif.id:
                            val.update({'tax_today': 1.0})
                        else:
                            date_to_use = val.get('invoice_date') or val.get('date') or fields.Date.context_today(self)
                            new_rate_ids = currency_dif._get_rates(self.env.company, date_to_use) if currency_dif else {}
                            if new_rate_ids and currency_dif.id in new_rate_ids:
                                db_rate = new_rate_ids[currency_dif.id]
                            else:
                                db_rate = currency_dif.inverse_rate if currency_dif else 1.0
                            
                            if 0.0 < db_rate < 1.0:
                                new_rate = 1.0 / db_rate
                            else:
                                new_rate = db_rate
                            val.update({'tax_today': new_rate})

                # Sincronizar tasas si se proporciona alguna
                tax_today = val.get('tax_today', 0.0)
                foreign_rate = val.get('foreign_rate', 0.0)
                foreign_inverse_rate = val.get('foreign_inverse_rate', 0.0)
                if tax_today > 0 and not foreign_rate:
                    val['foreign_rate'] = tax_today
                    if self.env.company.currency_id.name == 'USD':
                        val['foreign_inverse_rate'] = tax_today
                    else:
                        val['foreign_inverse_rate'] = 1.0 / tax_today
                elif foreign_rate > 0 and not tax_today:
                    val['tax_today'] = foreign_rate
                    if self.env.company.currency_id.name == 'USD':
                        val['foreign_inverse_rate'] = foreign_rate
                    else:
                        val['foreign_inverse_rate'] = 1.0 / foreign_rate
                elif foreign_inverse_rate > 0 and not tax_today and not foreign_rate:
                    if self.env.company.currency_id.name == 'USD':
                        val['tax_today'] = foreign_inverse_rate
                        val['foreign_rate'] = foreign_inverse_rate
                    else:
                        val['tax_today'] = 1.0 / foreign_inverse_rate
                        val['foreign_rate'] = 1.0 / foreign_inverse_rate

        res = super(AccountMove, self).create(values)
        return res

    @api.depends('currency_id')
    def _same_currency(self):
        self.same_currency = self.currency_id == self.env.company.currency_id


    @api.onchange('tax_today')
    def _onchange_tax_today(self):
        self = self.with_context(check_move_validity=False)
        for rec in self:
            if not rec.move_type == 'entry':
                for l in rec.invoice_line_ids:
                    if rec.currency_id == rec.company_id.currency_id:
                        if l.price_unit:
                            # Recalcular price_unit_usd basándose en la tasa:
                            if rec.company_id.currency_id.name == 'USD':
                                l.price_unit_usd = l.price_unit * rec.tax_today
                            else:
                                l.price_unit_usd = l.price_unit / rec.tax_today if rec.tax_today > 0 else 0.0
                        else:
                            if rec.company_id.currency_id.name == 'USD':
                                l.price_unit = l.price_unit_usd / rec.tax_today if rec.tax_today > 0 else 0.0
                            else:
                                l.price_unit = l.price_unit_usd * rec.tax_today
                    else:
                        if l.price_unit:
                            l.price_unit_usd = l.price_unit
                        else:
                            l.price_unit = l.price_unit_usd
                rec._onchange_quick_edit_total_amount()
                rec._onchange_quick_edit_line_ids()
                rec._compute_tax_totals()
                rec.invoice_line_ids._compute_totals()

                # Update the accounting lines (line_ids) in the UI immediately
                for aml in rec.line_ids:
                    if aml.debit != 0:
                        if aml.currency_id == rec.company_id.currency_id_dif:
                            aml.debit_usd = abs(aml.amount_currency)
                        else:
                            if rec.company_id.currency_id.name == 'USD':
                                aml.debit_usd = aml.debit * rec.tax_today
                            else:
                                aml.debit_usd = (aml.debit / rec.tax_today) if rec.tax_today > 0 else 0
                    else:
                        aml.debit_usd = 0
                    if aml.credit != 0:
                        if aml.currency_id == rec.company_id.currency_id_dif:
                            aml.credit_usd = abs(aml.amount_currency)
                        else:
                            if rec.company_id.currency_id.name == 'USD':
                                aml.credit_usd = aml.credit * rec.tax_today
                            else:
                                aml.credit_usd = (aml.credit / rec.tax_today) if rec.tax_today > 0 else 0
                    else:
                        aml.credit_usd = 0
                    aml.balance_usd = aml.debit_usd - aml.credit_usd
                    # Recalculate amount_residual_usd
                    reconciled_balance = sum(aml.matched_credit_ids.mapped('amount_usd')) \
                                         - sum(aml.matched_debit_ids.mapped('amount_usd'))
                    aml.amount_residual_usd = aml.balance_usd - reconciled_balance

            else:
                for aml in rec.with_context(check_move_validity=False).line_ids:
                    if aml.debit_usd == 0 and aml.debit > 0:
                        if rec.company_id.currency_id.name == 'USD':
                            aml.with_context(check_move_validity=False).debit_usd = aml.debit * rec.tax_today
                        else:
                            aml.with_context(check_move_validity=False).debit_usd = (aml.debit / rec.tax_today) if rec.tax_today > 0 else 0
                    if aml.credit_usd == 0 and aml.credit > 0:
                        if rec.company_id.currency_id.name == 'USD':
                            aml.with_context(check_move_validity=False).credit_usd = aml.credit * rec.tax_today
                        else:
                            aml.with_context(check_move_validity=False).credit_usd = (aml.credit / rec.tax_today) if rec.tax_today > 0 else 0
                    aml.balance_usd = aml.debit_usd - aml.credit_usd

    @api.depends('currency_id_dif')
    def _name_ref(self):
        for record in self:
            record.name_rate = record.currency_id_dif.currency_unit_label

    @api.onchange('currency_id')
    def _onchange_currency(self):
        for rec in self:
            if rec.currency_id == self.env.company.currency_id:
                for l in rec.invoice_line_ids:
                    l.currency_id = rec.currency_id
                    if rec.company_id.currency_id.name == 'USD':
                        l.price_unit = (l.price_unit_usd / (rec.tax_today if rec.tax_today > 0 else 1.0))
                    else:
                        l.price_unit = (l.price_unit_usd * (rec.tax_today if rec.tax_today > 0 else 1.0))

            else:
                for l in rec.invoice_line_ids:
                    l.currency_id = rec.currency_id
                    l.price_unit = l.price_unit_usd

            for aml in rec.line_ids:
                aml.currency_id = rec.currency_id
                aml._compute_currency_rate()


    @api.depends('state', 'move_type')
    def _edit_trm(self):
        for rec in self:
            edit_trm = False
            if rec.move_type in ('in_invoice', 'in_refund', 'in_receipt', 'entry'):
                if rec.state == 'draft' and not rec.acuerdo_moneda:
                    edit_trm = True
                else:
                    edit_trm = False
            else:
                edit_trm = self.env.user.has_group('account_dual_currency.group_edit_trm')
                if edit_trm:
                    if rec.state == 'draft' and not rec.acuerdo_moneda:
                        edit_trm = True
                    else:
                        edit_trm = False
            rec.edit_trm = edit_trm

    @api.depends(
        'line_ids.matched_debit_ids.debit_move_id.move_id.origin_payment_id.is_matched',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.matched_credit_ids.credit_move_id.move_id.origin_payment_id.is_matched',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.balance',
        'line_ids.currency_id',
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'line_ids.payment_id.state',
        'line_ids.full_reconcile_id','tax_today')
    def _compute_amount(self):
        for move in self:
            move_ctx = move.with_context(tasa_factura=move.tax_today, calcular_dual_currency=True)
            super(AccountMove, move_ctx)._compute_amount()
            total_residual = 0.0
            total = 0.0
            for line in move.line_ids:
                if move.is_invoice(True):
                    if line.display_type == 'tax' or (line.display_type == 'rounding' and line.tax_repartition_line_id):
                        # Tax amount.
                        total += line.balance_usd
                    elif line.display_type in ('product', 'rounding'):
                        total += line.balance_usd
                    elif line.display_type == 'payment_term':
                        # Residual amount.
                        total_residual += line.amount_residual_usd
            move.amount_residual_usd = total_residual
            move.amount_total_signed_usd = abs(total) if move.move_type == 'entry' else -total

    @api.depends(
        'tax_totals',
        'currency_id_dif',
        'currency_id',
        'tax_today',
        'line_ids.balance_usd',
        'move_type'
    )
    def _amount_all_usd(self):
        for rec in self:
            # Sincronización proactiva y segura de tasas para evitar desalineación o tasa a 0
            if rec.company_id.currency_id_dif and not rec.tax_today_edited:
                # Si tax_today es 0 pero la localización tiene tasa, usarla
                if (not rec.tax_today or rec.tax_today <= 0.0) and getattr(rec, 'foreign_rate', 0.0) > 0.0:
                    rec.tax_today = rec.foreign_rate
                
                # Si sigue siendo 0, buscar de forma proactiva la tasa de cambio en Odoo
                if not rec.tax_today or rec.tax_today <= 0.0:
                    date_to_use = rec.invoice_date or rec.date or fields.Date.context_today(rec)
                    new_rate_ids = rec.company_id.currency_id_dif._get_rates(rec.company_id, date_to_use)
                    if new_rate_ids and rec.company_id.currency_id_dif.id in new_rate_ids:
                        db_rate = new_rate_ids[rec.company_id.currency_id_dif.id]
                        if 0.0 < db_rate < 1.0:
                            new_rate = 1.0 / db_rate
                        else:
                            new_rate = db_rate
                        if new_rate > 0.0:
                            rec.tax_today = new_rate

            # Alinear campos de la localización si tax_today es válido
            if rec.tax_today > 0.0:
                if hasattr(rec, 'foreign_rate') and rec.foreign_rate != rec.tax_today:
                    rec.foreign_rate = rec.tax_today
                if hasattr(rec, 'foreign_inverse_rate'):
                    if rec.company_id.currency_id.name == 'USD':
                        expected_inverse = rec.tax_today
                    else:
                        expected_inverse = 1.0 / rec.tax_today
                    if abs(rec.foreign_inverse_rate - expected_inverse) > 1e-7:
                        rec.foreign_inverse_rate = expected_inverse

            rec.amount_untaxed_usd = 0
            rec.amount_tax_usd = 0
            rec.amount_total_usd = 0
            rec.amount_untaxed_bs = 0
            rec.amount_tax_bs = 0
            rec.amount_total_bs = 0

            # 1. Caso Facturas (Invoices/Refunds)
            if rec.is_invoice(include_receipts=True):
                tax_totals = rec.tax_totals or {}
                # Priorizar montos ya calculados por l10n_ve_tax
                untaxed_usd = tax_totals.get('foreign_amount_untaxed')
                tax_usd = tax_totals.get('foreign_amount_tax')
                total_usd = tax_totals.get('foreign_amount_total')

                if rec.company_id.currency_id.name == 'USD':
                    # Company is USD
                    if rec.currency_id.name == 'USD':
                        rec.amount_untaxed_usd = rec.amount_untaxed
                        rec.amount_total_usd = rec.amount_total
                        rec.amount_tax_usd = rec.amount_total - rec.amount_untaxed
                        
                        rec.amount_untaxed_bs = untaxed_usd if untaxed_usd is not None else (rec.amount_untaxed * rec.tax_today)
                        rec.amount_total_bs = total_usd if total_usd is not None else (rec.amount_total * rec.tax_today)
                        rec.amount_tax_bs = rec.amount_total_bs - rec.amount_untaxed_bs
                    else:
                        # Invoice is VES
                        rec.amount_untaxed_bs = rec.amount_untaxed
                        rec.amount_total_bs = rec.amount_total
                        rec.amount_tax_bs = rec.amount_total - rec.amount_untaxed
                        
                        rec.amount_untaxed_usd = untaxed_usd if untaxed_usd is not None else ((rec.amount_untaxed / rec.tax_today) if rec.tax_today > 0 else 0)
                        rec.amount_total_usd = total_usd if total_usd is not None else ((rec.amount_total / rec.tax_today) if rec.tax_today > 0 else 0)
                        rec.amount_tax_usd = rec.amount_total_usd - rec.amount_untaxed_usd
                else:
                    # Company is VES
                    if rec.currency_id == rec.company_id.currency_id:
                        # Invoice is VES
                        rec.amount_untaxed_bs = rec.amount_untaxed
                        rec.amount_total_bs = rec.amount_total
                        rec.amount_tax_bs = rec.amount_total - rec.amount_untaxed
                        
                        rec.amount_untaxed_usd = untaxed_usd if untaxed_usd is not None else ((rec.amount_untaxed / rec.tax_today) if rec.tax_today > 0 else 0)
                        rec.amount_total_usd = total_usd if total_usd is not None else ((rec.amount_total / rec.tax_today) if rec.tax_today > 0 else 0)
                        rec.amount_tax_usd = rec.amount_total_usd - rec.amount_untaxed_usd
                    else:
                        # Invoice is USD
                        rec.amount_untaxed_usd = rec.amount_untaxed
                        rec.amount_total_usd = rec.amount_total
                        rec.amount_tax_usd = rec.amount_total - rec.amount_untaxed
                        
                        rec.amount_untaxed_bs = untaxed_usd if untaxed_usd is not None else (rec.amount_untaxed * rec.tax_today)
                        rec.amount_total_bs = total_usd if total_usd is not None else (rec.amount_total * rec.tax_today)
                        rec.amount_tax_bs = rec.amount_total_bs - rec.amount_untaxed_bs

            # 2. Caso Asientos Manuales (MISC / entry)
            elif rec.move_type == 'entry':
                # Sumamos el balance_usd de las líneas (debe - haber en USD)
                # Para el total "bruto" del asiento, sumamos los débitos USD
                total_usd = sum(rec.line_ids.mapped('debit_usd'))
                rec.amount_total_usd = total_usd
                rec.amount_untaxed_usd = total_usd
                
                rec.amount_total_bs = sum(rec.line_ids.mapped('debit'))
                rec.amount_untaxed_bs = rec.amount_total_bs

    @api.depends('move_type', 'line_ids.amount_residual_usd')
    def _compute_payments_widget_reconciled_info_USD(self):
        for move in self:
            payments_widget_vals = {'title': _('Less Payment'), 'outstanding': False, 'content': []}
            total_pagado = 0
            if move.state == 'posted' and move.is_invoice(include_receipts=True):
                reconciled_vals = []
                reconciled_partials = move._get_all_reconciled_invoice_partials_USD()

                for reconciled_partial in reconciled_partials:
                    counterpart_line = reconciled_partial['aml']
                    if counterpart_line.move_id.ref:
                        reconciliation_ref = '%s (%s)' % (counterpart_line.move_id.name, counterpart_line.move_id.ref)
                    else:
                        reconciliation_ref = counterpart_line.move_id.name
                    if counterpart_line.amount_currency and counterpart_line.currency_id != counterpart_line.company_id.currency_id:
                        foreign_currency = counterpart_line.currency_id
                    else:
                        foreign_currency = False
                    total_pagado = total_pagado + float(reconciled_partial['amount'])
                    reconciled_vals.append({
                        'name': counterpart_line.name,
                        'journal_name': counterpart_line.journal_id.name,
                        'amount': reconciled_partial['amount'],
                        'currency_id': move.company_id.currency_id_dif.id if move.company_id.currency_id_dif else
                        move.company_id.currency_id.id,
                        'date': counterpart_line.date,
                        'partial_id': reconciled_partial['partial_id'],
                        'account_payment_id': counterpart_line.payment_id.id,
                        'payment_method_name': counterpart_line.payment_id.payment_method_line_id.name,
                        'move_id': counterpart_line.move_id.id,
                        'ref': reconciliation_ref,
                        # these are necessary for the views to change depending on the values
                        'is_exchange': reconciled_partial['is_exchange'],
                        'amount_company_currency': formatLang(self.env, abs(counterpart_line.balance_usd),
                                                               currency_obj=counterpart_line.company_id.currency_id_dif),
                        'amount_foreign_currency': foreign_currency and formatLang(self.env,
                                                                                   abs(counterpart_line.amount_currency),
                                                                                   currency_obj=foreign_currency)
                    })
                payments_widget_vals['content'] = reconciled_vals

            if payments_widget_vals['content']:
                move.invoice_payments_widget_usd = payments_widget_vals
                if total_pagado < move.amount_total_usd:
                    move.amount_residual_usd = move.amount_total_usd - total_pagado
                else:
                    move.amount_residual_usd = 0
            else:
                move.amount_residual_usd = move.amount_total_usd
                move.invoice_payments_widget_usd = False

    @api.depends('move_type', 'line_ids.amount_residual_usd')
    def _compute_payments_widget_reconciled_info_bs(self):
        for move in self:
            if move.state != 'posted' or not move.is_invoice(include_receipts=True):
                move.invoice_payments_widget_bs = json.dumps(False)
                continue
            reconciled_vals = move._get_reconciled_info_JSON_values_bs()
            if reconciled_vals:
                info = {
                    'title': _('Less Payment'),
                    'outstanding': False,
                    'content': reconciled_vals,
                }
                move.invoice_payments_widget_bs = json.dumps(info, default=date_utils.json_default)
            else:
                move.invoice_payments_widget_bs = json.dumps(False)

    def _get_reconciled_info_JSON_values_bs(self):
        self.ensure_one()
        reconciled_vals = []
        pay_term_line_ids = self.line_ids.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        partials = pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')
        for partial in partials:
            counterpart_lines = partial.debit_move_id + partial.credit_move_id
            counterpart_line = counterpart_lines.filtered(lambda line: line not in self.line_ids)

            if counterpart_line.credit > 0:
                amount = counterpart_line.credit
            else:
                amount = counterpart_line.debit

            ref = counterpart_line.move_id.name
            if counterpart_line.move_id.ref:
                ref += ' (' + counterpart_line.move_id.ref + ')'

            reconciled_vals.append({
                'name': counterpart_line.name,
                'journal_name': counterpart_line.journal_id.name,
                'amount': partial.amount,
                'currency': self.currency_id_dif.symbol,
                'digits': [69, 2],
                'position': self.currency_id_dif.position,
                'date': counterpart_line.date,
                'payment_id': counterpart_line.id,
                'account_payment_id': counterpart_line.payment_id.id,
                'payment_method_name': counterpart_line.payment_id.payment_method_id.name if counterpart_line.journal_id.type == 'bank' else None,
                'move_id': counterpart_line.move_id.id,
                'ref': ref,
            })
        return reconciled_vals

    def _get_all_reconciled_invoice_partials_USD(self):
        self.ensure_one()
        reconciled_lines = self.line_ids.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        if not reconciled_lines:
            return {}

        query = SQL(
            """
            SELECT
                part.id,
                part.exchange_move_id,
                part.amount_usd AS amount,
                part.credit_move_id AS counterpart_line_id
            FROM account_partial_reconcile part
            WHERE part.debit_move_id IN %s
            UNION ALL
            SELECT
                part.id,
                part.exchange_move_id,
                part.amount_usd AS amount,
                part.debit_move_id AS counterpart_line_id
            FROM account_partial_reconcile part
            WHERE part.credit_move_id IN %s
            """,
            tuple(reconciled_lines.ids),
            tuple(reconciled_lines.ids),
        )
        self._cr.execute(query)

        partial_values_list = []
        counterpart_line_ids = set()
        exchange_move_ids = set()
        for values in self._cr.dictfetchall():
            partial_values_list.append({
                'aml_id': values['counterpart_line_id'],
                'partial_id': values['id'],
                'amount': values['amount'],
                'currency': self.currency_id,
            })
            counterpart_line_ids.add(values['counterpart_line_id'])
            if values['exchange_move_id']:
                exchange_move_ids.add(values['exchange_move_id'])

        if exchange_move_ids:
            query = SQL(
                """
                SELECT
                    part.id,
                    part.credit_move_id AS counterpart_line_id
                FROM account_partial_reconcile part
                JOIN account_move_line credit_line ON credit_line.id = part.credit_move_id
                WHERE credit_line.move_id IN %s AND part.debit_move_id IN %s
                UNION ALL
                SELECT
                    part.id,
                    part.debit_move_id AS counterpart_line_id
                FROM account_partial_reconcile part
                JOIN account_move_line debit_line ON debit_line.id = part.debit_move_id
                WHERE debit_line.move_id IN %s AND part.credit_move_id IN %s
                """,
                tuple(exchange_move_ids),
                tuple(counterpart_line_ids),
                tuple(exchange_move_ids),
                tuple(counterpart_line_ids),
            )
            self._cr.execute(query)

            for values in self._cr.dictfetchall():
                counterpart_line_ids.add(values['counterpart_line_id'])
                partial_values_list.append({
                    'aml_id': values['counterpart_line_id'],
                    'partial_id': values['id'],
                    'currency': self.company_id.currency_id,
                })

        counterpart_lines = {x.id: x for x in self.env['account.move.line'].browse(counterpart_line_ids)}
        for partial_values in partial_values_list:
            partial_values['aml'] = counterpart_lines[partial_values['aml_id']]
            partial_values['is_exchange'] = partial_values['aml'].move_id.id in exchange_move_ids
            if partial_values['is_exchange']:
                partial_values['amount'] = abs(partial_values['aml'].balance_usd)

        return partial_values_list

    def js_assign_outstanding_line(self, line_id):
        lines = self.env['account.move.line'].browse(line_id)
        lines += self.line_ids.filtered(lambda line: line.account_id == lines[0].account_id and not line.reconciled)
        res = super(AccountMove, self).js_assign_outstanding_line(line_id)
        lines._compute_amount_residual_usd()
        return res


    @api.depends('state', 'payment_state', 'line_ids.reconciled', 'line_ids.amount_residual', 'line_ids.amount_residual_currency')
    def _compute_payments_widget_to_reconcile_info(self):
        for move in self:
            move.invoice_outstanding_credits_debits_widget = False
            move.invoice_has_outstanding = False

            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue

            pay_term_lines = move.line_ids \
                .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))

            domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.commercial_partner_id.id),
                ('reconciled', '=', False),
                '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0),
            ]

            payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

            if move.is_inbound():
                domain.append(('balance', '<', 0.0))
                payments_widget_vals['title'] = _('Outstanding credits')
            else:
                domain.append(('balance', '>', 0.0))
                payments_widget_vals['title'] = _('Outstanding debits')

            for line in self.env['account.move.line'].search(domain):
                # Odoo 18: payment_id on move.line may be empty; use move's payment_ids as fallback
                payment = line.payment_id
                if not payment:
                    payment = line.move_id.payment_ids[:1] if line.move_id.payment_ids else payment
                
                currency_dif = move.currency_id_dif_resolved
                
                if line.debit == 0 and line.credit == 0 and not line.full_reconcile_id:
                    if abs(line.amount_residual_usd) > 0:
                        journal_name = (payment.name if payment else False) or line.ref or line.move_id.name
                        if journal_name:
                            journal_name = journal_name.replace("Retención", "Ret.").replace("Retencion", "Ret.")
                            parts = journal_name.split()
                            for idx, part in enumerate(parts):
                                if part.isdigit() and len(part) > 8:
                                    parts[idx] = f"*{part[-5:]}"
                            journal_name = " ".join(parts)
                        
                        if currency_dif:
                            amount_sec = line.company_currency_id._convert(
                                abs(line.amount_residual),
                                currency_dif,
                                move.company_id,
                                line.date or fields.Date.context_today(self),
                            )
                            formatted_val = formatLang(self.env, amount_sec, currency_obj=currency_dif)
                            amount_formatted = formatLang(self.env, 0.0, currency_obj=move.currency_id)
                            journal_name = f"{journal_name} ({amount_formatted} / {formatted_val})"
                        
                        amount_formatted = formatLang(self.env, 0.0, currency_obj=move.currency_id)
                        amount_usd_formatted = formatLang(self.env, abs(line.amount_residual_usd), currency_obj=currency_dif) if currency_dif else False
                        
                        payments_widget_vals['content'].append({
                            'journal_name': journal_name,
                            'amount': 0,
                            'amount_formatted': amount_formatted,
                            'amount_usd': abs(line.amount_residual_usd),
                            'amount_usd_formatted': amount_usd_formatted,
                            'currency_id': move.currency_id.id,
                            'currency_id_dif': currency_dif.id if currency_dif else False,
                            'id': line.id,
                            'move_id': line.move_id.id,
                            'date': fields.Date.to_string(line.date),
                            'account_payment_id': payment.id if payment else False,
                        })
                        continue
                # Safely check if the payment has a retention (field from l10n_ve_payment_extension)
                is_retention = (
                    bool(payment and getattr(payment, 'retention_id', False))
                    or bool(getattr(line.move_id, 'is_retention', False))
                )
                # For retention moves without account.payment, check move ref pattern
                if not is_retention and not payment:
                    move_name = line.move_id.name or ''
                    is_retention = bool(
                        getattr(line.move_id, 'retention_islr_line_ids', False)
                        or getattr(line.move_id, 'retention_iva_line_ids', False)
                    )
                if not is_retention:
                    is_retention = 'ret' in (line.journal_id.code or '').lower() or 'ret' in (line.journal_id.name or '').lower()
                
                display_currency = currency_dif if (is_retention and currency_dif) else move.currency_id

                is_company_usd = move.company_id.currency_id.name == 'USD'

                if line.currency_id == display_currency:
                    # Same currency.
                    amount = abs(line.amount_residual_currency)
                    if is_company_usd and currency_dif and display_currency == currency_dif:
                        amount_usd = abs(line.amount_residual)
                    else:
                        amount_usd = abs(line.amount_residual_usd)
                else:
                    # Different currencies.
                    amount = line.company_currency_id._convert(
                        abs(line.amount_residual),
                        display_currency,
                        move.company_id,
                        line.date,
                    )
                    if is_company_usd and currency_dif and display_currency == currency_dif:
                        amount_usd = abs(line.amount_residual)
                    else:
                        amount_usd = abs(line.amount_residual_usd)

                if display_currency.is_zero(amount):
                    continue

                journal_name = (payment.name if payment else False) or line.ref or line.move_id.name
                if journal_name:
                    journal_name = journal_name.replace("Retención", "Ret.").replace("Retencion", "Ret.")
                    parts = journal_name.split()
                    for idx, part in enumerate(parts):
                        if part.isdigit() and len(part) > 8:
                            parts[idx] = f"*{part[-5:]}"
                    journal_name = " ".join(parts)
                
                amount_formatted = formatLang(self.env, amount, currency_obj=display_currency)
                amount_usd_formatted = False

                if currency_dif:
                    if display_currency == currency_dif:
                        amount_primary = abs(line.amount_residual_currency) if line.currency_id == move.currency_id else line.company_currency_id._convert(
                            abs(line.amount_residual),
                            move.currency_id,
                            move.company_id,
                            line.date,
                        )
                        formatted_val = formatLang(self.env, amount_primary, currency_obj=move.currency_id)
                        journal_name = f"{journal_name} ({formatted_val} / {amount_formatted})"
                        amount_usd_formatted = formatted_val
                    else:
                        amount_sec = line.company_currency_id._convert(
                            abs(line.amount_residual),
                            currency_dif,
                            move.company_id,
                            line.date or fields.Date.context_today(self),
                        )
                        formatted_val = formatLang(self.env, amount_sec, currency_obj=currency_dif)
                        journal_name = f"{journal_name} ({amount_formatted} / {formatted_val})"
                        amount_usd_formatted = formatted_val

                payments_widget_vals['content'].append({
                    'journal_name': journal_name,
                    'amount': amount,
                    'amount_formatted': amount_formatted,
                    'amount_usd': amount_usd,
                    'amount_usd_formatted': amount_usd_formatted,
                    'currency_id': display_currency.id,
                    'currency_id_dif': currency_dif.id if currency_dif else False,
                    'id': line.id,
                    'move_id': line.move_id.id,
                    'date': fields.Date.to_string(line.date),
                    'account_payment_id': payment.id if payment else False,
                })

            if not payments_widget_vals['content']:
                continue
            move.invoice_outstanding_credits_debits_widget = payments_widget_vals
            move.invoice_has_outstanding = True

    @api.model
    def _prepare_move_for_asset_depreciation(self, vals):
        move_vals = super(AccountMove, self)._prepare_move_for_asset_depreciation(vals)
        asset_id = vals.get('asset_id')
        move_vals['tax_today'] = asset_id.tax_today
        move_vals['currency_id_dif'] = asset_id.currency_id_dif.id
        return move_vals

    def js_remove_outstanding_partial(self, partial_id):
        self.ensure_one()
        partial = self.env['account.partial.reconcile'].browse(partial_id)
        debit_move_id = partial.debit_move_id
        credit_move_id = partial.credit_move_id
        partial.unlink()
        if debit_move_id and credit_move_id:
            debit_move_id._compute_amount_residual_usd()
            credit_move_id._compute_amount_residual_usd()
        return True

    def generar_retencion_igtf(self):
        for rec in self:
            return {'name': _('Aplicar Retención IGTF'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'generar.igtf.wizard',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'domain': "",
                    'context': {
                            'default_invoice_id': rec.id,
                            'default_igtf_porcentage': rec.company_id.igtf_divisa_porcentage,
                            'default_tax_today': rec.currency_id_dif.inverse_rate,
                            'default_currency_id_dif': rec.currency_id_dif.id,
                            'default_currency_id_company': rec.company_id.currency_id.id,
                            'default_amount': rec.amount_residual_usd,
                        },
                    }

    def action_force_recompute_usd_totals(self):
        for move in self:
            move._onchange_tax_today()
            move._amount_all_usd()
            
            for line in move.line_ids:
                line._compute_balance_usd()
                line._compute_amount_residual_usd()
            
            move._compute_amount()
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Recálculo Completado'),
                'message': _('Se han recalculado los totales USD para %s registros.') % len(self),
                'sticky': False,
            }
        }

    def crear_asiento_diferencia(self):
        if self:
            partner_ids = self.mapped('partner_id')
            if len(partner_ids) > 1:
                raise UserError('No se puede crear un asiento de diferencia para facturas de diferentes clientes o proveedores')
        fac_clientes = self.filtered(lambda x: x.move_type in ('out_invoice'))
        total_diferencia_cliente = sum(fac_clientes.filtered(lambda x: x.amount_residual_usd == 0 and x.amount_residual != 0).mapped('amount_residual'))
        partner_id = self.mapped('partner_id')
        if total_diferencia_cliente > 0:
            journal_id = self.env.company.currency_exchange_journal_id
            company_id = self.env.company
            if journal_id:
                move = self.env['account.move'].create({
                    'journal_id': journal_id.id,
                    'company_id': company_id.id,
                    'move_type': 'entry',
                    'date': fields.Date.today(),
                    'tax_today': 0,
                    'ref': 'Diferencia en tasa de cambio',
                })
                line_ids = [
                        (0, 0, {
                            'name': 'Diferencia en tasa de cambio',
                            'partner_id': partner_id.id,
                            'account_id': partner_id.property_account_receivable_id.id,
                            'credit': total_diferencia_cliente,
                            'credit_usd': 0,
                            'amount_currency': -total_diferencia_cliente,
                        }),
                        (0, 0, {
                            'name': 'Diferencia en tasa de cambio',
                            'account_id': company_id.expense_currency_exchange_account_id.id,
                            'debit': total_diferencia_cliente,
                            'debit_usd': 0,
                            'amount_currency': total_diferencia_cliente,
                        }),
                    ]
                move.write({'line_ids': line_ids})
                move._post()
                line = move.line_ids.filtered(lambda x: x.account_id == partner_id.property_account_receivable_id)
                lines_facturas = fac_clientes.line_ids.filtered(lambda x: x.account_id == partner_id.property_account_receivable_id)
                (lines_facturas + line).reconcile()

                return move

    def write(self, vals):
        # Si cambia la fecha y no hay tasa manual ni tasa explícita, recalcular tax_today
        new_date = vals.get('invoice_date') or vals.get('date')
        if new_date:
            for rec in self:
                if rec.tax_today_edited or getattr(rec, 'manually_set_rate', False):
                    continue
                currency_dif = rec.company_id.currency_id_dif
                if not currency_dif:
                    continue
                # Si la moneda de la factura es la misma que la moneda de referencia, tasa = 1
                move_currency = vals.get('currency_id') or rec.currency_id.id
                if move_currency and move_currency == currency_dif.id:
                    vals['tax_today'] = 1.0
                    break
                try:
                    rate_ids = currency_dif._get_rates(rec.company_id, new_date)
                except Exception:
                    rate_ids = {}
                if rate_ids and currency_dif.id in rate_ids and rate_ids[currency_dif.id] > 0:
                    db_rate = rate_ids[currency_dif.id]
                else:
                    db_rate = currency_dif.inverse_rate or 0.0
                
                if 0.0 < db_rate < 1.0:
                    new_rate = 1.0 / db_rate
                else:
                    new_rate = db_rate
                
                if new_rate > 0:
                    vals['tax_today'] = new_rate
                break  # Aplicar solo una vez (todos los records del recordset comparten los mismos vals)

        # Sincronizar tasas en el diccionario de valores antes de escribir
        tax_today = vals.get('tax_today')
        foreign_rate = vals.get('foreign_rate')
        foreign_inverse_rate = vals.get('foreign_inverse_rate')

        if tax_today is not None and tax_today > 0:
            vals['foreign_rate'] = tax_today
            if self.env.company.currency_id.name == 'USD':
                vals['foreign_inverse_rate'] = tax_today
            else:
                vals['foreign_inverse_rate'] = 1.0 / tax_today
        elif foreign_rate is not None and foreign_rate > 0:
            vals['tax_today'] = foreign_rate
            if self.env.company.currency_id.name == 'USD':
                vals['foreign_inverse_rate'] = foreign_rate
            else:
                vals['foreign_inverse_rate'] = 1.0 / foreign_rate
        elif foreign_inverse_rate is not None and foreign_inverse_rate > 0:
            if self.env.company.currency_id.name == 'USD':
                vals['tax_today'] = foreign_inverse_rate
                vals['foreign_rate'] = foreign_inverse_rate
            else:
                vals['tax_today'] = 1.0 / foreign_inverse_rate
                vals['foreign_rate'] = 1.0 / foreign_inverse_rate

        return super(AccountMove, self).write(vals)

    @api.onchange('invoice_date', 'date')
    def _onchange_invoice_date_or_date(self):
        for rec in self:
            if rec.company_id.currency_id_dif and not rec.tax_today_edited and not getattr(rec, 'manually_set_rate', False):
                date_to_use = rec.invoice_date or rec.date or fields.Date.context_today(rec)
                try:
                    new_rate_ids = rec.company_id.currency_id_dif._get_rates(rec.company_id, date_to_use)
                except Exception:
                    new_rate_ids = {}
                if new_rate_ids and rec.company_id.currency_id_dif.id in new_rate_ids and new_rate_ids[rec.company_id.currency_id_dif.id] > 0:
                    db_rate = new_rate_ids[rec.company_id.currency_id_dif.id]
                else:
                    db_rate = rec.company_id.currency_id_dif.inverse_rate or 0.0
                
                if 0.0 < db_rate < 1.0:
                    new_rate = 1.0 / db_rate
                else:
                    new_rate = db_rate

                if new_rate > 0:
                    rec.tax_today = new_rate
                    rec.foreign_rate = new_rate
                    if rec.company_id.currency_id.name == 'USD':
                        rec.foreign_inverse_rate = new_rate
                    else:
                        rec.foreign_inverse_rate = 1.0 / new_rate
                    rec._onchange_tax_today()

    @api.onchange('tax_today')
    def _onchange_tax_today_sync_ve(self):
        for rec in self:
            if rec.tax_today > 0:
                rec.foreign_rate = rec.tax_today
                if rec.company_id.currency_id.name == 'USD':
                    rec.foreign_inverse_rate = rec.tax_today
                else:
                    rec.foreign_inverse_rate = 1.0 / rec.tax_today

    @api.onchange('foreign_rate')
    def _onchange_foreign_rate_sync_ve(self):
        for rec in self:
            if rec.foreign_rate > 0:
                rec.tax_today = rec.foreign_rate
                if rec.company_id.currency_id.name == 'USD':
                    rec.foreign_inverse_rate = rec.foreign_rate
                else:
                    rec.foreign_inverse_rate = 1.0 / rec.foreign_rate

    @api.onchange('foreign_inverse_rate')
    def _onchange_foreign_inverse_rate_sync_ve(self):
        for rec in self:
            if rec.foreign_inverse_rate > 0:
                if rec.company_id.currency_id.name == 'USD':
                    rec.tax_today = rec.foreign_inverse_rate
                    rec.foreign_rate = rec.foreign_inverse_rate
                else:
                    rec.tax_today = 1.0 / rec.foreign_inverse_rate
                    rec.foreign_rate = 1.0 / rec.foreign_inverse_rate
