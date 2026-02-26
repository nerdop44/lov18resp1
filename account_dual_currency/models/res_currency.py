from odoo import api, fields, models, _
from datetime import date, timedelta, datetime
from bs4 import BeautifulSoup
import requests
import logging
from odoo.tools import SQL
from odoo.tools.misc import get_lang

_logger = logging.getLogger(__name__)
import urllib3
urllib3.disable_warnings()

class ResCurrency(models.Model):
    _inherit = 'res.currency'

    @api.model
    def _normalize_to_company_recordset(self, data):
        """ Helper to force any input into a res.company recordset. """
        if hasattr(data, 'currency_id'): # Already a recordset
            return data
        
        c_ids = []
        if isinstance(data, list):
            c_ids = [c['id'] if isinstance(c, dict) else (c.id if hasattr(c, 'id') else c) for c in data]
        elif isinstance(data, dict):
            if 'id' in data:
                c_ids = [data['id']]
            else:
                c_ids = [int(k) for k, v in data.items() if v and str(k).isdigit()]
        elif isinstance(data, (int, str)):
            try:
                c_ids = [int(data)]
            except:
                pass
        elif hasattr(data, 'ids'):
            c_ids = data.ids
            
        if c_ids:
            return self.env['res.company'].browse(c_ids)
        return self.env.company

    @api.model
    def _get_query_currency_table(self, options):
        """ Final Resolution V6.6: Manual 'VALUES' Table Construction.
        This ignores Odoo's internal methods which have inconsistent signatures
        and return partial SQL fragments. We build a full, valid PostgreSQL 
        VALUES table with all required columns: company_id, rate, and precision.
        """
        companies = self._normalize_to_company_recordset(options.get('companies') if isinstance(options, dict) else options)
        
        rows = []
        for company in companies:
            # We use 1.0 as the rate for the dual currency engine's internal table
            # because the dual currency amounts (balance_usd) are already calculated.
            # Precision is taken from the company's main currency.
            rows.append(SQL("(%(company_id)s, 1.0, %(precision)s)", 
                company_id=company.id, 
                precision=company.currency_id.decimal_places or 2
            ))
        
        if not rows:
            # Defensive fallback if no companies found
            rows = [SQL("(%(company_id)s, 1.0, 2)", company_id=self.env.company.id)]

        # Construct the final SQL: (VALUES (c1, r1, p1), (c2, r2, p2)) AS currency_table(company_id, rate, precision)
        return SQL("(VALUES %(rows)s) AS currency_table(company_id, rate, precision)", 
            rows=SQL(', ').join(rows)
        )

    @api.model
    def _check_currency_table_monocurrency(self, companies):
        # Override to ensure it uses our normalized recordsets
        companies_rs = self._normalize_to_company_recordset(companies)
        return super()._check_currency_table_monocurrency(companies_rs)

    # --- Business Logic (Restored) ---

    facturas_por_actualizar = fields.Boolean(compute="_facturas_por_actualizar")
    sincronizar = fields.Boolean(string="Sincronizar", default=False)
    server = fields.Selection([('bcv', 'BCV'), ('dolar_today', 'Dolar Today Promedio')], string='Servidor',
                              default='bcv')
    act_productos = fields.Boolean(string="Actualizar Productos", default=False)

    def _convert(self, from_amount, to_currency, company, date, round=True, custom_rate=0.0):
        self, to_currency = self or to_currency, to_currency or self
        assert self, "convert amount from unknown currency"
        to_currency = to_currency or self
        if not company:
            company = self.env.company
        if not date:
            date = fields.Date.context_today(self)
        
        if self == to_currency:
            to_amount = from_amount
        else:
            if custom_rate > 0:
                to_amount = from_amount * custom_rate
            elif self.env.context.get('tasa_factura'):
                if to_currency == self.env.company.currency_id_dif:
                    to_amount = from_amount / self.env.context.get('tasa_factura')
                else:
                    to_amount = from_amount * self.env.context.get('tasa_factura')
            else:
                to_amount = from_amount * self._get_conversion_rate(self, to_currency, company, date)
        
        return to_currency.round(to_amount) if round else to_amount

    def _facturas_por_actualizar(self):
        for rec in self:
            if rec.name == self.env.company.currency_id_dif.name:
                if self.env['account.move'].search_count([('state', 'in', ['draft','posted'])]):
                    rec.facturas_por_actualizar = True
                else:
                    rec.facturas_por_actualizar = False
            else:
                rec.facturas_por_actualizar = False

    def actualizar_facturas(self):
        for rec in self:
            facturas = self.env['account.move'].search([('acuerdo_moneda', '=', True)])
            if facturas:
                for f in facturas:
                    f.tax_today = rec.inverse_rate
                    for l in f.line_ids:
                        l.tax_today = rec.inverse_rate
                        l._debit_usd()
                        l._credit_usd()
                    for d in f.invoice_line_ids:
                        d.tax_today = rec.inverse_rate
                        d._price_unit_usd()
                        d._price_subtotal_usd()
                    f._amount_all_usd()
                    f._compute_payments_widget_reconciled_info_USD()

    def actualizar_productos(self):
        for rec in self:
            product_ids = self.env['product.template'].search([('list_price_usd','>',0)])
            for p in product_ids:
                p.list_price = p.list_price_usd * rec.inverse_rate

            product_product_ids = self.env['product.product'].search([('list_price_usd', '>', 0)])
            for p in product_product_ids:
                p.list_price = p.list_price_usd * rec.inverse_rate

            list_product_ids = self.env['product.pricelist.item'].search([('currency_id', '=', self.id)])

            for lp in list_product_ids:
                if lp.pricelist_id.pricelist_bs_id:
                    dominio = [('pricelist_id', '=', lp.pricelist_id.pricelist_bs_id.id)]
                    if lp.product_id:
                        dominio.append((('product_id', '=', lp.product_id.id)))
                    elif lp.product_tmpl_id:
                        dominio.append((('product_tmpl_id', '=', lp.product_tmpl_id.id)))
                    product_id_bs = self.env['product.pricelist.item'].search(dominio)
                    for p in product_id_bs:
                        p.fixed_price = lp.fixed_price * rec.inverse_rate
                else:
                    dominio = [('currency_id', '=', lp.company_id.currency_id.id or self.env.company.currency_id.id)]
                    if lp.product_id:
                        dominio.append((('product_id', '=', lp.product_id.id)))
                    elif lp.product_tmpl_id:
                        dominio.append((('product_tmpl_id', '=', lp.product_tmpl_id.id)))
                    product_id_bs = self.env['product.pricelist.item'].search(dominio)
                    for p in product_id_bs:
                        p.fixed_price = lp.fixed_price * rec.inverse_rate

            channel_id = self.env.ref('account_dual_currency.trm_channel')
            channel_id.message_post(
                body="Todos los productos han sido actualizados con la nueva tasa de cambio",
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

    def get_bcv(self):
        url = "https://www.bcv.org.ve/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
        }
        try:
            req = requests.get(url, headers=headers, verify=False, timeout=10)
        except Exception as e:
            return False

        status_code = req.status_code
        if status_code == 200:
            html = BeautifulSoup(req.text, "html.parser")
            dolar_tag = html.find('div', {'id': 'dolar'})
            if not dolar_tag:
                return False
            dolar = str(dolar_tag.find('strong')).split()
            if len(dolar) < 2:
                return False
            dolar = str.replace(dolar[1], '.', '')
            try:
                val_usd = float(str.replace(dolar, ',', '.'))
            except ValueError:
                return False

            euro_tag = html.find('div', {'id': 'euro'})
            if not euro_tag:
                val_eur = 0.0
            else:
                euro = str(euro_tag.find('strong')).split()
                if len(euro) > 1:
                    euro = str.replace(euro[1], '.', '')
                    try:
                        val_eur = float(str.replace(euro, ',', '.'))
                    except ValueError:
                        val_eur = 0.0
                else:
                    val_eur = 0.0

            curr_name = self.name
            if curr_name == 'USD':
                return val_usd
            elif curr_name == 'EUR':
                return val_eur
            elif curr_name in ['VES', 'VEF']:
                return 1.0
            else:
                return False
        else:
            return False

    def get_dolar_today_promedio(self):
        url = "https://s3.amazonaws.com/dolartoday/data.json"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data_json = response.json()
                usd = float(data_json['USD']['transferencia'])
                eur = float(data_json['EUR']['transferencia'])
                if self.name == 'USD':
                    return usd
                elif self.name == 'EUR':
                    return eur
            return False
        except:
            return False

    def actualizar_tasa(self):
        for rec in self:
            nueva_tasa_bcv = 0
            if rec.server == 'bcv':
                nueva_tasa_bcv = rec.get_bcv()
            elif rec.server == 'dolar_today':
                nueva_tasa_bcv = rec.get_dolar_today_promedio()

            if nueva_tasa_bcv:
                channel_id = self.env.ref('account_dual_currency.trm_channel')
                company_ids = self.env['res.company'].search([])
                today = fields.Date.context_today(self)
                
                for c in company_ids:
                    base_bcv = c.currency_id.get_bcv() or 1.0
                    odoo_rate = base_bcv / nueva_tasa_bcv
                    
                    tasa_actual = self.env['res.currency.rate'].sudo().search(
                        [('name', '=', today), ('currency_id', '=', rec.id), ('company_id', '=', c.id)], limit=1)
                    
                    nueva = False
                    if not tasa_actual:
                        self.env['res.currency.rate'].sudo().create({
                                'currency_id': rec.id,
                                'name': today,
                                'rate': odoo_rate,
                                'company_id': c.id,
                        })
                        nueva = True
                    else:
                        if abs(tasa_actual.rate - odoo_rate) > 0.000001:
                            tasa_actual.rate = odoo_rate
                            nueva = True

                    if nueva:
                        channel_id.message_post(
                            body="Tasa de cambio actualizada para %s (%s): %s (en %s), servidor %s a las %s." % (
                                rec.name, c.name, odoo_rate, c.currency_id.name, rec.server,
                                datetime.strftime(fields.Datetime.context_timestamp(self, datetime.now()),
                                                  "%d-%m-%Y %H:%M:%S")),
                            message_type='notification',
                            subtype_xmlid='mail.mt_comment',
                        )
                if rec.act_productos:
                    rec.actualizar_productos()

    @api.model
    def _cron_actualizar_tasa(self):
        monedas = self.env['res.currency'].search([('active', '=', True), ('sincronizar', '=',True)])
        for m in monedas:
            m.actualizar_tasa()

    @api.model
    def get_trm_systray(self):
        company_id = self.env.company
        currency_dif = company_id.currency_id_dif
        
        if not currency_dif:
            return 0.0

        last_rate = self.env['res.currency.rate'].search([
            ('currency_id', '=', currency_dif.id),
            ('company_id', '=', company_id.id),
        ], order='name desc', limit=1)

        tasa = 0.0
        if last_rate:
             tasa = last_rate.rate
        
        if (tasa == 0.0 or tasa == 1.0) and currency_dif.inverse_rate and currency_dif.inverse_rate > 1:
            tasa = currency_dif.inverse_rate

        if tasa == 0.0 or tasa == 1.0:
            try:
                usd_currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
                if usd_currency:
                    bcv_rate = usd_currency.get_bcv()
                    if bcv_rate and bcv_rate > 1:
                        tasa = bcv_rate
            except:
                pass

        if tasa < 1.0 and tasa > 0.0:
            tasa = 1.0 / tasa

        return round(tasa, 4)
