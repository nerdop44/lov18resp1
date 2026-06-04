from odoo import api, fields, models, _
# Force deployment update
from datetime import date, timedelta, datetime
from bs4 import BeautifulSoup
import requests
import logging

_logger = logging.getLogger(__name__)
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

    def _convert(self, from_amount, to_currency, company=None, date=None, round=True, custom_rate=0.0):
        """Returns the converted amount of ``from_amount``` from the currency
           ``self`` to the currency ``to_currency`` for the given ``date`` and
           company.

           :param company: The company from which we retrieve the convertion rate
           :param date: The nearest date from which we retriev the conversion rate.
           :param round: Round the result or not
        """
        company = company or self.env.company
        date = date or fields.Date.today()
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
        curr_name = self.name
        if curr_name in ['VES', 'VEF']:
            return 1.0

        url = "https://www.bcv.org.ve/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/58.0.3029.110 Safari/537.36'
        }
        try:
            req = requests.get(url, headers=headers, verify=False, timeout=25)
        except Exception as e:
            return False

        if req.status_code == 200:
            html = BeautifulSoup(req.text, "html.parser")

            # --- USD ---
            dolar_tag = html.find('div', {'id': 'dolar'})
            if not dolar_tag:
                return False
            try:
                val_usd_str = dolar_tag.find('strong').text.strip()
                val_usd = float(val_usd_str.replace('.', '').replace(',', '.'))
            except Exception:
                return False

            # --- EUR ---
            euro_tag = html.find('div', {'id': 'euro'})
            if not euro_tag:
                val_eur = 0.0
            else:
                try:
                    val_eur_str = euro_tag.find('strong').text.strip()
                    val_eur = float(val_eur_str.replace('.', '').replace(',', '.'))
                except Exception:
                    val_eur = 0.0

            if curr_name == 'USD':
                return val_usd
            elif curr_name == 'EUR':
                return val_eur
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
                    odoo_rate = base_bcv / nueva_tasa_bcv
                    
                    # Solo creamos o actualizamos la tasa del día de hoy
                    tasa_actual = self.env['res.currency.rate'].sudo().search([
                        ('name', '=', today),
                        ('currency_id', '=', rec.id),
                        ('company_id', '=', c.id)
                    ], limit=1)
                    
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
                            body="Tasa de cambio actualizada para %s (%s): %s (en %s), servidor %s a las %s para la fecha %s." % (
                                rec.name, c.name, odoo_rate, c.currency_id.name, rec.server,
                                datetime.strftime(fields.Datetime.context_timestamp(self, datetime.now()),
                                                  "%d-%m-%Y %H:%M:%S"),
                                today.strftime("%d-%m-%Y")),
                            message_type='notification',
                            subtype_xmlid='mail.mt_comment',
                        )
                if rec.act_productos:
                    rec.actualizar_productos()

    def recuperar_tasas_historicas(self):
        for rec in self:
            if rec.name in ['VES', 'VEF']:
                continue
                
            today = fields.Date.context_today(self)
            company_ids = self.env['res.company'].search([])
            channel_id = self.env.ref('account_dual_currency.trm_channel')
            
            # 1. Determinar URL histórica según moneda
            if rec.name == 'USD':
                url = 'https://ve.dolarapi.com/v1/historicos/dolares/oficial'
            elif rec.name == 'EUR':
                url = 'https://ve.dolarapi.com/v1/historicos/euros/oficial'
            else:
                continue
                
            # 2. Consultar historial de tasas
            historical_rates = {}
            try:
                req = requests.get(url, verify=False, timeout=15)
                if req.status_code == 200:
                    data = req.json()
                    for entry in data:
                        fecha_str = entry.get('fecha')
                        promedio = entry.get('promedio')
                        if fecha_str and promedio:
                            historical_rates[fecha_str] = float(promedio)
            except Exception as e:
                _logger.error("Error al obtener histórico de tasas de DolarApi: %s", e)
                continue

            if not historical_rates:
                continue

            for c in company_ids:
                # Obtener la última tasa registrada en el sistema
                last_rate_rec = self.env['res.currency.rate'].sudo().search([
                    ('currency_id', '=', rec.id),
                    ('company_id', '=', c.id)
                ], order='name desc', limit=1)
                
                dates_to_update = []
                if last_rate_rec:
                    last_date = last_rate_rec.name
                    current_date = last_date + timedelta(days=1)
                    max_past_date = today - timedelta(days=30)
                    if current_date < max_past_date:
                        current_date = max_past_date
                    
                    while current_date <= today:
                        dates_to_update.append(current_date)
                        current_date += timedelta(days=1)
                else:
                    dates_to_update.append(today)

                for d in dates_to_update:
                    # 3. Buscar tasa en el historial (retrocediendo hasta 5 días para fines de semana/feriados)
                    rate_val = None
                    for offset in range(5):
                        check_date = d - timedelta(days=offset)
                        check_date_str = check_date.strftime("%Y-%m-%d")
                        if check_date_str in historical_rates:
                            rate_val = historical_rates[check_date_str]
                            break
                    
                    if not rate_val:
                        continue  # Si no hay registro histórico, ignoramos
                    
                    base_bcv = c.currency_id.get_bcv() or 1.0
                    odoo_rate = base_bcv / rate_val
                    
                    tasa_actual = self.env['res.currency.rate'].sudo().search([
                        ('name', '=', d),
                        ('currency_id', '=', rec.id),
                        ('company_id', '=', c.id)
                    ], limit=1)
                    
                    nueva = False
                    if not tasa_actual:
                        self.env['res.currency.rate'].sudo().create({
                            'currency_id': rec.id,
                            'name': d,
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
                            body="Tasa HISTÓRICA recuperada para %s (%s): %s para la fecha %s." % (
                                rec.name, c.name, odoo_rate, d.strftime("%d-%m-%Y")),
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
        
        _logger.info(f"TRM DEBUG: Company {company_id.name} (ID: {company_id.id}), Currency Dif: {currency_dif.name if currency_dif else 'None'}")

        if not currency_dif:
            return 0.0

        # Busqueda directa de la ultima tasa registrada
        last_rate = self.env['res.currency.rate'].search([
            ('currency_id', '=', currency_dif.id),
            ('company_id', '=', company_id.id),
        ], order='name desc', limit=1)

        tasa = 0.0
        if last_rate:
             tasa = last_rate.rate
        
        _logger.info(f"TRM DEBUG: Initial DB Rate: {tasa}")

        # Si la tasa es 0 o 1, intentar usar el inverse_rate (calculado desde Odoo) si existe
        if (tasa == 0.0 or tasa == 1.0) and currency_dif.inverse_rate and currency_dif.inverse_rate > 1:
            tasa = currency_dif.inverse_rate
            _logger.info(f"TRM DEBUG: Using Inverse Rate fallback: {tasa}")

        # Fallback: BCV Directo (Solo si sigue siendo 0 o 1)
        if tasa == 0.0 or tasa == 1.0:
            try:
                # Intentamos obtener la tasa del Dólar (USD) del BCV
                usd_currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
                if usd_currency:
                    bcv_rate = usd_currency.get_bcv()
                    if bcv_rate and bcv_rate > 1:
                        tasa = bcv_rate
                        _logger.info(f"TRM DEBUG: BCV Scrape Success: {tasa}")
            except Exception as e:
                _logger.error(f"TRM DEBUG: BCV Scrape connection failed: {e}")
                pass

        # Lógica final de visualización:
        # En Venezuela siempre queremos ver "xx.xx Bs/S por Dolar".
        if tasa < 1.0 and tasa > 0.0:
            tasa = 1.0 / tasa
            _logger.info(f"TRM DEBUG: Rate inverted for display: {tasa}")

        _logger.info(f"TRM DEBUG: Final Rate returned to systray: {round(tasa, 4)}")
        return round(tasa, 4)
