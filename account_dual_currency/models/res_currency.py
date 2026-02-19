from odoo import api, fields, models, _
from datetime import date, timedelta, datetime
from bs4 import BeautifulSoup
import requests
import urllib3
urllib3.disable_warnings()
class ResCurrency(models.Model):
    _inherit = 'res.currency'

    facturas_por_actualizar = fields.Boolean(compute="_facturas_por_actualizar")

    # habilitar sincronización automatica
    sincronizar = fields.Boolean(string="Sincronizar", default=False)

    # campo listado de servidores, bcv o dolar today
    server = fields.Selection([('bcv', 'BCV'), ('dolar_today', 'Dolar Today Promedio')], string='Servidor',
                              default='bcv')

    act_productos = fields.Boolean(string="Actualizar Productos", default=False)

    def _convert(self, from_amount, to_currency, company, date, round=True, custom_rate=0.0):
        """Returns the converted amount of ``from_amount``` from the currency
           ``self`` to the currency ``to_currency`` for the given ``date`` and
           company.

           :param company: The company from which we retrieve the convertion rate
           :param date: The nearest date from which we retriev the conversion rate.
           :param round: Round the result or not
        """
        self, to_currency = self or to_currency, to_currency or self
        assert self, "convert amount from unknown currency"
        assert to_currency, "convert amount to unknown currency"
        assert company, "convert amount from unknown company"
        assert date, "convert amount from unknown date"
        # apply conversion rate
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
        # apply rounding
        #print("from_amount", from_amount)
        #print("to_amount", to_amount)
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
            # actualizar tasa a las facturas dinamicas
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
                    #f._amount_untaxed_usd()
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
                    # buscar el producto en la lista de Bs y actualizar
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
            # Dolar
            dolar_tag = html.find('div', {'id': 'dolar'})
            if not dolar_tag:
                return False
            dolar = str(dolar_tag.find('strong')).split()
            # Handle potential parsing errors if format changes
            if len(dolar) < 2:
                return False
            dolar = str.replace(dolar[1], '.', '')
            try:
                val_usd = float(str.replace(dolar, ',', '.'))
            except ValueError:
                return False

            # Euro
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
                 # If we are strictly asking for VES rate, it's 1. 
                 # But if we want the "Dolar" value, we should probably ask for USD currency.
                 # For now, return 1.0 as standard behaviour, but get_trm_systray handles the fallback.
                return 1.0
            else:
                return False
        else:
            return False


    def get_dolar_today_promedio(self):
        url = "https://s3.amazonaws.com/dolartoday/data.json"
        response = requests.get(url)
        status_code = response.status_code

        if status_code == 200:
            response = response.json()
            usd = float(response['USD']['transferencia'])
            eur = float(response['EUR']['transferencia'])
            if self.name == 'USD':
                data = usd
            elif self.name == 'EUR':
                data = eur
            else:
                data = False

            return data
        else:
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
                    # Obtener valor BCV de la moneda base de la compañía
                    base_bcv = c.currency_id.get_bcv() or 1.0
                    
                    # Cálculo de la tasa Odoo: (Valor BCV Base / Valor BCV Destino)
                    # Ej: Base VES (1.0), Destino USD (36.5) -> Rate = 1/36.5 = 0.027...
                    # Ej: Base USD (36.5), Destino VES (1.0) -> Rate = 36.5/1 = 36.5
                    odoo_rate = base_bcv / nueva_tasa_bcv
                    
                    # Buscar tasa existente para hoy
                    tasa_actual = self.env['res.currency.rate'].sudo().search(
                        [('name', '=', today), ('currency_id', '=', rec.id), ('company_id', '=', c.id)], limit=1)
                    
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
                        else:
                            nueva = False

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

        # Busqueda directa de la ultima tasa registrada
        last_rate = self.env['res.currency.rate'].search([
            ('currency_id', '=', currency_dif.id),
            ('company_id', '=', company_id.id),
        ], order='name desc', limit=1)

        if last_rate and last_rate.rate > 0:
            # Si la tasa es menor a 1 (ej: 0.0025 USD/VES), la invertimos para mostrar 398 VES/USD
            if last_rate.rate < 1.0:
                 tasa = 1 / last_rate.rate
            else:
                 tasa = last_rate.rate
        else:
            tasa = 1.0

        # Fallback: Si la tasa es 1.0 (sin datos o error), intentar obtener del BCV para mostrar algo real
        if tasa == 1.0:
            try:
                # Explicitly try to get the USD currency rate from BCV
                usd_currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
                if usd_currency:
                    bcv_rate = usd_currency.get_bcv()
                    # Only update if we got a valid rate significantly different from 1 or 0
                    if bcv_rate and bcv_rate > 1:
                        tasa = bcv_rate
            except Exception as e:
                pass

        return round(tasa, 4)