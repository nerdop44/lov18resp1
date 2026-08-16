
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    # Campo de compatibilidad (Alias para evitar errores de validación de vista)
    foreign_rate = fields.Float(related='tax_today', readonly=False, string="Tasa (Alias)")



    def _valid_field_parameter(self, field_name, parameter):
        return super()._valid_field_parameter(field_name, parameter)


    amount = fields.Monetary(currency_field='currency_id', store=True, readonly=False)
    tax_today = fields.Float(string="Tasa Actual")
    tax_invoice = fields.Float(string="Tasa Factura")
    usar_tasa_factura = fields.Boolean(string="Usar Tasa Factura", default=True)

    @api.onchange('usar_tasa_factura')
    def _onchange_usar_tasa_factura(self):
        pass # No modificar tax_today para que conserve siempre la tasa del dia
    currency_id_dif = fields.Many2one("res.currency",string="Divisa de Referencia")
    currency_id_name = fields.Char(string="Nombre de Divisa", related="currency_id.name")
    amount_residual_usd = fields.Monetary(currency_field='currency_id_dif',string='Adeudado Divisa Ref.', readonly=True)
    payment_difference_bs = fields.Monetary(string="Diferencia Bs", currency_field='company_currency_id')
    payment_difference_usd = fields.Monetary(string="Diferencia $", currency_field='currency_id_dif')
    journal_id_dif = fields.Many2one('account.journal', 'Diario de diferencia', store=True,
                                 domain="[('company_id', '=', company_id)]")
    amount_usd = fields.Monetary(currency_field='currency_id_dif',string='Importe $', readonly=True)

    journal_igtf_id = fields.Many2one('account.journal', string='Diario IGTF', check_company=True)
    aplicar_igtf_divisa = fields.Boolean(string="Aplicar IGTF",
                                         default=lambda self: self._get_default_igtf())
    igtf_divisa_porcentage = fields.Float('% IGTF', related='company_id.igtf_divisa_porcentage')

    mount_igtf = fields.Monetary(currency_field='currency_id', string='Importe IGTF', readonly=True)

    amount_total_pagar = fields.Monetary(currency_field='currency_id', string="Total Pagar(Importe + IGTF):",
                                         readonly=True)

    # company_currency_id = fields.Many2one('res.currency', string='Company Currency')


    @api.depends('currency_id')
    def _get_default_igtf(self):
        if self.currency_id == self.company_id.currency_id:
            return False
        else:
            return self.company_id.aplicar_igtf_divisa
    @api.onchange('aplicar_igtf_divisa')
    def _mount_igtf(self):
        for wizard in self:
            if wizard.aplicar_igtf_divisa:
                if wizard.currency_id.name == 'USD':
                    wizard.mount_igtf = wizard.amount * wizard.igtf_divisa_porcentage / 100
                    wizard.amount_total_pagar = wizard.mount_igtf + wizard.amount
                else:
                    wizard.mount_igtf = 0
                    wizard.amount_total_pagar = wizard.amount
            else:
                wizard.mount_igtf = 0
                wizard.amount_total_pagar = wizard.amount


    @api.onchange('tax_today', 'tax_invoice', 'usar_tasa_factura', 'source_amount', 'source_amount_currency', 'source_currency_id', 'company_id', 'currency_id',
                 'payment_date')
    def _compute_amount(self):
        for wizard in self:
            tasa_a_usar = wizard.tax_invoice if wizard.usar_tasa_factura else wizard.tax_today
            if not tasa_a_usar or tasa_a_usar <= 0:
                tasa_a_usar = 1.0

            if wizard.source_currency_id == wizard.currency_id:
                # Same currency.
                wizard.amount = wizard.source_amount
            elif wizard.currency_id == wizard.company_id.currency_id:
                # Payment expressed on company's currency (USD for Krill, VES for standard)
                # Since they are different, source_currency is the reference/foreign one (VES for Krill, USD for standard)
                # Converting from reference/foreign to base: divide by rate
                wizard.amount = wizard.source_amount / tasa_a_usar
            elif wizard.currency_id == wizard.company_id.currency_id_dif:
                # Payment expressed on reference currency (VES for Krill, USD for standard)
                # Since they are different, source_currency is the base one (USD for Krill, VES for standard)
                # Converting from base to reference/foreign: multiply by rate
                wizard.amount = wizard.source_amount * tasa_a_usar
            else:
                # Fallback
                wizard.amount = wizard.amount_residual_usd

            if wizard.aplicar_igtf_divisa:
                if wizard.currency_id.name == wizard.company_id.currency_id_dif.name:
                    wizard.mount_igtf = wizard.amount * wizard.igtf_divisa_porcentage / 100
                    wizard.amount_total_pagar = wizard.mount_igtf + wizard.amount
                else:
                    wizard.mount_igtf = 0
                    wizard.amount_total_pagar = wizard.amount
            else:
                wizard.mount_igtf = 0
                wizard.amount_total_pagar = wizard.amount

    @api.depends('amount', 'tax_today', 'tax_invoice', 'usar_tasa_factura')
    def _compute_payment_difference(self):
        for wizard in self:
            tasa_a_usar = wizard.tax_invoice if wizard.usar_tasa_factura else wizard.tax_today
            if not tasa_a_usar or tasa_a_usar <= 0:
                tasa_a_usar = 1.0

            wizard.amount_usd = wizard.amount / tasa_a_usar
            if wizard.source_currency_id == wizard.currency_id:
                # Same currency.
                wizard.payment_difference = wizard.source_amount_currency - wizard.amount
                wizard.payment_difference_usd = wizard.amount_residual_usd - (wizard.amount / tasa_a_usar)
                wizard.payment_difference_bs = 0
                if wizard.currency_id == wizard.company_id.currency_id_dif:
                    wizard.payment_difference_usd = wizard.amount_residual_usd - wizard.amount
                    wizard.payment_difference_bs = (wizard.amount_residual_usd / wizard.tax_invoice) - (wizard.amount / tasa_a_usar)
            elif wizard.currency_id == wizard.company_id.currency_id:
                # Payment expressed on the company's currency.
                if wizard.source_currency_id == wizard.company_id.currency_id:
                    wizard.payment_difference = wizard.source_amount - wizard.amount
                else:
                    wizard.payment_difference = (wizard.source_amount * wizard.tax_invoice) - wizard.amount
                    wizard.payment_difference_usd = wizard.amount_residual_usd - (wizard.amount / tasa_a_usar)
            else:
                # Foreign currency on payment different than the one set on the journal entries.
                wizard.payment_difference = wizard.amount_residual_usd - wizard.amount
                if tasa_a_usar == wizard.tax_invoice and wizard.amount_residual_usd == wizard.amount and wizard.currency_id == wizard.company_id.currency_id_dif:
                    wizard.payment_difference_bs = 0
                else:
                    wizard.payment_difference_bs = wizard.source_amount - (wizard.amount * tasa_a_usar)

            if wizard.aplicar_igtf_divisa:
                if wizard.currency_id.name == wizard.company_id.currency_id_dif.name:
                    wizard.mount_igtf = wizard.amount * wizard.igtf_divisa_porcentage / 100
                    wizard.amount_total_pagar = wizard.mount_igtf + wizard.amount
                else:
                    wizard.mount_igtf = 0
                    wizard.amount_total_pagar = wizard.amount
            else:
                wizard.mount_igtf = 0
                wizard.amount_total_pagar = wizard.amount

    @api.model
    def _get_wizard_values_from_batch(self, batch_result):
        ''' Extract values from the batch passed as parameter (see '_get_batches')
        to be mounted in the wizard view.
        :param batch_result:    A batch returned by '_get_batches'.
        :return:                A dictionary containing valid fields
        '''

        key_values = batch_result['payment_values']
        ###print('Values: %s' % batch_result)
        lines = batch_result['lines']
        company = lines[0].company_id
        tax_invoice = lines[0].tax_today
        if not self.tax_today:
            currency_dif = lines[0].company_id.currency_id_dif
            if lines[0].company_id.currency_id.name == 'USD':
                # Krill Energy: base USD, dual VES → tasa directa (Bs por 1 USD)
                tax_today = currency_dif.rate or 1.0
            else:
                # Estándar Venezuela: base VES, dual USD → tasa inversa
                tax_today = currency_dif.inverse_rate or 1.0
        else:
            tax_today = self.tax_today

        currency_id_dif = company.currency_id_dif or lines[0].currency_id_dif
        amount_residual_usd = lines[0].move_id.amount_residual_usd
        invoice_currency = lines[0].currency_id or company.currency_id
        source_amount = abs(sum(lines.mapped('amount_residual'))) if invoice_currency == company.currency_id else abs(sum(lines.mapped('amount_residual_currency')))
        if key_values['currency_id'] == company.currency_id.id:
            source_amount_currency = source_amount
        else:
            source_amount_currency = abs(sum(lines.mapped('amount_residual_currency')))
            if source_amount_currency == 0 and source_amount > 0:
                if company.currency_id.name == 'USD':
                    source_amount_currency = source_amount * tax_today
                else:
                    source_amount_currency = source_amount / tax_today

        # Restar retenciones pendientes (IVA, ISLR, Municipal) para evitar arrastrar saldos incorrectos
        move = lines[0].move_id
        if move:
            ret_lines = move.retention_iva_line_ids + move.retention_islr_line_ids + move.retention_municipal_line_ids
            total_ret_usd = sum(ret_lines.mapped('retention_amount'))
            total_ret_bs = sum(ret_lines.mapped('foreign_retention_amount'))

            reconciled_ret_usd = 0.0
            reconciled_ret_bs = 0.0
            ret_payments = ret_lines.mapped('retention_id.payment_ids')
            ret_payment_moves = ret_payments.mapped('move_id')

            if company.currency_id.name == 'USD':
                # Compania base USD, referencia VES/Bs
                for line in move.line_ids.filtered(lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')):
                    partials = line.matched_debit_ids + line.matched_credit_ids
                    for partial in partials:
                        counterpart_line = partial.debit_move_id if partial.credit_move_id == line else partial.credit_move_id
                        if counterpart_line.payment_id in ret_payments or counterpart_line.move_id in ret_payment_moves or counterpart_line.payment_id.is_retention:
                            reconciled_ret_usd += partial.amount      # USD
                            reconciled_ret_bs += partial.amount_usd   # VES
            else:
                # Compania base VES/Bs, referencia USD
                for line in move.line_ids.filtered(lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')):
                    partials = line.matched_debit_ids + line.matched_credit_ids
                    for partial in partials:
                        counterpart_line = partial.debit_move_id if partial.credit_move_id == line else partial.credit_move_id
                        if counterpart_line.payment_id in ret_payments or counterpart_line.move_id in ret_payment_moves or counterpart_line.payment_id.is_retention:
                            reconciled_ret_bs += partial.amount      # VES
                            reconciled_ret_usd += partial.amount_usd   # USD

            pending_ret_usd = max(0.0, total_ret_usd - reconciled_ret_usd)
            pending_ret_bs = max(0.0, total_ret_bs - reconciled_ret_bs)

            if company.currency_id.name == 'USD':
                # Base USD, referencia VES
                amount_residual_usd = max(0.0, amount_residual_usd - pending_ret_bs)
                if key_values['currency_id'] == company.currency_id.id:
                    source_amount = max(0.0, source_amount - pending_ret_usd)
                    source_amount_currency = source_amount
                else:
                    source_amount = max(0.0, source_amount - pending_ret_bs)
                    source_amount_currency = max(0.0, source_amount_currency - pending_ret_bs)
            else:
                # Base VES, referencia USD
                amount_residual_usd = max(0.0, amount_residual_usd - pending_ret_usd)
                if key_values['currency_id'] == company.currency_id.id:
                    source_amount = max(0.0, source_amount - pending_ret_bs)
                    source_amount_currency = source_amount
                else:
                    source_amount = max(0.0, source_amount - pending_ret_usd)
                    source_amount_currency = max(0.0, source_amount_currency - pending_ret_usd)

        # Si la factura ya está totalmente pagada en su moneda nativa, forzamos montos a 0.0
        if move and (move.currency_id.is_zero(move.amount_residual) or move.amount_residual <= 0.001):
            amount_residual_usd = 0.0
            source_amount = 0.0
            source_amount_currency = 0.0

        # En la inicializacion, tax_today debe ser la tasa del dia de hoy, no la de la factura
        # Para que el selector de usar tasa factura empiece en True pero use la del dia si se desmarca
        currency_dif = company.currency_id_dif
        if company.currency_id.name == 'USD':
            tax_today = currency_dif.rate or 1.0
        else:
            tax_today = currency_dif.inverse_rate or 1.0

        return {
            'company_id': company.id,
            'partner_id': key_values['partner_id'],
            'partner_type': key_values['partner_type'],
            'payment_type': key_values['payment_type'],
            'source_currency_id': key_values['currency_id'],
            'source_amount': source_amount,
            'source_amount_currency': source_amount_currency,
            'tax_today': tax_today,
            'tax_invoice': tax_invoice,
            'usar_tasa_factura': True,
            'currency_id_dif': currency_id_dif.id,
            'amount_residual_usd': amount_residual_usd,
            'aplicar_igtf_divisa': self.aplicar_igtf_divisa,
        }

    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        tasa_a_usar = self.tax_invoice if self.usar_tasa_factura else self.tax_today
        payment_vals.update({
            'tax_today': tasa_a_usar,
            'currency_id_dif': self.currency_id_dif.id,
            'aplicar_igtf_divisa': self.aplicar_igtf_divisa,
            'journal_igtf_id': self.journal_igtf_id.id,
            'mount_igtf': self.mount_igtf,
            'amount_total_pagar': self.amount_total_pagar,
        })
        return payment_vals

    def _create_payment_vals_from_batch(self, batch_result):
        payment_vals = super()._create_payment_vals_from_batch(batch_result)
        tasa_a_usar = self.tax_invoice if self.usar_tasa_factura else self.tax_today
        payment_vals.update({
            'tax_today': tasa_a_usar,
            'currency_id_dif': self.currency_id_dif.id,
            'aplicar_igtf_divisa': self.aplicar_igtf_divisa,
            'journal_igtf_id': self.journal_igtf_id.id,
            'mount_igtf': self.mount_igtf,
            'amount_total_pagar': self.amount_total_pagar,
        })
        return payment_vals


    def _create_payments(self):
        tasa_a_usar = self.tax_invoice if self.usar_tasa_factura else self.tax_today
        self.env.context = dict(self.env.context, tasa_factura=tasa_a_usar, calcular_dual_currency=True)

        prev_reconciled_lines = self.env['account.move.line']
        if self.line_ids:
            invoice_line = self.line_ids[0]
            for partial in (invoice_line.matched_debit_ids + invoice_line.matched_credit_ids):
                prev_reconciled_lines |= partial.debit_move_id
                prev_reconciled_lines |= partial.credit_move_id
            prev_reconciled_lines = prev_reconciled_lines - invoice_line

        payments = super()._create_payments()
        payments.move_id._verificar_pagos()
        if payments.move_id_dif:
            payments.move_id_dif._verificar_pagos()
        self.env.context = dict(self.env.context, tasa_factura=None, calcular_dual_currency=False)
        pay_term_line_ids = payments.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        partials = pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped(
            'matched_credit_ids')
        #print('partials: %s' % partials)
        for partial in partials:
            if partial.amount_usd == 0:
                monto_usd = 0
                to_reconcile = payments.move_id.line_ids.filtered_domain([('account_id', '=', self.line_ids[0].account_id.id)])

                if abs(self.line_ids[0].amount_residual_usd) > 0:
                    #print("1")
                    if abs(self.line_ids[0].amount_residual_usd) > abs(to_reconcile.amount_residual_usd):
                        #print("2", abs(self.line_ids[0].amount_residual_usd), to_reconcile.amount_residual_usd)
                        monto_usd = abs(to_reconcile.amount_residual_usd)
                    else:
                        #print("3")
                        monto_usd = abs(self.line_ids[0].amount_residual_usd)
                partial.write({'amount_usd': monto_usd})

                to_reconcile._compute_amount_residual_usd()
                #print('escribe el parcial: %s' % monto_usd)

        if self.source_amount == 0:
            payments.action_draft()
            move = payments.move_id
            l_cliente = move.with_context(check_move_validity=False).line_ids.filtered_domain([('account_id', '=', self.line_ids[0].account_id.id)])
            monto_diferencia = l_cliente.debit if l_cliente.debit > 0 else l_cliente.credit
            direccion = 'd' if l_cliente.debit > 0 else 'c'
            tmp_d = l_cliente.debit_usd
            tmp_c = l_cliente.credit_usd
            l_cliente.with_context(check_move_validity=False).debit = 0
            l_cliente.with_context(check_move_validity=False).credit = 0
            l_cliente.with_context(check_move_validity=False).debit_usd = tmp_d
            l_cliente.with_context(check_move_validity=False).credit_usd = tmp_c
            self.line_ids[0].with_context(check_move_validity=False).reconciled = False
            l_cliente.with_context(check_move_validity=False).reconciled = False
            move.line_ids = [(0, 0, {
                                    'debit': monto_diferencia if direccion == 'd' else 0,
                                    'credit': monto_diferencia if direccion == 'c' else 0,
                                    'debit_usd': 0,
                                    'credit_usd': 0,
                                    'account_id': self.writeoff_account_id.id,
                                    'partner_id': self.partner_id.id,
                                    'date': self.payment_date,
                                    'currency_id': self.currency_id.id,
                                    'name': self.writeoff_label + ' de ' + self.communication,
                                })]
            payments.action_post()
            if self.line_ids[0].full_reconcile_id:
                self.line_ids[0].full_reconcile_id.unlink()
            ###print(self.line_ids[0])
            # query = """
            #     INSERT INTO account_partial_reconcile(debit_move_id,credit_move_id,
            #          debit_currency_id,credit_currency_id,amount,
            #          debit_amount_currency,credit_amount_currency,company_id,max_date,
            #          create_uid,create_date,write_uid,write_date)
            #     VALUES(%s,%s,%s,%s)
            #     SELECT
            #         debit_currency_id,
            #         credit_currency_id,
            #         0 as amount,
            #         0 as debit_amount_currency,
            #         0 as credit_amount_currency,
            #         company_id,
            #         max_date,
            #         create_uid,
            #         create_date,
            #         write_uid,
            #         write_date
            #     FROM account_partial_reconcile
            #     WHERE debit_move_id = %s LIMIT 1
            #     """ % (self.line_ids[0].id, l_cliente.id, self.line_ids[0].move_id.currency_id.id, self.line_ids[0].move_id.currency_id.id)
            # ###print(query)
            # self.env.cr.execute(query)

            # Odoo 18: _compute_max_date hace max(debit_move.date, credit_move.date).
            # account.move.line.date es readonly/computed desde move_id.date y no puede
            # asignarse directamente. La solución es proveer max_date explícitamente en
            # el create() para que Odoo no intente computarlo con fechas potencialmente False.
            max_date = (
                self.line_ids[0].move_id.date
                or l_cliente.move_id.date
                or self.payment_date
            )

            self.env['account.partial.reconcile'].create([{
                'amount': 0,
                'amount_usd': self.amount_residual_usd if (tmp_d > self.amount_residual_usd or tmp_c > self.amount_residual_usd) else (tmp_d if tmp_d > 0 else tmp_c),
                'debit_amount_currency': 0,
                'credit_amount_currency': 0,
                'debit_move_id': self.line_ids[0].id,
                'credit_move_id': l_cliente.id,
                'max_date': max_date,
            }])


            self.env.context = dict(self.env.context, tasa_factura=None)
            lines_to_reconcile = (self.line_ids[0] + l_cliente)
            lines_to_reconcile.flush_recordset()
            lines_to_reconcile.invalidate_recordset(fnames=['reconciled'])
            lines_to_reconcile = lines_to_reconcile.filtered(lambda l: not l.reconciled)
            if len(lines_to_reconcile) > 1:
                lines_to_reconcile.reconcile()

        else:
            #self.payment_difference > 0 and self.payment_difference_bs > 0 and self.payment_difference_handling == 'reconcile' and self.currency_id != self.company_id.currency_id
            ##print("self.payment_difference", self.payment_difference)
            ##print("self.payment_difference_bs", self.payment_difference_bs)
            ##print("self.payment_difference_usd", self.payment_difference_usd)
            ##print("self.payment_difference_handling", self.payment_difference_handling)
            ##print("self.currency_id", self.currency_id)
            ##print("self.company_id.currency_id", self.company_id.currency_id)
            if not self.currency_id.is_zero(self.payment_difference) and self.payment_difference_bs < 0 and self.payment_difference_handling == 'reconcile':
                move = {'ref': self.writeoff_label + ' de ' + self.communication,
                        'line_ids': [(0, 0, {
                                        'debit': -self.payment_difference_bs if self.payment_difference_bs < 0.0 else self.payment_difference_bs,
                                        'credit': 0,
                                        'debit_usd': 0,
                                        'credit_usd': 0,
                                        'account_id': self.line_ids[0].account_id.id if payments.payment_type == 'inbound' else self.writeoff_account_id.id,
                                        'partner_id': self.partner_id.id if payments.payment_type == 'inbound' else False,
                                        'date': self.payment_date,
                                        'currency_id': self.currency_id.id,
                                        'name': self.writeoff_label + ' de ' + self.communication,
                                    }),(0, 0, {
                                        'debit': 0,
                                        'debit_usd': 0,
                                        'credit_usd': 0,
                                        'credit': -self.payment_difference_bs if self.payment_difference_bs < 0.0 else self.payment_difference_bs,
                                        'account_id': self.writeoff_account_id.id if payments.payment_type == 'inbound' else self.line_ids[0].account_id.id,
                                        'partner_id': False if payments.payment_type == 'inbound' else self.partner_id.id,
                                        'date': self.payment_date,
                                        'currency_id': self.currency_id.id,
                                        'name': self.writeoff_label + ' de ' + self.communication,
                                    })],
                        'journal_id': self.journal_id_dif.id if self.journal_id_dif else self.journal_id.id,
                        'date': self.payment_date,
                        'state': 'draft',
                        'type_name': 'entry',
                        'tax_today': 0,
                        'currency_id_dif': self.currency_id_dif.id,
                        }
                ###print(move)
                move_new = self.env['account.move'].create(move)
                payments.move_id_dif = move_new
                payments.move_id_dif._post(soft=False)
                #print('entra por diferencia 1')
                self.env.context = dict(self.env.context, tasa_factura=None)
                to_reconcile = payments.move_id.line_ids.filtered_domain(
                    [('account_id', '=', self.line_ids[0].account_id.id)])
                payment_lines = move_new.line_ids.filtered_domain(
                    [('account_id', '=', self.line_ids[0].account_id.id)])

                invoice_line = self.line_ids[0]
                if invoice_line.reconciled or to_reconcile.reconciled:
                    invoice_line.remove_move_reconcile()
                lines_to_rec = (payment_lines + to_reconcile + invoice_line + prev_reconciled_lines)
                lines_to_rec.flush_recordset()
                lines_to_rec.invalidate_recordset(fnames=['reconciled'])
                lines_to_rec = lines_to_rec.filtered(lambda l: not l.reconciled)
                if len(lines_to_rec) > 1:
                    lines_to_rec.reconcile()

            elif self.currency_id.is_zero(self.payment_difference) and not self.payment_difference_bs == 0 and self.payment_difference_handling == 'reconcile':
                move = {'ref': self.writeoff_label + ' de ' + self.communication,
                        'line_ids': [(0, 0, {
                                        'debit': -self.payment_difference_bs if self.payment_difference_bs < 0.0 else self.payment_difference_bs,
                                        'credit': 0,
                                        'debit_usd': 0,
                                        'credit_usd': 0,
                                        'account_id': self.line_ids[0].account_id.id if payments.payment_type == 'inbound' else self.writeoff_account_id.id,
                                        'partner_id': self.partner_id.id if payments.payment_type == 'inbound' else False,
                                        'date': self.payment_date,
                                        'currency_id': self.company_currency_id.id,
                                        'name': self.writeoff_label + ' de ' + self.communication,
                                    }),(0, 0, {
                                        'debit': 0,
                                        'debit_usd': 0,
                                        'credit_usd': 0,
                                        'credit': -self.payment_difference_bs if self.payment_difference_bs < 0.0 else self.payment_difference_bs,
                                        'account_id': self.writeoff_account_id.id if payments.payment_type == 'inbound' else self.line_ids[0].account_id.id,
                                        'partner_id': False if payments.payment_type == 'inbound' else self.partner_id.id,
                                        'date': self.payment_date,
                                        'currency_id': self.company_currency_id.id,
                                        'name': self.writeoff_label + ' de ' + self.communication,
                                    })],
                        'journal_id': self.journal_id_dif.id if self.journal_id_dif else self.journal_id.id,
                        'date': self.payment_date,
                        'state': 'draft',
                        'type_name': 'entry',
                        'tax_today': 0,
                        'currency_id_dif': self.currency_id.id,
                        }
                if self.payment_difference_bs > 0:
                    move['line_ids'][0][2]['account_id'] = self.writeoff_account_id.id if payments.payment_type == 'inbound' else self.line_ids[0].account_id.id
                    move['line_ids'][1][2]['account_id'] = self.line_ids[0].account_id.id if payments.payment_type == 'inbound' else self.writeoff_account_id.id
                    move['line_ids'][0][2]['partner_id'] = False if payments.payment_type == 'inbound' else self.partner_id.id
                    move['line_ids'][1][2]['partner_id'] = self.partner_id.id if payments.payment_type == 'inbound' else False

                move_new = self.env['account.move'].create(move)
                payments.move_id_dif = move_new
                payments.move_id_dif._post(soft=False)

                #print('entra por diferencia 2')
                ##print('estatus del asiento del pago ', payments.move_id.state)
                ##print('estatus del asiento de la diferencia ', payments.move_id_dif.state)
                self.env.context = dict(self.env.context, tasa_factura=None)
                invoice_line = self.line_ids[0]
                if self.payment_difference_bs < 0:
                    to_reconcile = payments.move_id.line_ids.filtered_domain(
                        [('account_id', '=', invoice_line.account_id.id)])
                    payment_lines = move_new.line_ids.filtered_domain(
                        [('account_id', '=', invoice_line.account_id.id)])
                    if invoice_line.reconciled or to_reconcile.reconciled:
                        invoice_line.remove_move_reconcile()
                    lines_to_rec = (payment_lines + to_reconcile + invoice_line + prev_reconciled_lines)
                    lines_to_rec.flush_recordset()
                    lines_to_rec.invalidate_recordset(fnames=['reconciled'])
                    lines_to_rec = lines_to_rec.filtered(lambda l: not l.reconciled)
                    if len(lines_to_rec) > 1:
                        lines_to_rec.reconcile()
                else:
                    payment_lines = move_new.line_ids.filtered_domain(
                        [('account_id', '=', invoice_line.account_id.id)])
                    to_reconcile = invoice_line
                    payment_main_line = payments.move_id.line_ids.filtered_domain(
                        [('account_id', '=', invoice_line.account_id.id)])
                    if invoice_line.reconciled or payment_main_line.reconciled:
                        invoice_line.remove_move_reconcile()
                    lines_to_rec = (payment_lines + to_reconcile + payment_main_line + prev_reconciled_lines)
                    lines_to_rec.flush_recordset()
                    lines_to_rec.invalidate_recordset(fnames=['reconciled'])
                    lines_to_rec = lines_to_rec.filtered(lambda l: not l.reconciled)
                    if len(lines_to_rec) > 1:
                        lines_to_rec.reconcile()
            elif not self.currency_id.is_zero(self.payment_difference) and self.payment_difference_bs == 0 and self.payment_difference_usd == 0\
                    and self.payment_difference_handling == 'reconcile' and self.currency_id == self.company_id.currency_id:
                move = {'ref': self.writeoff_label + ' de ' + self.communication,
                        'line_ids': [(0, 0, {
                            'debit': -self.payment_difference if self.payment_difference < 0.0 else self.payment_difference,
                            'credit': 0,
                            'debit_usd': 0,
                            'credit_usd': 0,
                            'account_id': self.line_ids[
                                0].account_id.id if payments.payment_type == 'inbound' else self.writeoff_account_id.id,
                            'partner_id': self.partner_id.id if payments.payment_type == 'inbound' else False,
                            'date': self.payment_date,
                            'currency_id': self.currency_id.id,
                            'name': self.writeoff_label + ' de ' + self.communication,
                        }), (0, 0, {
                            'debit': 0,
                            'debit_usd': 0,
                            'credit_usd': 0,
                            'credit': -self.payment_difference if self.payment_difference < 0.0 else self.payment_difference,
                            'account_id': self.writeoff_account_id.id if payments.payment_type == 'inbound' else
                            self.line_ids[0].account_id.id,
                            'partner_id': False if payments.payment_type == 'inbound' else self.partner_id.id,
                            'date': self.payment_date,
                            'currency_id': self.currency_id.id,
                            'name': self.writeoff_label + ' de ' + self.communication,
                        })],
                        'journal_id': self.journal_id_dif.id if self.journal_id_dif else self.journal_id.id,
                        'date': self.payment_date,
                        'state': 'draft',
                        'type_name': 'entry',
                        'tax_today': 0,
                        'currency_id_dif': self.currency_id.id,
                        }
                if self.payment_difference > 0:
                    move['line_ids'][0][2]['account_id'] = self.writeoff_account_id.id if payments.payment_type == 'inbound' else self.line_ids[0].account_id.id
                    move['line_ids'][1][2]['account_id'] = self.line_ids[0].account_id.id if payments.payment_type == 'inbound' else self.writeoff_account_id.id
                    move['line_ids'][0][2]['partner_id'] = False if payments.payment_type == 'inbound' else self.partner_id.id
                    move['line_ids'][1][2]['partner_id'] = self.partner_id.id if payments.payment_type == 'inbound' else False
                ##print(move)
                move_new = self.env['account.move'].create(move)
                payments.move_id_dif = move_new
                payments.move_id_dif._post(soft=False)

                #print('entra por diferencia 3')
                ##print('aqui llega y crea el asiento de diferencia', payments.move_id_dif)
                self.env.context = dict(self.env.context, tasa_factura=None)
                to_reconcile = payments.move_id.line_ids.filtered_domain(
                    [('account_id', '=', self.line_ids[0].account_id.id)])
                payment_lines = move_new.line_ids.filtered_domain(
                    [('account_id', '=', self.line_ids[0].account_id.id)])
                if self.payment_difference > 0:
                    invoice_line = self.line_ids[0]
                    payment_main_line = payments.move_id.line_ids.filtered_domain(
                        [('account_id', '=', invoice_line.account_id.id)])
                    if invoice_line.reconciled or payment_main_line.reconciled:
                        invoice_line.remove_move_reconcile()
                    lines_to_rec = (payment_lines + invoice_line + payment_main_line + prev_reconciled_lines)
                    lines_to_rec.flush_recordset()
                    lines_to_rec.invalidate_recordset(fnames=['reconciled'])
                    lines_to_rec = lines_to_rec.filtered(lambda l: not l.reconciled)
                    if len(lines_to_rec) > 1:
                        lines_to_rec.reconcile()

            elif self.payment_difference > 0 and self.payment_difference_bs > 0 and self.payment_difference_usd == 0 and self.payment_difference_handling == 'reconcile' and self.currency_id == self.company_id.currency_id:
                move = {'ref': self.writeoff_label + ' de ' + self.communication,
                        'line_ids': [(0, 0, {
                            'amount_currency': self.payment_difference,
                            'debit': self.payment_difference_bs,
                            'credit': 0,
                            'debit_usd': self.payment_difference,
                            'credit_usd': 0,
                            'account_id': self.writeoff_account_id.id if payments.payment_type == 'inbound' else
                            self.line_ids[0].account_id.id,
                            'partner_id': False if payments.payment_type == 'inbound' else self.partner_id.id,

                            'date': self.payment_date,
                            'currency_id': self.currency_id.id,
                            'name': self.writeoff_label + ' de ' + self.communication,
                        }), (0, 0, {
                            'amount_currency': -self.payment_difference,
                            'debit': 0,
                            'debit_usd': 0,
                            'credit_usd': self.payment_difference,
                            'credit': self.payment_difference_bs,
                            'account_id': self.line_ids[
                                0].account_id.id if payments.payment_type == 'inbound' else self.writeoff_account_id.id,
                            'partner_id': self.partner_id.id if payments.payment_type == 'inbound' else False,
                            'date': self.payment_date,
                            'currency_id': self.currency_id.id,
                            'name': self.writeoff_label + ' de ' + self.communication,
                        })],
                        'journal_id': self.journal_id_dif.id if self.journal_id_dif else self.journal_id.id,
                        'date': self.payment_date,
                        'state': 'draft',
                        'type_name': 'entry',
                        'tax_today': self.tax_today,
                        'currency_id_dif': self.currency_id.id,
                        }
                # ##print(move)
                move_new = self.env['account.move'].create(move)
                payments.move_id_dif = move_new
                payments.move_id_dif._post(soft=False)

                #print('entra por diferencia 4')
                self.env.context = dict(self.env.context, tasa_factura=None)
                to_reconcile = self.line_ids[0]
                payment_lines = move_new.line_ids.filtered_domain(
                    [('account_id', '=', self.line_ids[0].account_id.id)])
                invoice_line = self.line_ids[0]
                payment_main_line = payments.move_id.line_ids.filtered_domain(
                    [('account_id', '=', invoice_line.account_id.id)])
                if invoice_line.reconciled or payment_main_line.reconciled:
                    invoice_line.remove_move_reconcile()
                lines_to_rec = (payment_lines + invoice_line + payment_main_line + prev_reconciled_lines)
                lines_to_rec.flush_recordset()
                lines_to_rec.invalidate_recordset(fnames=['reconciled'])
                lines_to_rec = lines_to_rec.filtered(lambda l: not l.reconciled)
                if len(lines_to_rec) > 1:
                    lines_to_rec.reconcile()
            elif self.payment_difference > 0 and self.payment_difference_bs > 0 and self.payment_difference_handling == 'reconcile' and self.currency_id != self.company_id.currency_id:
                move = {'ref': self.writeoff_label + ' de ' + self.communication,
                        'line_ids': [(0, 0, {
                            'amount_currency': self.payment_difference,
                            'debit': self.payment_difference_bs,
                            'credit': 0,
                            'debit_usd': self.payment_difference,
                            'credit_usd': 0,
                            'account_id': self.line_ids[
                                0].account_id.id if payments.payment_type == 'inbound' else self.writeoff_account_id.id,
                            'partner_id': self.partner_id.id if payments.payment_type == 'inbound' else False,
                            'date': self.payment_date,
                            'currency_id': self.currency_id.id,
                            'name': self.writeoff_label + ' de ' + self.communication,
                        }), (0, 0, {
                            'amount_currency': -self.payment_difference,
                            'debit': 0,
                            'debit_usd': 0,
                            'credit_usd': self.payment_difference,
                            'credit': self.payment_difference_bs,
                            'account_id': self.writeoff_account_id.id if payments.payment_type == 'inbound' else
                            self.line_ids[0].account_id.id,
                            'partner_id': False if payments.payment_type == 'inbound' else self.partner_id.id,
                            'date': self.payment_date,
                            'currency_id': self.currency_id.id,
                            'name': self.writeoff_label + ' de ' + self.communication,
                        })],
                        'journal_id': self.journal_id_dif.id if self.journal_id_dif else self.journal_id.id,
                        'date': self.payment_date,
                        'state': 'draft',
                        'type_name': 'entry',
                        'tax_today': self.tax_today,
                        'currency_id_dif': self.currency_id.id,
                        }
                ###print(move)
                move_new = self.env['account.move'].create(move)
                payments.move_id_dif = move_new
                payments.move_id_dif._post(soft=False)

                #print('entra por diferencia 5')
                self.env.context = dict(self.env.context, tasa_factura=None)
                to_reconcile = payments.move_id.line_ids.filtered_domain(
                    [('account_id', '=', self.line_ids[0].account_id.id)])
                payment_lines = move_new.line_ids.filtered_domain(
                    [('account_id', '=', self.line_ids[0].account_id.id)])

                invoice_line = self.line_ids[0]
                if invoice_line.reconciled or to_reconcile.reconciled:
                    invoice_line.remove_move_reconcile()
                lines_to_rec = (payment_lines + to_reconcile + invoice_line + prev_reconciled_lines)
                lines_to_rec.flush_recordset()
                lines_to_rec.invalidate_recordset(fnames=['reconciled'])
                lines_to_rec = lines_to_rec.filtered(lambda l: not l.reconciled)
                if len(lines_to_rec) > 1:
                    lines_to_rec.reconcile()


            elif self.payment_difference > 0 and self.payment_difference_usd > 0 and self.payment_difference_handling == 'reconcile' and self.currency_id == self.source_currency_id:
                move = {'ref': self.writeoff_label + ' de ' + self.communication,
                        'line_ids': [(0, 0, {
                            'debit': self.payment_difference,
                            'credit': 0,
                            'debit_usd': self.payment_difference_usd,
                            'credit_usd': 0,
                            'account_id': self.writeoff_account_id.id if payments.payment_type == 'inbound' else
                            self.line_ids[0].account_id.id,
                            'partner_id': False if payments.payment_type == 'inbound' else self.partner_id.id,
                            'date': self.payment_date,
                            'currency_id': self.currency_id.id,
                            'name': self.writeoff_label + ' de ' + self.communication,
                        }), (0, 0, {
                            'debit': 0,
                            'debit_usd': 0,
                            'credit_usd': self.payment_difference_usd,
                            'credit': self.payment_difference,
                            'account_id': self.line_ids[
                                0].account_id.id if payments.payment_type == 'inbound' else self.writeoff_account_id.id,
                            'date': self.payment_date,
                            'partner_id': self.partner_id.id if payments.payment_type == 'inbound' else False,
                            'currency_id': self.currency_id.id,
                            'name': self.writeoff_label + ' de ' + self.communication,
                        })],
                        'journal_id': self.journal_id_dif.id if self.journal_id_dif else self.journal_id.id,
                        'date': self.payment_date,
                        'state': 'draft',
                        'type_name': 'entry',
                        'tax_today': self.tax_today,
                        'currency_id_dif': self.currency_id.id,
                        }
                move_new = self.env['account.move'].create(move)
                payments.move_id_dif = move_new
                payments.move_id_dif._post(soft=False)
                self.env.context = dict(self.env.context, tasa_factura=None)
                to_reconcile = payments.move_id.line_ids.filtered_domain(
                    [('account_id', '=', self.line_ids[0].account_id.id)])
                payment_lines = move_new.line_ids.filtered_domain(
                    [('account_id', '=', self.line_ids[0].account_id.id)])

                invoice_line = self.line_ids[0]
                if invoice_line.reconciled or to_reconcile.reconciled:
                    invoice_line.remove_move_reconcile()
                lines_to_rec = (payment_lines + to_reconcile + invoice_line + prev_reconciled_lines)
                lines_to_rec.flush_recordset()
                lines_to_rec.invalidate_recordset(fnames=['reconciled'])
                lines_to_rec = lines_to_rec.filtered(lambda l: not l.reconciled)
                if len(lines_to_rec) > 1:
                    lines_to_rec.reconcile()

        return payments

    @api.model
    def default_get(self, fields_list):
        # OVERRIDE
        ###print(fields_list)
        #if 'line_ids' in fields_list:
        #    fields_list.remove("line_ids")
        if 'line_ids' in fields_list:
            fields_list.remove("line_ids")
        res = super().default_get(fields_list)
        fields_list.append("line_ids")
        if 'line_ids' in fields_list and 'line_ids' not in res:

            # Retrieve moves to pay from the context.

            if self._context.get('active_model') == 'account.move':
                lines = self.env['account.move'].browse(self._context.get('active_ids', [])).line_ids
            elif self._context.get('active_model') == 'account.move.line':
                lines = self.env['account.move.line'].browse(self._context.get('active_ids', []))
            else:
                raise UserError(_(
                    "The register payment wizard should only be called on account.move or account.move.line records."
                ))

            # Keep lines having a residual amount to pay.
            available_lines = self.env['account.move.line']
            for line in lines:
                if line.move_id.state != 'posted':
                    raise UserError(_("You can only register payment for posted journal entries."))

                if line.account_type not in ('asset_receivable', 'liability_payable'):
                    continue
                if line.currency_id:
                    if line.move_id.amount_residual_usd == 0.0:
                        continue
                else:
                    if line.company_currency_id.is_zero(line.amount_residual) and line.move_id.amount_residual_usd == 0.0:
                        continue
                available_lines |= line

            # Check.
            if len(lines.company_id) > 1:
                raise UserError(_("You can't create payments for entries belonging to different companies."))
            if len(set(available_lines.mapped('account_type'))) > 1:
                raise UserError(
                    _("You can't register payments for journal items being either all inbound, either all outbound."))

            res['line_ids'] = [(6, 0, available_lines.ids)]

        return res

    # def _create_payments(self):
    #     self.ensure_one()
    #     batches = self._get_batches()
    #     edit_mode = self.can_edit_wizard and (len(batches[0]['lines']) == 1 or self.group_payment)
    #
    #     to_reconcile = []
    #     if edit_mode:
    #         payment_vals = self._create_payment_vals_from_wizard()
    #         #payment_vals['tax_today'] = self.tax_today
    #         #payment_vals['currency_id_dif'] = self.currency_id_dif.id
    #         payment_vals_list = [payment_vals]
    #         to_reconcile.append(batches[0]['lines'])
    #     else:
    #         # Don't group payments: Create one batch per move.
    #         if not self.group_payment:
    #             new_batches = []
    #             for batch_result in batches:
    #                 for line in batch_result['lines']:
    #                     new_batches.append({
    #                         **batch_result,
    #                         'lines': line,
    #                     })
    #             batches = new_batches
    #
    #         payment_vals_list = []
    #         for batch_result in batches:
    #             payment_vals_list.append(self._create_payment_vals_from_batch(batch_result))
    #             to_reconcile.append(batch_result['lines'])
    #     payment_vals_list[0]['tax_today'] = self.tax_today
    #     payment_vals_list[0]['currency_id_dif'] = self.currency_id_dif.id
    #     payments = self.env['account.payment'].create(payment_vals_list)
    #
    #     # If payments are made using a currency different than the source one, ensure the balance match exactly in
    #     # order to fully paid the source journal items.
    #     # For example, suppose a new currency B having a rate 100:1 regarding the company currency A.
    #     # If you try to pay 12.15A using 0.12B, the computed balance will be 12.00A for the payment instead of 12.15A.
    #     if edit_mode:
    #         for payment, lines in zip(payments, to_reconcile):
    #             # Batches are made using the same currency so making 'lines.currency_id' is ok.
    #             if payment.currency_id != lines.currency_id:
    #                 liquidity_lines, counterpart_lines, writeoff_lines = payment._seek_for_lines()
    #                 source_balance = abs(sum(lines.mapped('amount_residual')))
    #                 payment_rate = liquidity_lines[0].amount_currency / liquidity_lines[0].balance
    #                 source_balance_converted = abs(source_balance) * payment_rate
    #
    #                 # Translate the balance into the payment currency is order to be able to compare them.
    #                 # In case in both have the same value (12.15 * 0.01 ~= 0.12 in our example), it means the user
    #                 # attempt to fully paid the source lines and then, we need to manually fix them to get a perfect
    #                 # match.
    #                 payment_balance = abs(sum(counterpart_lines.mapped('balance')))
    #                 payment_amount_currency = abs(sum(counterpart_lines.mapped('amount_currency')))
    #                 if not payment.currency_id.is_zero(source_balance_converted - payment_amount_currency):
    #                     continue
    #
    #                 delta_balance = source_balance - payment_balance
    #
    #                 # Balance are already the same.
    #                 if self.company_currency_id.is_zero(delta_balance):
    #                     continue
    #
    #                 # Fix the balance but make sure to peek the liquidity and counterpart lines first.
    #                 debit_lines = (liquidity_lines + counterpart_lines).filtered('debit')
    #                 credit_lines = (liquidity_lines + counterpart_lines).filtered('credit')
    #
    #                 payment.move_id.write({'line_ids': [
    #                     (1, debit_lines[0].id, {'debit': debit_lines[0].debit + delta_balance}),
    #                     (1, credit_lines[0].id, {'credit': credit_lines[0].credit + delta_balance}),
    #                 ]})
    #
    #     payments.action_post()
    #
    #     domain = [('account_internal_type', 'in', ('receivable', 'payable')), ('reconciled', '=', False)]
    #     for payment, lines in zip(payments, to_reconcile):
    #
    #         # When using the payment tokens, the payment could not be posted at this point (e.g. the transaction failed)
    #         # and then, we can't perform the reconciliation.
    #         if payment.state != 'posted':
    #             continue
    #
    #         payment_lines = payment.line_ids.filtered_domain(domain)
    #         for account in payment_lines.account_id:
    #             (payment_lines + lines)\
    #                 .filtered_domain([('account_id', '=', account.id), ('reconciled', '=', False)])\
    #                 .reconcile()
    #
    #     return payments