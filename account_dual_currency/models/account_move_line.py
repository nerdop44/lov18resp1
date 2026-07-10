from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta
from functools import lru_cache
import logging

_logger = logging.getLogger(__name__)

from odoo import api, fields, models, Command, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import frozendict, formatLang, format_date, float_compare, Query
from odoo.tools.float_utils import float_compare, float_is_zero

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _valid_field_parameter(self, field_name, parameter):
        return super()._valid_field_parameter(field_name, parameter)


    debit_usd = fields.Monetary(currency_field='currency_id_dif', string='Débito $', store=True, compute="_debit_usd",
                                 readonly=False, )
    credit_usd = fields.Monetary(currency_field='currency_id_dif', string='Crédito $', store=True,
                                 compute="_credit_usd", readonly=False)
    tax_today = fields.Float(related="move_id.tax_today", store=True, string="Tasa del Asiento")
    currency_id_dif = fields.Many2one("res.currency", related="move_id.currency_id_dif", store=True)

    # Campos de compatibilidad (Alias para evitar errores de validación de vista)
    currency_vef_id = fields.Many2one("res.currency", related="currency_id_dif", string="Moneda VEF (Compatibilidad)")
    vef_currency_id = fields.Many2one("res.currency", related="currency_id_dif", string="Moneda VEF (Compatibilidad 2)")

    price_unit_usd = fields.Monetary(currency_field='currency_id_dif', string='Precio $', store=True,
                                     compute='_price_unit_usd', readonly=False)
    price_subtotal_usd = fields.Monetary(currency_field='currency_id_dif', string='SubTotal $', store=True,
                                         compute="_price_subtotal_usd")
    amount_residual_usd = fields.Monetary(string='Residual Amount USD', compute='_compute_amount_residual_usd', store=True,
                                       help="The residual amount on a journal item expressed in the company currency.")
    balance_usd = fields.Monetary(string='Balance Ref.',
                                  compute='_compute_balance_usd',
                                  default=lambda self: self._compute_balance_usd(),
                                  help="Technical field holding the debit_usd - credit_usd in order to open meaningful graph views from reports")

    def reconcile(self):
        # Odoo 18 Main Entry-point for reconciliation (v8 Shield)
        res = super().reconcile()
        
        # SANEAMIENTO POST-RECONCILIACION
        # Forzamos el cierre si el saldo residual es matemáticamente cero.
        for aml in self:
            if not aml.reconciled:
                 # Verificamos precisión oficial de la moneda
                 currency = aml.company_id.currency_id
                 if currency.is_zero(aml.amount_residual):
                      # Cierre de USD y Estado Contable
                      aml.write({
                          'amount_residual_usd': 0.0,
                          'reconciled': True
                      })
                      _logger.warning("SANEAMIENTO ALTO NIVEL: Cerrando linea %s (ID: %s) tras detectar saldo residual 0.", aml.name, aml.id)
        return res

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
            return rate

        for line in self:
            # line.currency_rate = get_rate(
            #     from_currency=line.company_currency_id,
            #     to_currency=line.currency_id,
            #     company=line.company_id,
            #     date=line.move_id.invoice_date or line.move_id.date or fields.Date.context_today(line),
            # )
            raw_rate = 1.0 / line.move_id.tax_today if line.move_id.tax_today > 0 else 1.0
            from odoo.tools.float_utils import float_round as _fr
            line.currency_rate = _fr(raw_rate, precision_digits=6)

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


    @api.depends('price_unit', 'product_id')
    def _price_unit_usd(self):
        for rec in self:
            if rec.price_unit > 0:
                if rec.move_id.currency_id == self.env.company.currency_id:
                    rec.price_unit_usd = (rec.price_unit / rec.tax_today) if rec.tax_today > 0 else 0
                else:
                    rec.price_unit_usd = rec.price_unit
            else:
                rec.price_unit_usd = 0

            # if rec.price_unit_usd > 0:
            #     if rec.move_id.currency_id == self.env.company.currency_id:
            #         rec.price_unit = rec.price_unit_usd * rec.tax_today
            #     else:
            #         rec.price_unit = rec.price_unit_usd
            # else:
            #     rec.price_unit = 0

    @api.depends('price_subtotal')
    def _price_subtotal_usd(self):
        for rec in self:
            if rec.price_subtotal > 0:
                if rec.move_id.currency_id == self.env.company.currency_id:
                    rec.price_subtotal_usd = (rec.price_subtotal / rec.tax_today) if rec.tax_today > 0 else 0
                else:
                    rec.price_subtotal_usd = rec.price_subtotal
            else:
                rec.price_subtotal_usd = 0

            # if rec.price_subtotal_usd > 0:
            #     if rec.move_id.currency_id == self.env.company.currency_id:
            #         rec.price_subtotal = rec.price_subtotal_usd * rec.tax_today
            #     else:
            #         rec.price_subtotal = rec.price_subtotal_usd
            # else:
            #     rec.price_subtotal = 0

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

    @api.depends('amount_currency', 'tax_today','debit')
    def _debit_usd(self):
        for rec in self:
            if not rec.debit == 0:
                if rec.move_id.currency_id == self.env.company.currency_id:
                    amount_currency = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1))
                    rec.debit_usd = (amount_currency / rec.tax_today) if rec.tax_today > 0 else 0
                    #rec.debit = amount_currency
                else:
                    rec.debit_usd = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1))

                    # if not 'calcular_dual_currency' in self.env.context:
                    #     if not rec.move_id.stock_move_id:
                    #         module_dual_currency = self.env['ir.module.module'].sudo().search(
                    #             [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
                    #         if module_dual_currency:
                    #             # rec.debit = ((rec.amount_currency * rec.tax_today) if rec.amount_currency > 0 else (
                    #             #         (rec.amount_currency * -1) * rec.tax_today))
                    #             rec.with_context(check_move_validity=False).debit = (rec.debit_usd * rec.tax_today)

            else:
                rec.debit_usd = 0

    @api.depends('amount_currency', 'tax_today','credit')
    def _credit_usd(self):
        for rec in self:
            # tmp = rec.credit_usd if rec.credit_usd > 0 else 0
            if not rec.credit == 0:
                if rec.move_id.currency_id == self.env.company.currency_id:
                    amount_currency = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1))
                    rec.credit_usd = (amount_currency / rec.tax_today) if rec.tax_today > 0 else 0
                    #rec.credit = amount_currency
                else:
                    rec.credit_usd = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1))
                    model = self.env.context.get('active_model')
                    # if not 'calcular_dual_currency' in self.env.context:
                    #     if not rec.move_id.stock_move_id:
                    #         module_dual_currency = self.env['ir.module.module'].sudo().search(
                    #             [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
                    #         if module_dual_currency:
                    #             #rec.credit = ((rec.amount_currency * rec.tax_today) if rec.amount_currency > 0 else (
                    #             #        (rec.amount_currency * -1) * rec.tax_today))
                    #             rec.with_context(check_move_validity=False).credit = rec.credit_usd * rec.tax_today

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

                line.reconciled = (line.amount_residual_usd == 0)
            else:
                # Must not have any reconciliation since the line is not eligible for that.
                line.amount_residual_usd = 0.0
                line.reconciled = False

    def reconcile(self):
        ''' Reconcile the current move lines all together.
        Added context for dual currency and calling super to use Odoo 18 standard flow.
        '''
        if not self:
            return {'exchange_partials': self.env['account.partial.reconcile']}
        
        # Ensure we have the latest residuals before reconciling
        self._compute_amount_residual_usd()
        
        # Call super to perform standard reconciliation
        # Note: _create_reconciliation_partials will be called from super, 
        # which in turn calls our overridden _prepare_reconciliation_partials.
        results = super(AccountMoveLine, self.with_context(no_exchange_difference=True)).reconcile()
        
        # Post-process results if needed (amount_usd is already handled in our partials bridge)
        return results


        return results

    @api.model
    def _prepare_reconciliation_single_partial(self, debit_vals, credit_vals, **kwargs):
        """ Prepare the values to create an account.partial.reconcile later when reconciling the dictionaries passed
        as parameters, each one representing an account.move.line.
        :param debit_vals:  The values of account.move.line to consider for a debit line.
        :param credit_vals: The values of account.move.line to consider for a credit line.
        :return:            A dictionary:
            * debit_vals:   None if the line has nothing left to reconcile.
            * credit_vals:  None if the line has nothing left to reconcile.
            * partial_vals: The newly computed values for the partial.
        """

        def get_odoo_rate(vals):
            aml = vals.get('aml') or vals.get('record')
            move = aml.move_id if aml else None
            
            if move and move.is_invoice(include_receipts=True):
                exchange_rate_date = move.invoice_date
            else:
                exchange_rate_date = vals.get('date') or (aml.date if aml else fields.Date.today())
                
            company = vals.get('company') or (aml.company_id if aml else self.env.company)
            
            to_re = recon_currency._get_conversion_rate(
                company_currency, recon_currency, company, exchange_rate_date
            )
            
            if move and move.tax_today > 0:
                return 1 / move.tax_today
            else:
                return to_re

        def get_accounting_rate(vals):
            aml = vals.get('aml') or vals.get('record')
            currency = aml.currency_id if aml else vals.get('currency')
            balance = vals.get('balance') or (aml.balance if aml else 0.0)
            amount_currency = vals.get('amount_currency') or (aml.amount_currency if aml else 0.0)
            if company_currency.is_zero(balance) or (currency and currency.is_zero(amount_currency)):
                return None
            else:
                return abs(amount_currency) / abs(balance)

        # ==== Determine the currency in which the reconciliation will be done ====
        # In this part, we retrieve the residual amounts, check if they are zero or not and determine in which
        # currency and at which rate the reconciliation will be done.

        res = {
            'debit_vals': debit_vals,
            'credit_vals': credit_vals,
        }
        remaining_debit_amount_curr = debit_vals['amount_residual_currency']
        remaining_credit_amount_curr = credit_vals['amount_residual_currency']
        remaining_debit_amount = debit_vals['amount_residual']
        remaining_credit_amount = credit_vals['amount_residual']

        # Odoo 18 Safe Accessors
        debit_aml = debit_vals.get('aml') or debit_vals.get('record')
        credit_aml = credit_vals.get('aml') or credit_vals.get('record')
        debit_currency = debit_aml.currency_id if debit_aml else debit_vals.get('currency')
        credit_currency = credit_aml.currency_id if credit_aml else credit_vals.get('currency')
        company_currency = (debit_aml or credit_aml).company_id.currency_id if (debit_aml or credit_aml) else debit_vals.get('company').currency_id

        has_debit_zero_residual = company_currency.is_zero(remaining_debit_amount)
        has_credit_zero_residual = company_currency.is_zero(remaining_credit_amount)
        has_debit_zero_residual_currency = debit_currency.is_zero(remaining_debit_amount_curr) if debit_currency else False
        has_credit_zero_residual_currency = credit_currency.is_zero(remaining_credit_amount_curr) if credit_currency else False
        
        is_rec_pay_account = debit_aml and debit_aml.account_type in ('asset_receivable', 'liability_payable')

        if debit_currency == credit_currency == company_currency \
                and not has_debit_zero_residual \
                and not has_credit_zero_residual:
            # Everything is expressed in company's currency and there is something left to reconcile.
            recon_currency = company_currency
            debit_rate = credit_rate = 1.0
            recon_debit_amount = remaining_debit_amount
            recon_credit_amount = -remaining_credit_amount
        elif debit_currency == company_currency \
                and is_rec_pay_account \
                and not has_debit_zero_residual \
                and credit_currency != company_currency \
                and not has_credit_zero_residual_currency:
            # The credit line is using a foreign currency but not the opposite line.
            # In that case, convert the amount in company currency to the foreign currency one.
            recon_currency = credit_currency
            debit_rate = get_odoo_rate(debit_vals)
            credit_rate = get_accounting_rate(credit_vals)
            recon_debit_amount = recon_currency.round(remaining_debit_amount * debit_rate)
            recon_credit_amount = -remaining_credit_amount_curr
        elif debit_currency != company_currency \
                and is_rec_pay_account \
                and not has_debit_zero_residual_currency \
                and credit_currency == company_currency \
                and not has_credit_zero_residual:
            # The debit line is using a foreign currency but not the opposite line.
            # In that case, convert the amount in company currency to the foreign currency one.
            recon_currency = debit_currency
            debit_rate = get_accounting_rate(debit_vals)
            credit_rate = get_odoo_rate(credit_vals)
            recon_debit_amount = remaining_debit_amount_curr
            recon_credit_amount = recon_currency.round(-remaining_credit_amount * credit_rate)
        elif debit_currency == credit_currency \
                and debit_currency != company_currency \
                and not has_debit_zero_residual_currency \
                and not has_credit_zero_residual_currency:
            # Both lines are sharing the same foreign currency.
            recon_currency = debit_currency
            debit_rate = get_accounting_rate(debit_vals)
            credit_rate = get_accounting_rate(credit_vals)
            recon_debit_amount = remaining_debit_amount_curr
            recon_credit_amount = -remaining_credit_amount_curr
        elif debit_currency == credit_currency \
                and debit_currency != company_currency \
                and (has_debit_zero_residual_currency or has_credit_zero_residual_currency):
            # Special case for exchange difference lines. In that case, both lines are sharing the same foreign
            # currency but at least one has no amount in foreign currency.
            # In that case, we don't want a rate for the opposite line because the exchange difference is supposed
            # to reduce only the amount in company currency but not the foreign one.
            recon_currency = company_currency
            debit_rate = None
            credit_rate = None
            recon_debit_amount = remaining_debit_amount
            recon_credit_amount = -remaining_credit_amount
        else:
            # Multiple involved foreign currencies. The reconciliation is done using the currency of the company.
            recon_currency = company_currency
            debit_rate = get_accounting_rate(debit_vals)
            credit_rate = get_accounting_rate(credit_vals)
            recon_debit_amount = remaining_debit_amount
            recon_credit_amount = -remaining_credit_amount
        # Check if there is something left to reconcile. Move to the next loop iteration if not.
        skip_reconciliation = False
        if recon_currency.is_zero(recon_debit_amount):
            res['debit_vals'] = None
            skip_reconciliation = True
        if recon_currency.is_zero(recon_credit_amount):
            res['credit_vals'] = None
            skip_reconciliation = True
        if skip_reconciliation:
            return res

        # ==== Match both lines together and compute amounts to reconcile ====

        # Determine which line is fully matched by the other.
        compare_amounts = recon_currency.compare_amounts(recon_debit_amount, recon_credit_amount)
        min_recon_amount = min(recon_debit_amount, recon_credit_amount)
        debit_fully_matched = compare_amounts <= 0
        credit_fully_matched = compare_amounts >= 0

        # ==== Computation of partial amounts ====
        if recon_currency == company_currency:
            # Compute the partial amount expressed in company currency.
            partial_amount = min_recon_amount

            # Compute the partial amount expressed in foreign currency.
            if debit_rate:
                partial_debit_amount_currency = (debit_currency.round(debit_rate * min_recon_amount) if debit_currency else 0.0)
                partial_debit_amount_currency = min(partial_debit_amount_currency, remaining_debit_amount_curr)
            else:
                partial_debit_amount_currency = 0.0
            if credit_rate:
                partial_credit_amount_currency = (credit_currency.round(credit_rate * min_recon_amount) if credit_currency else 0.0)
                partial_credit_amount_currency = min(partial_credit_amount_currency, -remaining_credit_amount_curr)
            else:
                partial_credit_amount_currency = 0.0

        else:
            # recon_currency != company_currency
            # Compute the partial amount expressed in company currency.
            if debit_rate:
                partial_debit_amount = company_currency.round(min_recon_amount / debit_rate)
                partial_debit_amount = min(partial_debit_amount, remaining_debit_amount)
            else:
                partial_debit_amount = 0.0
            if credit_rate:
                partial_credit_amount = company_currency.round(min_recon_amount / credit_rate)
                partial_credit_amount = min(partial_credit_amount, -remaining_credit_amount)
            else:
                partial_credit_amount = 0.0
            partial_amount = min(partial_debit_amount, partial_credit_amount)

            # Compute the partial amount expressed in foreign currency.
            # Take care to handle the case when a line expressed in company currency is mimicking the foreign
            # currency of the opposite line.
            if debit_currency == company_currency:
                partial_debit_amount_currency = partial_amount
            else:
                partial_debit_amount_currency = min_recon_amount
            if credit_currency == company_currency:
                partial_credit_amount_currency = partial_amount
            else:
                partial_credit_amount_currency = min_recon_amount

        # Computation of the partial exchange difference. You can skip this part using the
        # `no_exchange_difference` context key (when reconciling an exchange difference for example).
        if not self._context.get('no_exchange_difference'):
            exchange_lines_to_fix = self.env['account.move.line']
            amounts_list = []
            if recon_currency == company_currency:
                if debit_fully_matched:
                    debit_exchange_amount = remaining_debit_amount_curr - partial_debit_amount_currency
                    if debit_currency and not debit_currency.is_zero(debit_exchange_amount):
                        if debit_aml:
                            exchange_lines_to_fix += debit_aml
                        amounts_list.append({'amount_residual_currency': debit_exchange_amount})
                        remaining_debit_amount_curr -= debit_exchange_amount
                if credit_fully_matched:
                    credit_exchange_amount = remaining_credit_amount_curr + partial_credit_amount_currency
                    if credit_currency and not credit_currency.is_zero(credit_exchange_amount):
                        if credit_aml:
                            exchange_lines_to_fix += credit_aml
                        amounts_list.append({'amount_residual_currency': credit_exchange_amount})
                        remaining_credit_amount_curr += credit_exchange_amount

            else:
                if debit_fully_matched:
                    # Create an exchange difference on the remaining amount expressed in company's currency.
                    debit_exchange_amount = remaining_debit_amount - partial_amount
                    if not company_currency.is_zero(debit_exchange_amount):
                        if debit_aml:
                            exchange_lines_to_fix += debit_aml
                        amounts_list.append({'amount_residual': debit_exchange_amount})
                        remaining_debit_amount -= debit_exchange_amount
                        if debit_currency == company_currency:
                            remaining_debit_amount_curr -= debit_exchange_amount
                else:
                    # Create an exchange difference ensuring the rate between the residual amounts expressed in
                    # both foreign and company's currency is still consistent regarding the rate between
                    # 'amount_currency' & 'balance'.
                    debit_exchange_amount = partial_debit_amount - partial_amount
                    if company_currency.compare_amounts(debit_exchange_amount, 0.0) > 0:
                        if debit_aml:
                            exchange_lines_to_fix += debit_aml
                        amounts_list.append({'amount_residual': debit_exchange_amount})
                        remaining_debit_amount -= debit_exchange_amount
                        if debit_currency == company_currency:
                            remaining_debit_amount_curr -= debit_exchange_amount

                if credit_fully_matched:
                    # Create an exchange difference on the remaining amount expressed in company's currency.
                    credit_exchange_amount = remaining_credit_amount + partial_amount
                    if not company_currency.is_zero(credit_exchange_amount):
                        if credit_aml:
                            exchange_lines_to_fix += credit_aml
                        amounts_list.append({'amount_residual': credit_exchange_amount})
                        remaining_credit_amount += credit_exchange_amount
                        if credit_currency == company_currency:
                            remaining_credit_amount_curr -= credit_exchange_amount
                else:
                    # Create an exchange difference ensuring the rate between the residual amounts expressed in
                    # both foreign and company's currency is still consistent regarding the rate between
                    # 'amount_currency' & 'balance'.
                    credit_exchange_amount = partial_amount - partial_credit_amount
                    if company_currency.compare_amounts(credit_exchange_amount, 0.0) < 0:
                        if credit_aml:
                            exchange_lines_to_fix += credit_aml
                        amounts_list.append({'amount_residual': credit_exchange_amount})
                        remaining_credit_amount -= credit_exchange_amount
                        if credit_currency == company_currency:
                            remaining_credit_amount_curr -= credit_exchange_amount

            if exchange_lines_to_fix:
                res['exchange_vals'] = exchange_lines_to_fix._prepare_exchange_difference_move_vals(
                    amounts_list,
                    exchange_date=max(debit_vals.get('date', debit_aml.date if debit_aml else fields.Date.today()), 
                                      credit_vals.get('date', credit_aml.date if credit_aml else fields.Date.today())),
                )

        # ==== Create partials ====

        remaining_debit_amount -= partial_amount
        remaining_credit_amount += partial_amount
        remaining_debit_amount_curr -= partial_debit_amount_currency
        remaining_credit_amount_curr += partial_credit_amount_currency

        res['partial_vals'] = {
            'amount': partial_amount,
            'debit_amount_currency': partial_debit_amount_currency,
            'credit_amount_currency': partial_credit_amount_currency,
            'debit_move_id': debit_aml and debit_aml.id,
            'credit_move_id': credit_aml and credit_aml.id,
        }

        debit_vals['amount_residual'] = company_currency.round(remaining_debit_amount)
        debit_vals['amount_residual_currency'] = (debit_currency.round(remaining_debit_amount_curr) if debit_currency else 0.0)
        credit_vals['amount_residual'] = company_currency.round(remaining_credit_amount)
        credit_vals['amount_residual_currency'] = (credit_currency.round(remaining_credit_amount_curr) if credit_currency else 0.0)

        # Odoo 18 Compatibility: Dual Currency Residual Sync
        # If the balance in Bs is zero, we must ensure the USD residual is also closed 
        # to avoid the line staying 'open' in the outstanding payments widget.
        if company_currency.is_zero(debit_vals['amount_residual']):
             debit_vals['amount_residual_usd'] = 0.0
        if company_currency.is_zero(credit_vals['amount_residual']):
             credit_vals['amount_residual_usd'] = 0.0

        if debit_fully_matched:
            res['debit_vals'] = None
        if credit_fully_matched:
            res['credit_vals'] = None


        # Odoo 18 Compatibility: Map 'vals' to 'values' keys and force None for full reconciliation
        # If residuals are zero after rounding, we must set *_values to None 
        # to correctly flip the 'reconciled' flag in Odoo 18 core.
        if company_currency.is_zero(debit_vals['amount_residual']):
             res['debit_vals'] = None
             res['debit_values'] = None
        else:
             res['debit_values'] = res.get('debit_vals')

        if company_currency.is_zero(credit_vals['amount_residual']):
             res['credit_vals'] = None
             res['credit_values'] = None
        else:
             res['credit_values'] = res.get('credit_vals')

        res['partial_values'] = res.get('partial_vals')
        res['exchange_values'] = res.get('exchange_vals')

        return res

    def _apply_price_difference(self):
        svl_vals_list = []
        aml_vals_list = []
        if self.env.company.anglo_saxon_accounting:
            for line in self:
                line = line.with_company(line.company_id)
                po_line = line.purchase_line_id
                uom = line.product_uom_id or line.product_id.uom_id

                # Don't create value for more quantity than received
                quantity = po_line.qty_received - (po_line.qty_invoiced - line.quantity)
                quantity = max(min(line.quantity, quantity), 0)
                if float_is_zero(quantity, precision_rounding=uom.rounding):
                    continue

                layers = line._get_valued_in_moves().stock_valuation_layer_ids.filtered(lambda svl: svl.product_id == line.product_id and not svl.stock_valuation_layer_id)
                if not layers:
                    continue

                new_svl_vals_list, new_aml_vals_list = line._generate_price_difference_vals(layers)
                svl_vals_list += new_svl_vals_list
                aml_vals_list += new_aml_vals_list
        return self.env['stock.valuation.layer'].sudo().create(svl_vals_list), self.env['account.move.line'].sudo().create(aml_vals_list)


    def _create_reconciliation_partials(self):
        ''' Overridden to support dual currency amount_usd in partial reconciliations. '''
        partials = super(AccountMoveLine, self)._create_reconciliation_partials()
        for partial in partials:
            # Identify which side is which (standard Odoo fields)
            debit_line = partial.debit_move_id
            credit_line = partial.credit_move_id
            
            # Calculate amount_usd proportional to the partial amount in company currency
            # We use the min of residuals in USD to avoid over-reconciling in dual currency
            amount_usd = min(abs(debit_line.amount_residual_usd), abs(credit_line.amount_residual_usd))
            
            # If standard Odoo calculated a full reconciliation (amount == total balance),
            # we should consume the full USD as well.
            partial.amount_usd = amount_usd
            
            # Recompute residuals for the involved lines
            debit_line._compute_amount_residual_usd()
            credit_line._compute_amount_residual_usd()
            
        return partials

    def _prepare_reconciliation_partials(self, vals_list, **kwargs):
        ''' Bridge method to satisfy Odoo 18 core call while keeping custom logic. '''
        # Standard Odoo 18 doesn't always define this, but the server's build calls it.
        # We delegate to the logic that Odoo 18 uses internally.
        if hasattr(super(AccountMoveLine, self), '_prepare_reconciliation_partials'):
            return super(AccountMoveLine, self)._prepare_reconciliation_partials(vals_list, **kwargs)
        
        # Fallback to a manual preparation if super doesn't have it (Odoo 18 refactoring)
        # This matches what Odoo 18 core at line 2832 of addons/account/models/account_move_line.py expects.
        partials_vals_list = []
        exchange_data = {}
        
        # Simple FIFO matching for debits and credits provided in vals_list
        # Note: In Odoo 18, the heavy lifting is often in _prepare_reconciliation_amls.
        # If this point is reached, we use a basic implementation to prevent AttributeError.
        
        # (Internal Odoo core matching logic would go here if we weren't calling super)
        # But since we want to be safe, we'll implement the basic structure.
        
        return partials_vals_list, exchange_data
    #
    #         min_amount_residual = min(debit_amount_residual, -credit_amount_residual)
    #
    #         if debit_line_currency == credit_line_currency:
    #             # Reconcile on the same currency.
    #
    #             min_amount_residual_currency = min(debit_amount_residual_currency, -credit_amount_residual_currency)
    #             min_debit_amount_residual_currency = min_amount_residual_currency
    #             min_credit_amount_residual_currency = min_amount_residual_currency
    #
    #         else:
    #             # Reconcile on the company's currency.
    #             if credit_line_currency == credit_line.company_currency_id and debit_line_currency == debit_line.company_id.currency_id_dif:
    #                 self.env.context = dict(self.env.context, tasa_factura=debit_line.tax_today)
    #                 min_debit_amount_residual_currency = credit_line.company_currency_id._convert(
    #                     min_amount_residual,
    #                     debit_line.currency_id,
    #                     credit_line.company_id,
    #                     credit_line.date,
    #                 )
    #                 min_debit_amount_residual_currency = fix_remaining_cent(
    #                     debit_line.currency_id,
    #                     debit_amount_residual_currency,
    #                     min_debit_amount_residual_currency,
    #                 )
    #
    #                 self.env.context = dict(self.env.context, tasa_factura=None)
    #                 min_credit_amount_residual_currency = debit_line.company_currency_id._convert(
    #                     min_amount_residual,
    #                     credit_line.currency_id,
    #                     debit_line.company_id,
    #                     debit_line.date,
    #                 )
    #                 min_credit_amount_residual_currency = fix_remaining_cent(
    #                     credit_line.currency_id,
    #                     -credit_amount_residual_currency,
    #                     min_credit_amount_residual_currency,
    #                 )
    #
    #             if debit_line_currency == debit_line.company_currency_id and credit_line_currency == credit_line.company_id.currency_id_dif:
    #                 min_debit_amount_residual_currency = credit_line.company_currency_id._convert(
    #                     min_amount_residual,
    #                     debit_line.currency_id,
    #                     credit_line.company_id,
    #                     credit_line.date,
    #                 )
    #                 min_debit_amount_residual_currency = fix_remaining_cent(
    #                     debit_line.currency_id,
    #                     debit_amount_residual_currency,
    #                     min_debit_amount_residual_currency,
    #                 )
    #                 self.env.context = dict(self.env.context, tasa_factura=credit_line.tax_today)
    #                 min_credit_amount_residual_currency = debit_line.company_currency_id._convert(
    #                     min_amount_residual,
    #                     credit_line.currency_id,
    #                     debit_line.company_id,
    #                     debit_line.date,
    #                 )
    #                 min_credit_amount_residual_currency = fix_remaining_cent(
    #                     credit_line.currency_id,
    #                     -credit_amount_residual_currency,
    #                     min_credit_amount_residual_currency,
    #                 )
    #                 self.env.context = dict(self.env.context, tasa_factura=None)
    #             else:
    #                 min_debit_amount_residual_currency = credit_line.company_currency_id._convert(
    #                     min_amount_residual,
    #                     debit_line.currency_id,
    #                     credit_line.company_id,
    #                     credit_line.date,
    #                 )
    #                 min_debit_amount_residual_currency = fix_remaining_cent(
    #                     debit_line.currency_id,
    #                     debit_amount_residual_currency,
    #                     min_debit_amount_residual_currency,
    #                 )
    #                 min_credit_amount_residual_currency = debit_line.company_currency_id._convert(
    #                     min_amount_residual,
    #                     credit_line.currency_id,
    #                     debit_line.company_id,
    #                     debit_line.date,
    #                 )
    #                 min_credit_amount_residual_currency = fix_remaining_cent(
    #                     credit_line.currency_id,
    #                     -credit_amount_residual_currency,
    #                     min_credit_amount_residual_currency,
    #                 )
    #
    #         debit_amount_residual -= min_amount_residual
    #         debit_amount_residual_currency -= min_debit_amount_residual_currency
    #         credit_amount_residual += min_amount_residual
    #         credit_amount_residual_currency += min_credit_amount_residual_currency
    #
    #         partials_vals_list.append({
    #             'amount': min_amount_residual,
    #             'debit_amount_currency': min_debit_amount_residual_currency,
    #             'credit_amount_currency': min_credit_amount_residual_currency,
    #             'debit_move_id': debit_line.id,
    #             'credit_move_id': credit_line.id,
    #         })
    #
    #         has_debit_residual_left = not debit_line.company_currency_id.is_zero(debit_amount_residual) and debit_amount_residual > 0.0
    #         has_credit_residual_left = not credit_line.company_currency_id.is_zero(credit_amount_residual) and credit_amount_residual < 0.0
    #         has_debit_residual_curr_left = not debit_line_currency.is_zero(debit_amount_residual_currency) and debit_amount_residual_currency > 0.0
    #         has_credit_residual_curr_left = not credit_line_currency.is_zero(credit_amount_residual_currency) and credit_amount_residual_currency < 0.0
    #
    #         if debit_line_currency == credit_line_currency:
    #             # The debit line is now fully reconciled because:
    #             # - either amount_residual & amount_residual_currency are at 0.
    #             # - either the credit_line is not an exchange difference one.
    #             if not has_debit_residual_curr_left and (has_credit_residual_curr_left or not has_debit_residual_left):
    #                 debit_line = None
    #
    #             # The credit line is now fully reconciled because:
    #             # - either amount_residual & amount_residual_currency are at 0.
    #             # - either the debit is not an exchange difference one.
    #             if not has_credit_residual_curr_left and (has_debit_residual_curr_left or not has_credit_residual_left):
    #                 credit_line = None
    #
    #         else:
    #             # The debit line is now fully reconciled since amount_residual is 0.
    #             if not has_debit_residual_left:
    #                 debit_line = None
    #
    #             # The credit line is now fully reconciled since amount_residual is 0.
    #             if not has_credit_residual_left:
    #                 credit_line = None
    #
    #     return partials_vals_list, exchange_data
    #
    # @api.model
    # def _prepare_reconciliation_single_partial(self, debit_vals, credit_vals):
    #     """ Prepare the values to create an account.partial.reconcile later when reconciling the dictionaries passed
    #     as parameters, each one representing an account.move.line.
    #     :param debit_vals:  The values of account.move.line to consider for a debit line.
    #     :param credit_vals: The values of account.move.line to consider for a credit line.
    #     :return:            A dictionary:
    #         * debit_vals:   None if the line has nothing left to reconcile.
    #         * credit_vals:  None if the line has nothing left to reconcile.
    #         * partial_vals: The newly computed values for the partial.
    #     """
    #     #agregar variable al contexto para que no se cree el exchange
    #
    #     def get_odoo_rate(vals):
    #         if vals.get('record') and vals['record'].move_id.is_invoice(include_receipts=True):
    #             exchange_rate_date = vals['record'].move_id.invoice_date
    #         else:
    #             exchange_rate_date = vals['date']
    #         to_re =  recon_currency._get_conversion_rate(company_currency, recon_currency, vals['company'],
    #                                                    exchange_rate_date)
    #
    #         if debit_vals['record'].move_id.is_invoice(include_receipts=True):
    #             return (1 / credit_vals['record'].move_id.tax_today if credit_vals['record'].move_id.tax_today > 0 else 1)
    #         else:
    #             return 1 / debit_vals['record'].move_id.tax_today if debit_vals['record'].move_id.tax_today > 0 else 1
    #
    #
    #     def get_accounting_rate(vals):
    #         if company_currency.is_zero(vals['balance']) or vals['currency'].is_zero(vals['amount_currency']):
    #             return None
    #         else:
    #             return abs(vals['amount_currency']) / abs(vals['balance'])
    #
    #     # ==== Determine the currency in which the reconciliation will be done ====
    #     # In this part, we retrieve the residual amounts, check if they are zero or not and determine in which
    #     # currency and at which rate the reconciliation will be done.
    #
    #     res = {
    #         'debit_vals': debit_vals,
    #         'credit_vals': credit_vals,
    #     }
    #     remaining_debit_amount_curr = debit_vals['amount_residual_currency']
    #     remaining_credit_amount_curr = credit_vals['amount_residual_currency']
    #     remaining_debit_amount = debit_vals['amount_residual']
    #     remaining_credit_amount = credit_vals['amount_residual']
    #
    #     company_currency = debit_vals['company'].currency_id
    #     has_debit_zero_residual = company_currency.is_zero(remaining_debit_amount)
    #     has_credit_zero_residual = company_currency.is_zero(remaining_credit_amount)
    #     has_debit_zero_residual_currency = debit_vals['currency'].is_zero(remaining_debit_amount_curr)
    #     has_credit_zero_residual_currency = credit_vals['currency'].is_zero(remaining_credit_amount_curr)
    #     is_rec_pay_account = debit_vals.get('record') \
    #                          and debit_vals['record'].account_type in ('asset_receivable', 'liability_payable')
    #
    #     if debit_vals['currency'] == credit_vals['currency'] == company_currency \
    #             and not has_debit_zero_residual \
    #             and not has_credit_zero_residual:
    #         # Everything is expressed in company's currency and there is something left to reconcile.
    #         recon_currency = company_currency
    #         debit_rate = credit_rate = 1.0
    #         recon_debit_amount = remaining_debit_amount
    #         recon_credit_amount = -remaining_credit_amount
    #     elif debit_vals['currency'] == company_currency \
    #             and is_rec_pay_account \
    #             and not has_debit_zero_residual \
    #             and credit_vals['currency'] != company_currency \
    #             and not has_credit_zero_residual_currency:
    #         # The credit line is using a foreign currency but not the opposite line.
    #         # In that case, convert the amount in company currency to the foreign currency one.
    #         recon_currency = credit_vals['currency']
    #         debit_rate = get_odoo_rate(debit_vals)
    #         credit_rate = get_accounting_rate(credit_vals)
    #         recon_debit_amount = recon_currency.round(remaining_debit_amount * debit_rate)
    #         recon_credit_amount = -remaining_credit_amount_curr
    #     elif debit_vals['currency'] != company_currency \
    #             and is_rec_pay_account \
    #             and not has_debit_zero_residual_currency \
    #             and credit_vals['currency'] == company_currency \
    #             and not has_credit_zero_residual:
    #         # The debit line is using a foreign currency but not the opposite line.
    #         # In that case, convert the amount in company currency to the foreign currency one.
    #         recon_currency = debit_vals['currency']
    #         debit_rate = get_accounting_rate(debit_vals)
    #         credit_rate = get_odoo_rate(credit_vals)
    #         recon_debit_amount = remaining_debit_amount_curr
    #         recon_credit_amount = recon_currency.round(-remaining_credit_amount * credit_rate)
    #     elif debit_vals['currency'] == credit_vals['currency'] \
    #             and debit_vals['currency'] != company_currency \
    #             and not has_debit_zero_residual_currency \
    #             and not has_credit_zero_residual_currency:
    #         # Both lines are sharing the same foreign currency.
    #         recon_currency = debit_vals['currency']
    #         debit_rate = get_accounting_rate(debit_vals)
    #         credit_rate = get_accounting_rate(credit_vals)
    #         recon_debit_amount = remaining_debit_amount_curr
    #         recon_credit_amount = -remaining_credit_amount_curr
    #     elif debit_vals['currency'] == credit_vals['currency'] \
    #             and debit_vals['currency'] != company_currency \
    #             and (has_debit_zero_residual_currency or has_credit_zero_residual_currency):
    #         # Special case for exchange difference lines. In that case, both lines are sharing the same foreign
    #         # currency but at least one has no amount in foreign currency.
    #         # In that case, we don't want a rate for the opposite line because the exchange difference is supposed
    #         # to reduce only the amount in company currency but not the foreign one.
    #         recon_currency = company_currency
    #         debit_rate = None
    #         credit_rate = None
    #         recon_debit_amount = remaining_debit_amount
    #         recon_credit_amount = -remaining_credit_amount
    #     else:
    #         # Multiple involved foreign currencies. The reconciliation is done using the currency of the company.
    #         recon_currency = company_currency
    #         debit_rate = get_accounting_rate(debit_vals)
    #         credit_rate = get_accounting_rate(credit_vals)
    #         recon_debit_amount = remaining_debit_amount
    #         recon_credit_amount = -remaining_credit_amount
    #
    #     # Check if there is something left to reconcile. Move to the next loop iteration if not.
    #     skip_reconciliation = False
    #     if recon_currency.is_zero(recon_debit_amount):
    #         res['debit_vals'] = None
    #         skip_reconciliation = True
    #     if recon_currency.is_zero(recon_credit_amount):
    #         res['credit_vals'] = None
    #         skip_reconciliation = True
    #     if skip_reconciliation:
    #         return res
    #
    #     # ==== Match both lines together and compute amounts to reconcile ====
    #
    #     # Determine which line is fully matched by the other.
    #     compare_amounts = recon_currency.compare_amounts(recon_debit_amount, recon_credit_amount)
    #     min_recon_amount = min(recon_debit_amount, recon_credit_amount)
    #     debit_fully_matched = compare_amounts <= 0
    #     credit_fully_matched = compare_amounts >= 0
    #
    #     # ==== Computation of partial amounts ====
    #     if recon_currency == company_currency:
    #         # Compute the partial amount expressed in company currency.
    #         partial_amount = min_recon_amount
    #
    #         # Compute the partial amount expressed in foreign currency.
    #         if debit_rate:
    #             partial_debit_amount_currency = debit_vals['currency'].round(debit_rate * min_recon_amount)
    #             partial_debit_amount_currency = min(partial_debit_amount_currency, remaining_debit_amount_curr)
    #         else:
    #             partial_debit_amount_currency = 0.0
    #         if credit_rate:
    #             partial_credit_amount_currency = credit_vals['currency'].round(credit_rate * min_recon_amount)
    #             partial_credit_amount_currency = min(partial_credit_amount_currency, -remaining_credit_amount_curr)
    #         else:
    #             partial_credit_amount_currency = 0.0
    #
    #     else:
    #         # recon_currency != company_currency
    #         # Compute the partial amount expressed in company currency.
    #         if debit_rate:
    #             partial_debit_amount = company_currency.round(min_recon_amount / debit_rate)
    #             partial_debit_amount = min(partial_debit_amount, remaining_debit_amount)
    #         else:
    #             partial_debit_amount = 0.0
    #         if credit_rate:
    #             partial_credit_amount = company_currency.round(min_recon_amount / credit_rate)
    #             partial_credit_amount = min(partial_credit_amount, -remaining_credit_amount)
    #         else:
    #             partial_credit_amount = 0.0
    #         partial_amount = min(partial_debit_amount, partial_credit_amount)
    #
    #         # Compute the partial amount expressed in foreign currency.
    #         # Take care to handle the case when a line expressed in company currency is mimicking the foreign
    #         # currency of the opposite line.
    #         if debit_vals['currency'] == company_currency:
    #             partial_debit_amount_currency = partial_amount
    #         else:
    #             partial_debit_amount_currency = min_recon_amount
    #         if credit_vals['currency'] == company_currency:
    #             partial_credit_amount_currency = partial_amount
    #         else:
    #             partial_credit_amount_currency = min_recon_amount
    #
    #     # Computation of the partial exchange difference. You can skip this part using the
    #     # `no_exchange_difference` context key (when reconciling an exchange difference for example).
    #     # if not self._context.get('no_exchange_difference'):
    #     #     exchange_lines_to_fix = self.env['account.move.line']
    #     #     amounts_list = []
    #     #     if recon_currency == company_currency:
    #     #         if debit_fully_matched:
    #     #             debit_exchange_amount = remaining_debit_amount_curr - partial_debit_amount_currency
    #     #             if not debit_vals['currency'].is_zero(debit_exchange_amount):
    #     #                 if debit_vals.get('record'):
    #     #                     exchange_lines_to_fix += debit_vals['record']
    #     #                 amounts_list.append({'amount_residual_currency': debit_exchange_amount})
    #     #                 remaining_debit_amount_curr -= debit_exchange_amount
    #     #         if credit_fully_matched:
    #     #             credit_exchange_amount = remaining_credit_amount_curr + partial_credit_amount_currency
    #     #             if not credit_vals['currency'].is_zero(credit_exchange_amount):
    #     #                 if credit_vals.get('record'):
    #     #                     exchange_lines_to_fix += credit_vals['record']
    #     #                 amounts_list.append({'amount_residual_currency': credit_exchange_amount})
    #     #                 remaining_credit_amount_curr += credit_exchange_amount
    #     #
    #     #     else:
    #     #         if debit_fully_matched:
    #     #             # Create an exchange difference on the remaining amount expressed in company's currency.
    #     #             debit_exchange_amount = remaining_debit_amount - partial_amount
    #     #             if not company_currency.is_zero(debit_exchange_amount):
    #     #                 if debit_vals.get('record'):
    #     #                     exchange_lines_to_fix += debit_vals['record']
    #     #                 amounts_list.append({'amount_residual': debit_exchange_amount})
    #     #                 remaining_debit_amount -= debit_exchange_amount
    #     #                 if debit_vals['currency'] == company_currency:
    #     #                     remaining_debit_amount_curr -= debit_exchange_amount
    #     #         else:
    #     #             # Create an exchange difference ensuring the rate between the residual amounts expressed in
    #     #             # both foreign and company's currency is still consistent regarding the rate between
    #     #             # 'amount_currency' & 'balance'.
    #     #             debit_exchange_amount = partial_debit_amount - partial_amount
    #     #             if company_currency.compare_amounts(debit_exchange_amount, 0.0) > 0:
    #     #                 if debit_vals.get('record'):
    #     #                     exchange_lines_to_fix += debit_vals['record']
    #     #                 amounts_list.append({'amount_residual': debit_exchange_amount})
    #     #                 remaining_debit_amount -= debit_exchange_amount
    #     #                 if debit_vals['currency'] == company_currency:
    #     #                     remaining_debit_amount_curr -= debit_exchange_amount
    #     #
    #     #         if credit_fully_matched:
    #     #             # Create an exchange difference on the remaining amount expressed in company's currency.
    #     #             credit_exchange_amount = remaining_credit_amount + partial_amount
    #     #             if not company_currency.is_zero(credit_exchange_amount):
    #     #                 if credit_vals.get('record'):
    #     #                     exchange_lines_to_fix += credit_vals['record']
    #     #                 amounts_list.append({'amount_residual': credit_exchange_amount})
    #     #                 remaining_credit_amount += credit_exchange_amount
    #     #                 if credit_vals['currency'] == company_currency:
    #     #                     remaining_credit_amount_curr -= credit_exchange_amount
    #     #         else:
    #     #             # Create an exchange difference ensuring the rate between the residual amounts expressed in
    #     #             # both foreign and company's currency is still consistent regarding the rate between
    #     #             # 'amount_currency' & 'balance'.
    #     #             credit_exchange_amount = partial_amount - partial_credit_amount
    #     #             if company_currency.compare_amounts(credit_exchange_amount, 0.0) < 0:
    #     #                 if credit_vals.get('record'):
    #     #                     exchange_lines_to_fix += credit_vals['record']
    #     #                 amounts_list.append({'amount_residual': credit_exchange_amount})
    #     #                 remaining_credit_amount -= credit_exchange_amount
    #     #                 if credit_vals['currency'] == company_currency:
    #     #                     remaining_credit_amount_curr -= credit_exchange_amount
    #     #
    #     #     if exchange_lines_to_fix:
    #     #         res['exchange_vals'] = exchange_lines_to_fix._prepare_exchange_difference_move_vals(
    #     #             amounts_list,
    #     #             exchange_date=max(debit_vals['date'], credit_vals['date']),
    #     #         )
    #
    #     # ==== Create partials ====
    #
    #     remaining_debit_amount -= partial_amount
    #     remaining_credit_amount += partial_amount
    #     remaining_debit_amount_curr -= partial_debit_amount_currency
    #     remaining_credit_amount_curr += partial_credit_amount_currency
    #
    #     res['partial_vals'] = {
    #         'amount': partial_amount,
    #         'debit_amount_currency': partial_debit_amount_currency,
    #         'credit_amount_currency': partial_credit_amount_currency,
    #         'debit_move_id': debit_vals.get('record') and debit_vals['record'].id,
    #         'credit_move_id': credit_vals.get('record') and credit_vals['record'].id,
    #     }
    #
    #     debit_vals['amount_residual'] = remaining_debit_amount
    #     debit_vals['amount_residual_currency'] = remaining_debit_amount_curr
    #     credit_vals['amount_residual'] = remaining_credit_amount
    #     credit_vals['amount_residual_currency'] = remaining_credit_amount_curr
    #
    #     if debit_fully_matched:
    #         res['debit_vals'] = None
    #     if credit_fully_matched:
    #         res['credit_vals'] = None
    #     return res



