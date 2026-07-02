
from itertools import groupby
from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import AccessError, UserError, ValidationError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    currency_id_dif = fields.Many2one("res.currency",
                                      string="Moneda Dual Ref.",
                                      related="company_id.currency_id_dif",
                                      store=False, readonly=True)

    tasa_referencial = fields.Float(string="Tasa Referencial", digits=(16, 4),
                                    compute='_compute_tasa_ref_po', store=False)

    amount_total_dif = fields.Monetary(string='Total Ref.', store=False, readonly=True,
                                       compute='_compute_amount_dif_po', currency_field='currency_id_dif')
    amount_untaxed_dif = fields.Monetary(string='Base Ref.', store=False, readonly=True,
                                         compute='_compute_amount_dif_po', currency_field='currency_id_dif')
    amount_tax_dif = fields.Monetary(string='Impuesto Ref.', store=False, readonly=True,
                                     compute='_compute_amount_dif_po', currency_field='currency_id_dif')

    krill_tasa_fijada = fields.Boolean(
        string='Fijar tasa de hoy',
        default=False,
        help='Si se activa, el presupuesto usará la tasa de este momento de forma permanente (Histórica).'
    )

    krill_tasa_valor = fields.Float(
        string='Valor de Tasa Guardado',
        digits=(16, 4),
        store=True,
        readonly=True,
        help='Valor numérico de la tasa que se usará en el reporte PDF.'
    )

    krill_tasa_visual = fields.Float(
        string="Tasa de Cambio",
        digits=(16, 4),
        compute='_compute_krill_tasa_visual',
        store=False,
        readonly=False
    )

    amount_total_usd = fields.Monetary(
        string='Total ($)',
        compute='_compute_amount_total_usd',
        store=True,
        currency_field='currency_id_usd_krill'
    )

    currency_id_usd_krill = fields.Many2one(
        'res.currency',
        string='Moneda USD',
        default=lambda self: self.env.ref('base.USD')
    )

    @api.depends('krill_tasa_fijada', 'krill_tasa_valor', 'company_id', 'date_order')
    def _compute_krill_tasa_visual(self):
        for record in self:
            if not record.krill_tasa_fijada:
                record.krill_tasa_visual = self.env['res.currency'].get_trm_systray()
            else:
                if record.krill_tasa_valor:
                    record.krill_tasa_visual = record.krill_tasa_valor
                else:
                    dif = record.currency_id_dif
                    if dif:
                        target_date = record.date_order or fields.Date.today()
                        rate_entry = self.env['res.currency.rate'].search([
                            ('currency_id', '=', dif.id),
                            ('company_id', '=', record.company_id.id),
                            ('name', '<=', target_date)
                        ], order='name desc', limit=1)
                        if rate_entry:
                            tasa = rate_entry.rate
                            if 0.0 < tasa < 1.0:
                                tasa = 1.0 / tasa
                            record.krill_tasa_visual = round(tasa, 4)
                        else:
                            record.krill_tasa_visual = 1.0
                    else:
                        record.krill_tasa_visual = 1.0

    @api.depends('company_id', 'currency_id_dif', 'krill_tasa_fijada', 'krill_tasa_valor')
    def _compute_tasa_ref_po(self):
        for record in self:
            if record.krill_tasa_fijada and record.krill_tasa_valor > 0:
                record.tasa_referencial = record.krill_tasa_valor
            else:
                dif = record.currency_id_dif or record.company_id.currency_id_dif
                if dif and dif.inverse_rate:
                    record.tasa_referencial = dif.inverse_rate
                else:
                    record.tasa_referencial = 1.0

    @api.depends('amount_total', 'amount_untaxed', 'amount_tax', 'tasa_referencial', 'currency_id', 'company_id', 'krill_tasa_fijada', 'krill_tasa_valor')
    def _compute_amount_dif_po(self):
        for record in self:
            dif = record.currency_id_dif or record.company_id.currency_id_dif
            if not dif:
                record.amount_total_dif = 0
                record.amount_untaxed_dif = 0
                record.amount_tax_dif = 0
                continue
            src = record.currency_id
            company = record.company_id

            if record.krill_tasa_fijada and record.krill_tasa_valor > 0:
                tasa = record.krill_tasa_valor
            else:
                tasa = dif.inverse_rate if dif.inverse_rate and dif.inverse_rate > 0 else 1.0

            if src == dif:
                record.amount_total_dif = record.amount_total
                record.amount_untaxed_dif = record.amount_untaxed
                record.amount_tax_dif = record.amount_tax
            elif src.name != dif.name:
                record.amount_total_dif = record.amount_total * tasa
                record.amount_untaxed_dif = record.amount_untaxed * tasa
                record.amount_tax_dif = record.amount_tax * tasa
            else:
                record.amount_total_dif = record.amount_total / tasa if tasa else 0.0
                record.amount_untaxed_dif = record.amount_untaxed / tasa if tasa else 0.0
                record.amount_tax_dif = record.amount_tax / tasa if tasa else 0.0

    @api.depends('amount_total', 'tasa_referencial', 'currency_id')
    def _compute_amount_total_usd(self):
        for order in self:
            if order.currency_id.name == 'USD':
                order.amount_total_usd = order.amount_total
            else:
                tasa = order.tasa_referencial if order.tasa_referencial > 0 else 1.0
                order.amount_total_usd = order.amount_total / tasa

    def action_update_krill_rate(self):
        self.ensure_one()
        self.write({
            'tasa_referencial': self.krill_tasa_visual,
            'krill_tasa_valor': self.krill_tasa_visual
        })
        return True

    def action_create_invoice(self):
        """Create the invoice associated to the PO.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        # 1) Prepare invoice vals and clean-up the section lines
        invoice_vals_list = []
        sequence = 10
        for order in self:
            if order.invoice_status != 'to invoice':
                continue

            order = order.with_company(order.company_id)
            pending_section = None
            # Invoice values.
            invoice_vals = order._prepare_invoice()
            # Invoice line values (keep only necessary sections).
            for line in order.order_line:
                if line.display_type == 'line_section':
                    pending_section = line
                    continue
                if not float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    if pending_section:
                        line_vals = pending_section._prepare_account_move_line(move=False)
                        line_vals.update({'sequence': sequence})
                        invoice_vals['invoice_line_ids'].append((0, 0, line_vals))
                        sequence += 1
                        pending_section = None
                    line_vals = line._prepare_account_move_line(move=False)
                    line_vals.update({'sequence': sequence})
                    invoice_vals['invoice_line_ids'].append((0, 0, line_vals))
                    sequence += 1
            invoice_vals_list.append(invoice_vals)

        if not invoice_vals_list:
            raise UserError(_('There is no invoiceable line. If a product has a control policy based on received quantity, please make sure that a quantity has been received.'))

        # 2) group by (company_id, partner_id, currency_id) for batch creation
        new_invoice_vals_list = []
        for grouping_keys, invoices in groupby(invoice_vals_list, key=lambda x: (x.get('company_id'), x.get('partner_id'), x.get('currency_id'))):
            origins = set()
            payment_refs = set()
            refs = set()
            ref_invoice_vals = None
            for invoice_vals in invoices:
                if not ref_invoice_vals:
                    ref_invoice_vals = invoice_vals
                else:
                    ref_invoice_vals['invoice_line_ids'] += invoice_vals['invoice_line_ids']
                origins.add(invoice_vals['invoice_origin'])
                payment_refs.add(invoice_vals['payment_reference'])
                refs.add(invoice_vals['ref'])
            ref_invoice_vals.update({
                'ref': ', '.join(refs)[:2000],
                'invoice_origin': ', '.join(origins),
                'payment_reference': len(payment_refs) == 1 and payment_refs.pop() or False,
            })
            new_invoice_vals_list.append(ref_invoice_vals)
        invoice_vals_list = new_invoice_vals_list

        # 3) Create invoices.
        moves = self.env['account.move']
        AccountMove = self.env['account.move'].with_context(default_move_type='in_invoice',calcular_dual_currency=False)
        for vals in invoice_vals_list:
            po_currency_id = vals.get('currency_id')
            company = self.env.company
            currency_dif = company.currency_id_dif
            # If the PO currency is the same as the dual/reference currency (e.g. PO in USD
            # and currency_id_dif = USD), then tax_today must be 1.0 to avoid double conversion.
            # Only apply the inverse_rate when the PO is in the base currency (VES) and the dual is USD.
            if po_currency_id and currency_dif and po_currency_id == currency_dif.id:
                vals['tax_today'] = 1.0
            else:
                origin_names = vals.get('invoice_origin', '').split(', ')
                orders = self.env['purchase.order'].search([('name', 'in', origin_names)])
                order_fixed = orders.filtered(lambda o: o.krill_tasa_fijada and o.krill_tasa_valor > 0)
                if order_fixed:
                    vals['tax_today'] = order_fixed[0].krill_tasa_valor
                else:
                    vals['tax_today'] = currency_dif.inverse_rate if currency_dif else 1.0
            moves |= AccountMove.with_company(vals['company_id']).create(vals)

        # 4) Some moves might actually be refunds: convert them if the total amount is negative
        # We do this after the moves have been created since we need taxes, etc. to know if the total
        # is actually negative or not
        moves.filtered(lambda m: m.currency_id.round(m.amount_total) < 0).action_switch_move_type()

        return self.action_view_invoice(moves)