import logging
from collections import defaultdict

_logger = logging.getLogger(__name__)
from datetime import timedelta
from itertools import groupby

from odoo import api, fields, models, _, Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_is_zero, float_compare
from odoo.osv.expression import AND, OR
from odoo.service.common import exp_version

class PosSession(models.Model):
    _inherit = "pos.session"

    tax_today = fields.Float(string="Tasa Sesión", store=True,
                             compute="_tax_today",
                             tracking=True, digits=(16, 4))

    ref_me_currency_id = fields.Many2one('res.currency', related='config_id.show_currency', string="Reference Currency",
                                         store=False)
    cash_register_difference_ref = fields.Monetary(
        compute='_compute_cash_balance_ref',
        string='Ref Before Closing Difference',
        currency_field='ref_me_currency_id',
        help="Difference between the ref theoretical closing balance and the ref real closing balance.",
        readonly=True)

    cash_register_balance_start_mn_ref = fields.Monetary(
        string="Reference Starting Balance",
        currency_field='ref_me_currency_id',
        readonly=True)

    cash_register_balance_end_real_mn_ref = fields.Monetary(
        string="Reference Ending Balance",
        currency_field='ref_me_currency_id',
        readonly=True)
    me_ref_cash_journal_id = fields.Many2one('account.journal', compute='_compute_cash_all', string='Ref Cash Journal',
                                             store=True)

    cash_register_total_entry_encoding_ref = fields.Monetary(
        compute='_compute_cash_balance_ref',
        string='Ref Total Cash Transaction',
        currency_field='ref_me_currency_id',
        readonly=True)

    cash_register_balance_end_ref = fields.Monetary(
        compute='_compute_cash_balance_ref',
        string="Ref Theoretical Closing Balance",
        currency_field='ref_me_currency_id',
        help="Opening balance summed to all cash transactions.",
        readonly=True)
    cash_real_transaction_ref = fields.Monetary(string='Transaction', currency_field='ref_me_currency_id',
                                                readonly=True)

    def set_cashbox_pos_usd(self, cashbox_value, notes):
        difference = cashbox_value - self.cash_register_balance_start_mn_ref
        self.cash_register_balance_start_mn_ref = cashbox_value
        self.sudo()._post_statement_difference_usd(difference)
        self._post_cash_details_message_usd('Opening', difference, notes)

    def _post_cash_details_message_usd(self, state, difference, notes):
        message = ""
        if difference:
            message = f"{state} difference: " \
                      f"{self.ref_me_currency_id.symbol + ' ' if self.ref_me_currency_id.position == 'before' else ''}" \
                      f"{self.ref_me_currency_id.round(difference)} " \
                      f"{self.ref_me_currency_id.symbol if self.ref_me_currency_id.position == 'after' else ''}<br/>"
        if notes:
            message += notes.replace('\n', '<br/>')
        if message:
            self.message_post(body=message)

    @api.model
    def _load_pos_data(self, data):
        _logger.info(">>>>>>>> _load_pos_data called for Dual Currency <<<<<<<<")
        result = super()._load_pos_data(data)
        
        # Injected data for dual currency display
        company_currency_id = self.company_id.currency_id.id
        currency_id = company_currency_id
        
        # Priority: 1. Config "Show Currency" (if different from company)
        #           2. Company "Currency Dif" (if different from company)
        #           3. Fallback to any other active currency? (Not implemented to avoid randomness)
        
        target_currency = self.ref_me_currency_id if self.ref_me_currency_id else self.config_id.show_currency
        
        if target_currency and target_currency.id != company_currency_id:
             currency_id = target_currency.id
        elif self.company_id.currency_id_dif and self.company_id.currency_id_dif.id != company_currency_id:
             currency_id = self.company_id.currency_id_dif.id
        
        # --- ROBUST VEF/Bs SELECTION LOGIC ---
        # Search for VEF/VES currency by Name OR Symbol
        vef_currency = self.env['res.currency'].search([
            '|', ('name', 'in', ['VES', 'VEF']), ('symbol', 'in', ['Bs', 'Bs.', 'Bs']),
            ('active', '=', True)
        ], limit=1)

        _logger.info(">>>>>>>> Debug [Dual Currency]: Company ID: %s, Initial Dual ID: %s", company_currency_id, currency_id)
        _logger.info(">>>>>>>> Debug [Dual Currency]: VEF Currency Found: %s (ID: %s)", vef_currency.name if vef_currency else 'None', vef_currency.id if vef_currency else 'None')

        if vef_currency:
             should_force_vef = False
             
             # Case 1: No dual currency selected yet (currency_id is False or None)
             if not currency_id:
                 should_force_vef = True
                 _logger.info(">>>>>>>> Debug [Dual Currency]: Case 1 - No dual currency selected. Forcing VEF.")
             
             # Case 2: Selected dual currency is explicitly USD
             elif currency_id:
                 curr = self.env['res.currency'].browse(currency_id)
                 if curr.name == 'USD':
                     should_force_vef = True
                     _logger.info(">>>>>>>> Debug [Dual Currency]: Case 2 - USD selected. Forcing VEF.")
            
             # Case 3: Selected matches Company, and Company is USD
             if not should_force_vef and currency_id == company_currency_id:
                 comp_curr = self.company_id.currency_id
                 if comp_curr.name == 'USD':
                     should_force_vef = True
                     _logger.info(">>>>>>>> Debug [Dual Currency]: Case 3 - Company is USD. Forcing VEF.")
            
             if should_force_vef:
                 currency_id = vef_currency.id
                 _logger.info(">>>>>>>> Debug [Dual Currency]: FORCED SWAP to VEF/Bs (ID: %s)", currency_id)

        # Fallback: If we match company currency (e.g. Company=VEF), try to fallback to USD
        if currency_id == company_currency_id:
             _logger.info(">>>>>>>> Debug [Dual Currency]: Dual matches Company. Checking for fallback to USD.")
             if vef_currency and company_currency_id == vef_currency.id:
                 # Company is VEF. Dual is VEF. We likely want USD.
                 usd_currency = self.env['res.currency'].search([('name', '=', 'USD'), ('active', '=', True)], limit=1)
                 if usd_currency:
                     currency_id = usd_currency.id
                     _logger.info(">>>>>>>> Debug [Dual Currency]: Swapped to USD (ID: %s) because Company is VEF.", currency_id)

        _logger.info(">>>>>>>> Debug [Dual Currency]: FINAL SELECTION ID=%s <<<<<<<<", currency_id)
        
        # Debug: List all active currencies to see what's available
        all_currencies = self.env['res.currency'].search_read([('active', '=', True)], ['name', 'symbol'])
        _logger.info(">>>>>>>> Debug: All Active Currencies: %s <<<<<<<<", all_currencies)

        currency_fields = ['id', 'name', 'symbol', 'position', 'rounding', 'rate', 'decimal_places']
        currency_ref = self.env['res.currency'].search_read([('id', '=', currency_id)], currency_fields)
        _logger.info(">>>>>>>> Debug: currency_ref found=%s <<<<<<<<", len(currency_ref) if currency_ref else 0)
        
        if currency_ref:
            # Odoo 18 _load_pos_data returns a dict with 'data' and 'fields'
            _logger.info(">>>>>>>> Debug: result keys=%s <<<<<<<<", list(result.keys()) if result else 'None')
            
            # Fetch the official TRM (Tasa) for the reference currency
            # Ensure we get a float
            rate_tasa = 0.0
            try:
                rate_tasa = self.env['res.currency'].get_trm_systray()
                if not isinstance(rate_tasa, (int, float)):
                     rate_tasa = float(rate_tasa)
            except Exception as e:
                _logger.error("Error getting TRM: %s", e)
                # Fallback to currency rate if TRM fails
                rate_tasa = currency_ref[0].get('rate', 1.0)
            
            currency_ref[0]['rate'] = rate_tasa  # Inject the "Tasa" instead of native Odoo rate
            
            if result and 'data' in result and result['data']:
                result['data'][0]['res_currency_ref'] = currency_ref[0]
                _logger.info(">>>>>>>> Injected res_currency_ref: %s with rate %s <<<<<<<<", currency_ref[0]['name'], rate_tasa)
            else:
                _logger.warning(">>>>>>>> Debug: result['data'] is empty! <<<<<<<<")
        
        return result

    def try_cash_in_out_ref_currency(self, _type, amount, reason, extras, currency_ref):
        sign = 1 if _type == 'in' else -1
        sessions = self.filtered('me_ref_cash_journal_id')
        if not sessions:
            raise UserError(_("There is no cash payment method for this PoS Session"))

        self.env['account.bank.statement.line'].create([
            {
                'pos_session_id': session.id,
                'journal_id': session.me_ref_cash_journal_id.id,
                'amount': sign * amount,
                'date': fields.Date.context_today(self),
                'payment_ref': '-'.join([session.name, extras['translatedType'], reason]),
                'currency_id': session.ref_me_currency_id.id,
            }
            for session in sessions
        ])

        message_content = [f"Cash {extras['translatedType']}", f'- Amount: {extras["formattedAmount"]}']
        if reason:
            message_content.append(f'- Reason: {reason}')
        self.message_post(body='<br/>\n'.join(message_content))

    @api.depends('config_id', 'payment_method_ids')
    def _compute_cash_all(self):
        super(PosSession, self)._compute_cash_all()
        for session in self:
            session.me_ref_cash_journal_id = False
            cash_journal_ref = session.payment_method_ids.filtered(
                lambda p: p.is_cash_count and p.currency_id == session.ref_me_currency_id)[:1].journal_id
            if not cash_journal_ref:
                continue
            session.me_ref_cash_journal_id = cash_journal_ref

    # def get_closing_control_data(self):
    #     if not self.env.user.has_group('point_of_sale.group_pos_user'):
    #         raise AccessError(_("You don't have the access rights to get the point of sale closing control data."))
    #     self.ensure_one()
    #     orders = self.order_ids.filtered(lambda o: o.state == 'paid' or o.state == 'invoiced')
    #     payments = orders.payment_ids.filtered(lambda p: p.payment_method_id.type != "pay_later")
    #     pay_later_payments = orders.payment_ids - payments
    #     cash_payment_method_ids = self.payment_method_ids.filtered(lambda pm: pm.type == 'cash' and (pm.currency_id == self.company_id.currency_id or not pm.currency_id ))
    #     print(cash_payment_method_ids)
    #     default_cash_payment_method_id = cash_payment_method_ids[0] if cash_payment_method_ids else None
    #     total_default_cash_payment_amount = sum(payments.filtered(lambda p: p.payment_method_id == default_cash_payment_method_id).mapped('amount')) if default_cash_payment_method_id else 0
    #     other_payment_method_ids = self.payment_method_ids - default_cash_payment_method_id if default_cash_payment_method_id else self.payment_method_ids
    #     cash_in_count = 0
    #     cash_out_count = 0
    #     cash_in_out_list = []
    #     last_session = self.search([('config_id', '=', self.config_id.id), ('id', '!=', self.id)], limit=1)
    #     for cash_move in self.sudo().statement_line_ids.sorted('create_date'):
    #         if cash_move.amount > 0:
    #             cash_in_count += 1
    #             name = f'Cash in {cash_in_count}'
    #         else:
    #             cash_out_count += 1
    #             name = f'Cash out {cash_out_count}'
    #         cash_in_out_list.append({
    #             'name': cash_move.payment_ref if cash_move.payment_ref else name,
    #             'amount': cash_move.amount
    #         })
    #
    #     closing_control_data = {
    #         'orders_details': {
    #             'quantity': len(orders),
    #             'amount': sum(orders.mapped('amount_total'))
    #         },
    #         'payments_amount': sum(payments.mapped('amount')),
    #         'pay_later_amount': sum(pay_later_payments.mapped('amount')),
    #         'opening_notes': self.opening_notes,
    #         'default_cash_details': {
    #             'name': default_cash_payment_method_id.name,
    #             'amount': last_session.cash_register_balance_end_real
    #                       + total_default_cash_payment_amount
    #                       + sum(self.sudo().statement_line_ids.mapped('amount')),
    #             'opening': last_session.cash_register_balance_end_real,
    #             'payment_amount': total_default_cash_payment_amount,
    #             'moves': cash_in_out_list,
    #             'id': default_cash_payment_method_id.id
    #         } if default_cash_payment_method_id else None,
    #         'other_payment_methods': [{
    #             'name': pm.name,
    #             'amount': sum(orders.payment_ids.filtered(lambda p: p.payment_method_id == pm).mapped('amount')),
    #             'number': len(orders.payment_ids.filtered(lambda p: p.payment_method_id == pm)),
    #             'id': pm.id,
    #             'type': pm.type,
    #         } for pm in other_payment_method_ids],
    #         'is_manager': self.env.user.has_group("point_of_sale.group_pos_manager"),
    #         'amount_authorized_diff': self.config_id.amount_authorized_diff if self.config_id.set_maximum_difference else None
    #     }
    #
    #
    #
    #
    #     #closing_control_data = super(PosSession, self).get_closing_control_data()
    #     #self.ensure_one()
    #     orders = self.order_ids.filtered(lambda o: o.state == 'paid' or o.state == 'invoiced')
    #     payments = orders.payment_ids.filtered(lambda p: p.payment_method_id.type != "pay_later")
    #     cash_payment_method_ref_ids = self.payment_method_ids.filtered(
    #         lambda pm: pm.type == 'cash' and pm.currency_id == self.ref_me_currency_id)
    #     default_cash_payment_ref_method_id = cash_payment_method_ref_ids[0] if cash_payment_method_ref_ids else None
    #     print(default_cash_payment_ref_method_id)
    #     total_default_cash_ref_payment_amount = sum(
    #         payments.filtered(lambda p: p.payment_method_id == default_cash_payment_ref_method_id).mapped(
    #             'amount_ref')) if default_cash_payment_ref_method_id else 0
    #     cash_payment_method_ids = self.payment_method_ids.filtered(
    #         lambda pm: pm.type == 'cash' and pm.currency_id != self.ref_me_currency_id)
    #     print(cash_payment_method_ids)
    #     default_cash_payment_method_id = cash_payment_method_ids[0] if cash_payment_method_ids else None
    #     other_payment_method_ids = self.payment_method_ids - default_cash_payment_ref_method_id if default_cash_payment_ref_method_id else self.payment_method_ids
    #     other_payment_method_update_ids = other_payment_method_ids - default_cash_payment_method_id if default_cash_payment_method_id else other_payment_method_ids
    #     cash_in_count = 0
    #     cash_out_count = 0
    #     cash_in_count_ref = 0
    #     cash_out_count_ref = 0
    #     cash_in_out_list = []
    #     cash_in_out_list_ref = []
    #     last_session = self.search([('config_id', '=', self.config_id.id), ('id', '!=', self.id)], limit=1)
    #     for cash_move in self.statement_line_ids.sorted('create_date'):
    #         if cash_move.currency_id == self.ref_me_currency_id:
    #             if cash_move.amount > 0:
    #                 cash_in_count_ref += 1
    #                 name = f'Cash in {cash_in_count_ref}'
    #             else:
    #                 cash_out_count_ref += 1
    #                 name = f'Cash out {cash_out_count_ref}'
    #             cash_in_out_list_ref.append({
    #                 'name': cash_move.payment_ref if cash_move.payment_ref else name,
    #                 'amount': cash_move.amount
    #             })
    #         else:
    #             if cash_move.amount > 0:
    #                 cash_in_count += 1
    #                 name = f'Cash in {cash_in_count}'
    #             else:
    #                 cash_out_count += 1
    #                 name = f'Cash out {cash_out_count}'
    #             cash_in_out_list.append({
    #                 'name': cash_move.payment_ref if cash_move.payment_ref else name,
    #                 'amount': cash_move.amount
    #             })
    #
    #     default_cash_details_ref = {
    #         'name': default_cash_payment_ref_method_id.name,
    #         'amount': last_session.cash_register_balance_end_real_mn_ref
    #                   + total_default_cash_ref_payment_amount
    #                   + sum(
    #             self.statement_line_ids.filtered(lambda s: s.currency_id == self.ref_me_currency_id).mapped('amount')),
    #         'opening': last_session.cash_register_balance_end_real_mn_ref,
    #         'moves': cash_in_out_list_ref,
    #         'payment_amount': total_default_cash_ref_payment_amount,
    #         'id': default_cash_payment_ref_method_id.id,
    #     } if default_cash_payment_ref_method_id else {
    #         'name': None,
    #         'amount': last_session.cash_register_balance_end_real_mn_ref
    #                   + total_default_cash_ref_payment_amount
    #                   + sum(
    #             self.statement_line_ids.filtered(lambda s: s.currency_id == self.ref_me_currency_id).mapped('amount')),
    #         'opening': last_session.cash_register_balance_end_real_mn_ref,
    #         'moves': cash_in_out_list_ref,
    #         'payment_amount': total_default_cash_ref_payment_amount,
    #         'id': None,
    #     }
    #     if 'default_cash_details' in closing_control_data:
    #         if closing_control_data['default_cash_details']:
    #             closing_control_data['default_cash_details']['amount'] = closing_control_data['default_cash_details'][
    #                                                                          'amount'] - sum(
    #                 self.statement_line_ids.filtered(lambda s: s.currency_id == self.ref_me_currency_id).mapped(
    #                     'amount'))
    #             closing_control_data['default_cash_details']['default_cash_details_ref'] = default_cash_details_ref
    #             closing_control_data['default_cash_details']['moves'] = cash_in_out_list
    #     closing_control_data['other_payment_methods'] = [{
    #         'name': pm.name,
    #         'amount': sum(orders.payment_ids.filtered(lambda p: p.payment_method_id == pm).mapped('amount')),
    #         'number': len(orders.payment_ids.filtered(lambda p: p.payment_method_id == pm)),
    #         'id': pm.id,
    #         'type': pm.type,
    #     } for pm in other_payment_method_update_ids]
    #     closing_control_data[
    #         'amount_authorized_diff_ref'] = self.config_id.amount_authorized_diff_ref if self.config_id.set_maximum_difference else None
    #     return closing_control_data

    def get_closing_control_data(self):
        closing_control_data = super(PosSession, self).get_closing_control_data()
        self.ensure_one()
        orders = self.order_ids.filtered(lambda o: o.state == 'paid' or o.state == 'invoiced')
        payments = orders.payment_ids.filtered(lambda p: p.payment_method_id.type != "pay_later")
        cash_payment_method_ref_ids = self.payment_method_ids.filtered(
            lambda pm: pm.type == 'cash' and pm.currency_id == self.ref_me_currency_id)
        default_cash_payment_ref_method_id = cash_payment_method_ref_ids[0] if cash_payment_method_ref_ids else None
        total_default_cash_ref_payment_amount = sum(
            payments.filtered(lambda p: p.payment_method_id == default_cash_payment_ref_method_id).mapped(
                'amount_ref')) if default_cash_payment_ref_method_id else 0
        cash_payment_method_ids = self.payment_method_ids.filtered(
            lambda pm: pm.type == 'cash' and pm.currency_id != self.ref_me_currency_id)
        default_cash_payment_method_id = cash_payment_method_ids[0] if cash_payment_method_ids else None
        other_payment_method_ids = self.payment_method_ids - default_cash_payment_ref_method_id if default_cash_payment_ref_method_id else self.payment_method_ids
        other_payment_method_update_ids = other_payment_method_ids - default_cash_payment_method_id if default_cash_payment_method_id else other_payment_method_ids
        cash_in_count = 0
        cash_out_count = 0
        cash_in_count_ref = 0
        cash_out_count_ref = 0
        cash_in_out_list = []
        cash_in_out_list_ref = []
        last_session = self.search([('config_id', '=', self.config_id.id), ('id', '!=', self.id)], limit=1)
        for cash_move in self.statement_line_ids.sorted('create_date'):
            if cash_move.currency_id == self.ref_me_currency_id:
                if cash_move.amount > 0:
                    cash_in_count_ref += 1
                    name = f'Cash in {cash_in_count_ref}'
                else:
                    cash_out_count_ref += 1
                    name = f'Cash out {cash_out_count_ref}'
                cash_in_out_list_ref.append({
                    'name': cash_move.payment_ref if cash_move.payment_ref else name,
                    'amount': cash_move.amount
                })
            else:
                if cash_move.amount > 0:
                    cash_in_count += 1
                    name = f'Cash in {cash_in_count}'
                else:
                    cash_out_count += 1
                    name = f'Cash out {cash_out_count}'
                cash_in_out_list.append({
                    'name': cash_move.payment_ref if cash_move.payment_ref else name,
                    'amount': cash_move.amount
                })

        default_cash_details_ref = {
            'name': default_cash_payment_ref_method_id.name,
            'amount': last_session.cash_register_balance_end_real_mn_ref
                      + total_default_cash_ref_payment_amount
                      + sum(
                self.statement_line_ids.filtered(lambda s: s.currency_id == self.ref_me_currency_id).mapped('amount')),
            'opening': last_session.cash_register_balance_end_real_mn_ref,
            'moves': cash_in_out_list_ref,
            'payment_amount': total_default_cash_ref_payment_amount,
            'id': default_cash_payment_ref_method_id.id,
        } if default_cash_payment_ref_method_id else {
            'name': None,
            'amount': last_session.cash_register_balance_end_real_mn_ref
                      + total_default_cash_ref_payment_amount
                      + sum(
                self.statement_line_ids.filtered(lambda s: s.currency_id == self.ref_me_currency_id).mapped('amount')),
            'opening': last_session.cash_register_balance_end_real_mn_ref,
            'moves': cash_in_out_list_ref,
            'payment_amount': total_default_cash_ref_payment_amount,
            'id': None,
        }
        if 'default_cash_details' in closing_control_data:
            if closing_control_data['default_cash_details']:
                closing_control_data['default_cash_details']['amount'] = closing_control_data['default_cash_details'][
                                                                             'amount'] - sum(
                    self.statement_line_ids.filtered(lambda s: s.currency_id == self.ref_me_currency_id).mapped(
                        'amount'))
                closing_control_data['default_cash_details']['default_cash_details_ref'] = default_cash_details_ref
                closing_control_data['default_cash_details']['moves'] = cash_in_out_list
        closing_control_data['other_payment_methods'] = [{
            'name': pm.name,
            'amount': sum(orders.payment_ids.filtered(lambda p: p.payment_method_id == pm).mapped('amount')),
            'number': len(orders.payment_ids.filtered(lambda p: p.payment_method_id == pm)),
            'id': pm.id,
            'type': pm.type,
        } for pm in other_payment_method_update_ids]
        closing_control_data[
            'amount_authorized_diff_ref'] = self.config_id.amount_authorized_diff_ref if self.config_id.set_maximum_difference else None
        return closing_control_data

    def post_closing_cash_details_ref(self, counted_cash):
        if not self.me_ref_cash_journal_id:
            pass
            #raise UserError(_("There is no Ref cash register in this session."))
        self.cash_register_balance_end_real_mn_ref = counted_cash
        return {'successful': True}

    def _post_statement_difference_usd(self, amount):
        if amount:
            if self.config_id.cash_control:
                st_line_vals = {
                    'journal_id': self.me_ref_cash_journal_id.id,
                    'amount': amount,
                    'date': self.statement_line_ids.sorted()[-1:].date or fields.Date.context_today(self),
                    'pos_session_id': self.id,
                    'currency_id': self.ref_me_currency_id.id,
                }

            if amount < 0.0:
                if not self.me_ref_cash_journal_id.loss_account_id:
                    raise UserError(
                        _('Please go on the %s journal and define a Loss Account. This account will be used to record cash difference.',
                          self.me_ref_cash_journal_id.name))

                st_line_vals['payment_ref'] = _("Cash difference observed during the counting (Loss)")
                st_line_vals['counterpart_account_id'] = self.me_ref_cash_journal_id.loss_account_id.id
            else:
                # self.cash_register_difference  > 0.0
                if not self.me_ref_cash_journal_id.profit_account_id:
                    raise UserError(
                        _('Please go on the %s journal and define a Profit Account. This account will be used to record cash difference.',
                          self.cash_journal_id.name))

                st_line_vals['payment_ref'] = _("Cash difference observed during the counting (Profit)")
                st_line_vals['counterpart_account_id'] = self.me_ref_cash_journal_id.profit_account_id.id

            self.env['account.bank.statement.line'].create(st_line_vals)

    def update_closing_control_state_session_ref(self, notes):
        self._post_cash_details_message_usd('Closing', self.cash_register_difference_ref, notes)

    @api.depends('payment_method_ids', 'order_ids', 'cash_register_balance_start_mn_ref')
    def _compute_cash_balance_ref(self):
        for session in self:
            cash_payment_method = session.payment_method_ids.filtered(
                lambda p: p.is_cash_count and p.currency_id == session.ref_me_currency_id)[:1]
            if cash_payment_method:
                total_cash_payment = 0.0
                last_session = session.search([('config_id', '=', session.config_id.id), ('id', '!=', session.id)],
                                              limit=1)
                result = self.env['pos.payment']._read_group(
                    [('session_id', '=', session.id), ('payment_method_id', '=', cash_payment_method.id)], ['session_id'],
                    ['amount:sum'])
                if result:
                    total_cash_payment = result[0]['amount']
                session.cash_register_total_entry_encoding_ref = sum(
                    session.statement_line_ids.filtered(lambda s: s.currency_id == session.ref_me_currency_id).mapped(
                        'amount')) + (
                                                                     0.0 if session.state == 'closed' else total_cash_payment
                                                                 )
                session.cash_register_balance_end_ref = last_session.cash_register_balance_end_real_mn_ref + session.cash_register_total_entry_encoding_ref
                session.cash_register_difference_ref = session.cash_register_balance_end_real_mn_ref - session.cash_register_balance_end_ref
            else:
                session.cash_register_total_entry_encoding_ref = 0.0
                session.cash_register_balance_end_ref = 0.0
                session.cash_register_difference_ref = 0.0

    def close_session_from_ui_ref(self, bank_payment_method_diff_pairs=None):
        bank_payment_method_diffs = dict(bank_payment_method_diff_pairs or [])
        self.ensure_one()
        # Even if this is called in `post_closing_cash_details`, we need to call this here too for case
        # where cash_control = False
        check_closing_session = self._cannot_close_session_ref(bank_payment_method_diffs)
        if check_closing_session:
            return check_closing_session

        validate_result = self.action_pos_session_closing_control_ref(
            bank_payment_method_diffs=bank_payment_method_diffs)

        # If an error is raised, the user will still be redirected to the back end to manually close the session.
        # If the return result is a dict, this means that normally we have a redirection or a wizard => we redirect the user
        if isinstance(validate_result, dict):
            # imbalance accounting entry
            return {
                'successful': False,
                'message': validate_result.get('name'),
                'redirect': True
            }

        self.message_post(body='Point of Sale Session ended')

        return {'successful': True}

    def _cannot_close_session_ref(self, bank_payment_method_diffs=None):
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        if any(order.state == 'draft' for order in self.order_ids):
            return {'successful': False, 'message': _("You cannot close the POS when orders are still in draft"),
                    'redirect': False}
        if self.state == 'closed':
            return {'successful': False, 'message': _("This session is already closed."), 'redirect': True}
        if bank_payment_method_diffs:
            no_loss_account = self.env['account.journal']
            no_profit_account = self.env['account.journal']
            for payment_method in self.env['pos.payment.method'].browse(bank_payment_method_diffs.keys()):
                journal = payment_method.journal_id
                compare_to_zero = self.ref_me_currency_id.compare_amounts(
                    bank_payment_method_diffs.get(payment_method.id), 0)
                if compare_to_zero == -1 and not journal.loss_account_id:
                    no_loss_account |= journal
                elif compare_to_zero == 1 and not journal.profit_account_id:
                    no_profit_account |= journal
            message = ''
            if no_loss_account:
                message += _("Need loss account for the following journals to post the lost amount: %s\n",
                             ', '.join(no_loss_account.mapped('name')))
            if no_profit_account:
                message += _("Need profit account for the following journals to post the gained amount: %s",
                             ', '.join(no_profit_account.mapped('name')))
            if message:
                return {'successful': False, 'message': message, 'redirect': False}

    def action_pos_session_closing_control_ref(self, balancing_account=False, amount_to_balance=0,
                                               bank_payment_method_diffs=None):
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        for session in self:
            if any(order.state == 'draft' for order in session.order_ids):
                raise UserError(_("You cannot close the POS when orders are still in draft"))
            if session.state == 'closed':
                raise UserError(_('This session is already closed.'))
            session.write({'state': 'closing_control', 'stop_at': fields.Datetime.now()})
            if not session.config_id.cash_control:
                return session.action_pos_session_close_ref(balancing_account, amount_to_balance,
                                                            bank_payment_method_diffs)
            # If the session is in rescue, we only compute the payments in the cash register
            # It is not yet possible to close a rescue session through the front end, see `close_session_from_ui`
            if session.rescue and session.config_id.cash_control:
                default_cash_payment_method_id = self.payment_method_ids.filtered(
                    lambda pm: pm.type == 'cash' and pm.payment_method_id.currency_id == self.ref_me_currency_id)[0]
                orders = self.order_ids.filtered(lambda o: o.state == 'paid' or o.state == 'invoiced')
                total_cash = sum(
                    orders.payment_ids.filtered(lambda p: p.payment_method_id == default_cash_payment_method_id).mapped(
                        'amount')
                ) + self.cash_register_balance_start_mn_ref

                session.cash_register_balance_end_real_mn_ref = total_cash

            return session.action_pos_session_validate_ref(balancing_account, amount_to_balance,
                                                           bank_payment_method_diffs)

    def action_pos_session_close_ref(self, balancing_account=False, amount_to_balance=0,
                                     bank_payment_method_diffs=None):
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        # Session without cash payment method will not have a cash register.
        # However, there could be other payment methods, thus, session still
        # needs to be validated.
        return self._validate_session_ref(balancing_account, amount_to_balance, bank_payment_method_diffs)

    def _validate_session_ref(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        self.ensure_one()
        sudo = self.env.user.has_group('point_of_sale.group_pos_user')
        if self.order_ids or self.statement_line_ids:
            self.cash_real_transaction_ref = sum(
                self.statement_line_ids.filtered(lambda s: s.currency_id == self.ref_me_currency_id).mapped('amount'))
            cash_difference_before_statements = self.cash_register_difference_ref
            try:
                data = self.with_company(self.company_id).with_context(check_move_validity=False,
                                                                       skip_invoice_sync=True)._create_account_move(
                    balancing_account, amount_to_balance, bank_payment_method_diffs)
            except AccessError as e:
                if sudo:
                    data = self.sudo().with_company(self.company_id).with_context(check_move_validity=False,
                                                                                  skip_invoice_sync=True)._create_account_move(
                        balancing_account, amount_to_balance, bank_payment_method_diffs)
                else:
                    raise e

            try:
                balance = sum(self.move_id.line_ids.mapped('balance'))
                with self.move_id._check_balanced({'records': self.move_id.sudo()}):
                    pass
            except UserError:
                self.env.cr.rollback()
                return self._close_session_action(balance)
            self.sudo()._post_statement_difference(cash_difference_before_statements)
            if self.move_id.line_ids:
                self.move_id.sudo().with_company(self.company_id)._post()
            else:
                self.move_id.sudo().unlink()
            self.sudo().with_company(self.company_id)._reconcile_account_move_lines(data)
        else:
            self.sudo()._post_statement_difference_usd(self.cash_register_difference_ref)
        return True

    def action_pos_session_validate_ref(self, balancing_account=False, amount_to_balance=0,
                                        bank_payment_method_diffs=None):
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        return self.action_pos_session_close_ref(balancing_account, amount_to_balance, bank_payment_method_diffs)

    @api.model
    def _loader_params_pos_config(self):
        result = super()._loader_params_pos_config()
        result['search_params']['fields'].extend([
            'show_dual_currency',
            'show_currency',
            'show_currency_rate',
            'show_currency_symbol',
            'show_currency_position',
        ])
        return result

    def _loader_params_pos_session(self):
        search_params = super(PosSession, self)._loader_params_pos_session()
        fields = search_params['search_params']['fields']
        fields.append('cash_register_balance_start_mn_ref')
        return search_params

    def action_pos_session_open(self):
        for session in self.filtered(lambda session: session.state == 'opening_control'):
            if session.config_id.cash_control and not session.rescue:
                last_session = self.search([('config_id', '=', session.config_id.id), ('id', '!=', session.id)],
                                           limit=1)
                session.cash_register_balance_start_mn_ref = last_session.cash_register_balance_end_real_mn_ref  # defaults to 0 if lastsession is empty
        return super(PosSession, self).action_pos_session_open()


    @api.depends('config_id')
    def _tax_today(self):
        for rec in self:
            rec.tax_today = 1 / rec.config_id.show_currency_rate if rec.config_id.show_currency_rate > 0 else 1

    def _loader_params_pos_payment_method(self):
        result = super()._loader_params_pos_payment_method()
        result['search_params']['fields'].append('currency_id')
        return result

    # def _get_pos_ui_pos_payment_method(self, params):
    #     payment_ids_new = []
    #     payment_ids = self.env['pos.payment.method'].search_read(**params['search_params'])
    #     payment_company_currency = []
    #     for payment in payment_ids:
    #         if payment.get('currency_id') == self.company_id.currency_id.id or not payment.get('currency_id'):
    #             payment_company_currency.append(payment)
    #     payment_ids_new.append(payment_company_currency)
    #     for payment in payment_ids:
    #         if payment.get('currency_id') != self.company_id.currency_id.id or payment.get('currency_id'):
    #             payment_ids_new.append(payment)
    #     print(payment_ids_new)
    #     return payment_ids_new

    def _create_cash_statement_lines_and_cash_move_lines(self, data):
        # Create the split and combine cash statement lines and account move lines.
        # `split_cash_statement_lines` maps `journal` -> split cash statement lines
        # `combine_cash_statement_lines` maps `journal` -> combine cash statement lines
        # `split_cash_receivable_lines` maps `journal` -> split cash receivable lines
        # `combine_cash_receivable_lines` maps `journal` -> combine cash receivable lines
        MoveLine = data.get('MoveLine')
        split_receivables_cash = data.get('split_receivables_cash')
        combine_receivables_cash = data.get('combine_receivables_cash')

        # handle split cash payments
        split_cash_statement_line_vals = []
        split_cash_receivable_vals = []
        for payment, amounts in split_receivables_cash.items():
            journal_id = payment.payment_method_id.journal_id.id
            split_cash_statement_line_vals.append(
                self._get_split_statement_line_vals(
                    journal_id,
                    amounts['amount'] if (payment.payment_method_id.currency_id == self.company_id.currency_id or not payment.payment_method_id.currency_id) else amounts['amount'] * self.config_id.show_currency_rate,
                    payment
                )
            )
            split_cash_receivable_vals.append(
                self._get_split_receivable_vals(
                    payment,
                    amounts['amount'] if (payment.payment_method_id.currency_id == self.company_id.currency_id or not payment.payment_method_id.currency_id) else amounts['amount'] * self.config_id.show_currency_rate,
                    amounts['amount_converted']
                )
            )
        # handle combine cash payments
        combine_cash_statement_line_vals = []
        combine_cash_receivable_vals = []
        for payment_method, amounts in combine_receivables_cash.items():
            if not float_is_zero(amounts['amount'], precision_rounding=self.currency_id.rounding):
                combine_cash_statement_line_vals.append(
                    self._get_combine_statement_line_vals(
                        payment_method.journal_id.id,
                        amounts['amount'] if (payment_method.currency_id == self.company_id.currency_id or not payment_method.currency_id) else amounts['amount'] * self.config_id.show_currency_rate,
                        payment_method
                    )
                )
                combine_cash_receivable_vals.append(
                    self._get_combine_receivable_vals(
                        payment_method,
                        amounts['amount'] if (payment_method.currency_id == self.company_id.currency_id or not payment_method.currency_id) else amounts['amount'] * self.config_id.show_currency_rate,
                        amounts['amount_converted']
                    )
                )

        # create the statement lines and account move lines
        BankStatementLine = self.env['account.bank.statement.line']
        split_cash_statement_lines = {}
        combine_cash_statement_lines = {}
        split_cash_receivable_lines = {}
        combine_cash_receivable_lines = {}
        split_cash_statement_lines = BankStatementLine.create(split_cash_statement_line_vals).mapped(
            'move_id.line_ids').filtered(lambda line: line.account_id.account_type == 'asset_receivable')

        combine_cash_statement_lines = BankStatementLine.create(combine_cash_statement_line_vals).mapped(
            'move_id.line_ids').filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        split_cash_receivable_lines = MoveLine.create(split_cash_receivable_vals)
        combine_cash_receivable_lines = MoveLine.create(combine_cash_receivable_vals)

        data.update(
            {'split_cash_statement_lines': split_cash_statement_lines,
             'combine_cash_statement_lines': combine_cash_statement_lines,
             'split_cash_receivable_lines': split_cash_receivable_lines,
             'combine_cash_receivable_lines': combine_cash_receivable_lines
             })
        return data


    def _create_bank_payment_moves(self, data):
        combine_receivables_bank = data.get('combine_receivables_bank')
        split_receivables_bank = data.get('split_receivables_bank')
        bank_payment_method_diffs = data.get('bank_payment_method_diffs')
        MoveLine = data.get('MoveLine')
        payment_method_to_receivable_lines = {}
        payment_to_receivable_lines = {}
        for payment_method, amounts in combine_receivables_bank.items():

            combine_receivable_line = MoveLine.create(self._get_combine_receivable_vals(payment_method, amounts['amount'], amounts['amount_converted']))
            amount = amounts['amount'] if (
                        payment_method.currency_id == self.company_id.currency_id or not payment_method.currency_id) else \
            amounts['amount'] * self.config_id.show_currency_rate
            amount_converted = amounts['amount_converted'] if (
                        payment_method.currency_id == self.company_id.currency_id or not payment_method.currency_id) else \
            amounts['amount_converted'] * self.config_id.show_currency_rate
            amounts['amount'] = amount
            amounts['amount_converted'] = amount_converted
            payment_receivable_line = self._create_combine_account_payment(payment_method, amounts, diff_amount=bank_payment_method_diffs.get(payment_method.id) or 0)
            payment_method_to_receivable_lines[payment_method] = combine_receivable_line | payment_receivable_line

        for payment, amounts in split_receivables_bank.items():

            split_receivable_line = MoveLine.create(self._get_split_receivable_vals(payment, amounts['amount'], amounts['amount_converted']))
            amount = amounts['amount'] if (
                    payment.currency_id == self.company_id.currency_id or not payment.currency_id) else \
                amounts['amount'] * self.config_id.show_currency_rate
            amount_converted = amounts['amount_converted'] if (
                    payment.currency_id == self.company_id.currency_id or not payment.currency_id) else \
                amounts['amount_converted'] * self.config_id.show_currency_rate
            amounts['amount'] = amount
            amounts['amount_converted'] = amount_converted
            payment_receivable_line = self._create_split_account_payment(payment, amounts)
            payment_to_receivable_lines[payment] = split_receivable_line | payment_receivable_line

        for bank_payment_method in self.payment_method_ids.filtered(lambda pm: pm.type == 'bank' and pm.split_transactions):
            self._create_diff_account_move_for_split_payment_method(bank_payment_method, bank_payment_method_diffs.get(bank_payment_method.id) or 0)

        data['payment_method_to_receivable_lines'] = payment_method_to_receivable_lines
        data['payment_to_receivable_lines'] = payment_to_receivable_lines
        print('data para linea en banco', data)
        return data

