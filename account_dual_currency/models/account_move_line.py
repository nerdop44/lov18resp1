from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta
from functools import lru_cache

from odoo import api, fields, models, Command, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import frozendict, formatLang, format_date, float_compare, Query
from odoo.tools.float_utils import float_compare, float_is_zero

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _valid_field_parameter(self, field_name, parameter):
        return super()._valid_field_parameter(field_name, parameter)


    debit_usd = fields.Monetary(currency_field='currency_id_dif', string='Débito Ref.', store=True, compute="_debit_usd",
                                 readonly=False, )
    credit_usd = fields.Monetary(currency_field='currency_id_dif', string='Crédito Ref.', store=True,
                                 compute="_credit_usd", readonly=False)
    tax_today = fields.Float(related="move_id.tax_today", store=True, string="Tasa del Asiento")
    currency_id_dif = fields.Many2one("res.currency", related="move_id.currency_id_dif", store=True)
    price_unit_usd = fields.Monetary(currency_field='currency_id_dif', string='Precio Ref.', store=True,
                                     compute='_price_unit_usd', readonly=False)
    price_subtotal_usd = fields.Monetary(currency_field='currency_id_dif', string='SubTotal Ref.', store=True,
                                         compute="_price_subtotal_usd")
    amount_residual_usd = fields.Monetary(string='Residual Amount USD', compute='_compute_amount_residual_usd', store=True,
                                       help="The residual amount on a journal item expressed in the company currency.")
    balance_usd = fields.Monetary(string='Balance Ref.',
                                  currency_field='currency_id_dif', store=True, readonly=False,
                                  compute='_compute_balance_usd',
                                  default=lambda self: self._compute_balance_usd(),
                                  help="Technical field holding the debit_usd - credit_usd in order to open meaningful graph views from reports")

    @api.depends('currency_id', 'company_id', 'move_id.date','move_id.tax_today')
    def _compute_currency_rate(self):

        @lru_cache()
        def get_rate(from_currency, to_currency, company, date):
            rate = self.env['res.currency']._get_conversion_rate(
                from_currency=from_currency,
                to_currency=to_currency,
                company=company,
                date=date,
            )
            #print('pasando por get_rate', rate)
            return rate

        for line in self:
            self.env.context = dict(self.env.context, tasa_factura=line.move_id.tax_today, calcular_dual_currency=True)
            if line.currency_id == line.company_currency_id:
                line.currency_rate = 1.0
            elif line.move_id.tax_today > 0:
                line.currency_rate = line.move_id.tax_today
            else:
                line.currency_rate = 1.0
        self.env.context = dict(self.env.context, tasa_factura=None, calcular_dual_currency=False)

    @api.onchange('amount_currency')
    def _onchange_amount_currency(self):
        self._debit_usd()
        self._credit_usd()

    @api.onchange('price_unit_usd')
    def _onchange_price_unit_usd(self):
        for rec in self:
            if rec.move_id.currency_id != rec.company_id.currency_id:
                rec.price_unit = rec.price_unit_usd
            else:
                rec.price_unit = rec.price_unit_usd * rec.tax_today


    @api.onchange('product_id')
    def _onchange_product_id(self):
        #super()._onchange_product_id()
        self._price_unit_usd()

    @api.depends('debit_usd', 'credit_usd')
    def _compute_balance_usd(self):
        for line in self:
            line.balance_usd = line.debit_usd - line.credit_usd


    @api.depends('price_unit', 'product_id', 'move_id.tax_today')
    def _price_unit_usd(self):
        for rec in self:
            is_company_usd = rec.company_id.currency_id.name == 'USD'
            rate = rec.tax_today if rec.tax_today > 0 else 1.0
            if rec.price_unit > 0:
                if is_company_usd:
                    if rec.move_id.currency_id == rec.company_id.currency_id:
                        rec.price_unit_usd = rec.price_unit * rate
                    else:
                        rec.price_unit_usd = rec.price_unit
                else:
                    if rec.move_id.currency_id == rec.company_id.currency_id:
                        rec.price_unit_usd = (rec.price_unit / rate) if rate > 0 else 0
                    else:
                        rec.price_unit_usd = rec.price_unit
            else:
                rec.price_unit_usd = 0

    @api.depends('price_subtotal', 'move_id.tax_today')
    def _price_subtotal_usd(self):
        for rec in self:
            is_company_usd = rec.company_id.currency_id.name == 'USD'
            rate = rec.tax_today if rec.tax_today > 0 else 1.0
            if rec.price_subtotal > 0:
                if is_company_usd:
                    if rec.move_id.currency_id == rec.company_id.currency_id:
                        rec.price_subtotal_usd = rec.price_subtotal * rate
                    else:
                        rec.price_subtotal_usd = rec.price_subtotal
                else:
                    if rec.move_id.currency_id == rec.company_id.currency_id:
                        rec.price_subtotal_usd = (rec.price_subtotal / rate) if rate > 0 else 0
                    else:
                        rec.price_subtotal_usd = rec.price_subtotal
            else:
                rec.price_subtotal_usd = 0

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        if 'tax_today' not in fields:
            return super(AccountMoveLine, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                           orderby=orderby, lazy=lazy)
        res = super(AccountMoveLine, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                      orderby=orderby, lazy=lazy)
        for group in res:
            if group.get('__domain'):
                records = self.search(group['__domain'])
                group['tax_today'] = 0
        return res

    @api.depends('amount_currency', 'tax_today', 'debit', 'move_id.amount_total_usd')
    def _debit_usd(self):
        for rec in self:
            is_company_usd = rec.company_id.currency_id.name == 'USD'
            rate = rec.tax_today if rec.tax_today > 0 else 1.0
            if not rec.debit == 0 or (is_company_usd and rec.amount_currency > 0):
                if is_company_usd:
                    if rec.move_id.currency_id == rec.company_id.currency_id:
                        if rec.move_id and rec.move_id.is_invoice(include_receipts=True) and rec.account_id.account_type in ('asset_receivable', 'liability_payable') and rec.move_id.amount_total_usd:
                            rec.debit_usd = rec.move_id.amount_total_usd
                        else:
                            rec.debit_usd = abs(rec.amount_currency) * rate if rec.amount_currency else rec.debit * rate
                    else:
                        rec.debit_usd = abs(rec.amount_currency) if rec.amount_currency else abs(rec.debit)
                else:
                    if rec.move_id.currency_id == rec.company_id.currency_id:
                        amount_currency = abs(rec.amount_currency) if rec.amount_currency else abs(rec.debit)
                        rec.debit_usd = (amount_currency / rate) if rate > 0 else 0
                    else:
                        rec.debit_usd = abs(rec.amount_currency) if rec.amount_currency else abs(rec.debit)
            else:
                rec.debit_usd = 0

    @api.depends('amount_currency', 'tax_today', 'credit', 'move_id.amount_total_usd')
    def _credit_usd(self):
        for rec in self:
            is_company_usd = rec.company_id.currency_id.name == 'USD'
            rate = rec.tax_today if rec.tax_today > 0 else 1.0
            if not rec.credit == 0 or (is_company_usd and rec.amount_currency < 0):
                if is_company_usd:
                    if rec.move_id.currency_id == rec.company_id.currency_id:
                        if rec.move_id and rec.move_id.is_invoice(include_receipts=True) and rec.account_id.account_type in ('asset_receivable', 'liability_payable') and rec.move_id.amount_total_usd:
                            rec.credit_usd = rec.move_id.amount_total_usd
                        else:
                            rec.credit_usd = abs(rec.amount_currency) * rate if rec.amount_currency else rec.credit * rate
                    else:
                        rec.credit_usd = abs(rec.amount_currency) if rec.amount_currency else abs(rec.credit)
                else:
                    if rec.move_id.currency_id == rec.company_id.currency_id:
                        amount_currency = abs(rec.amount_currency) if rec.amount_currency else abs(rec.credit)
                        rec.credit_usd = (amount_currency / rate) if rate > 0 else 0
                    else:
                        rec.credit_usd = abs(rec.amount_currency) if rec.amount_currency else abs(rec.credit)
            else:
                rec.credit_usd = 0

    @api.depends('debit','credit','debit_usd', 'credit_usd', 'amount_currency', 'account_id', 'currency_id', 'move_id.state',
                 'company_id',
                 'matched_debit_ids', 'matched_credit_ids')
    def _compute_amount_residual_usd(self):
        """ Computes the residual amount of a move line from a reconcilable account in the company currency and the line's currency.
            This amount will be 0 for fully reconciled lines or lines from a non-reconcilable account, the original line amount
            for unreconciled lines, and something in-between for partially reconciled lines.
        """
        for line in self:
            if line.id and (line.account_id.reconcile or line.account_id.account_type in ('asset_cash', 'liability_credit_card')):
                reconciled_balance = sum(line.matched_credit_ids.mapped('amount_usd')) \
                                     - sum(line.matched_debit_ids.mapped('amount_usd'))

                line.amount_residual_usd = (line.debit_usd - line.credit_usd) - reconciled_balance
            else:
                # Must not have any reconciliation since the line is not eligible for that.
                line.amount_residual_usd = 0.0


    def reconcile(self):
        ''' Reconcile the current move lines all together.
        '''
        self = self.with_context(no_exchange_difference=True)
        res = super().reconcile()

        # Post-reconcile: Actualizar amount_usd en las líneas de reconciliación parcial creadas
        partials = (self.matched_debit_ids | self.matched_credit_ids).sorted('id')
        new_partials = partials.filtered(lambda p: not p.amount_usd)
        new_partial_ids = set(new_partials.ids)

        rem_usd = {}
        for p in new_partials:
            debit = p.debit_move_id
            credit = p.credit_move_id

            if debit not in rem_usd:
                # El saldo inicial en USD disponible es el total en USD de la línea
                # menos lo ya reconciliado por otros parciales existentes fuera de este lote nuevo
                already_reconciled = sum(other.amount_usd for other in debit.matched_credit_ids if other.id not in new_partial_ids)
                rem_usd[debit] = max(0.0, (debit.debit_usd or 0.0) - already_reconciled)

            if credit not in rem_usd:
                already_reconciled = sum(other.amount_usd for other in credit.matched_debit_ids if other.id not in new_partial_ids)
                rem_usd[credit] = max(0.0, (credit.credit_usd or 0.0) - already_reconciled)

            # Calculamos el USD a asignar en base a lo disponible en memoria de forma secuencial
            amt_usd = min(rem_usd[debit], rem_usd[credit])

            # Descontamos de lo disponible para la siguiente iteración del loop
            rem_usd[debit] -= amt_usd
            rem_usd[credit] -= amt_usd

            p.write({'amount_usd': amt_usd})
        return res

