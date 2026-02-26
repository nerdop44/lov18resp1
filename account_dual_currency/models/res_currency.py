from odoo import api, fields, models, _
from datetime import date, timedelta, datetime
from bs4 import BeautifulSoup
import requests
import logging
from odoo.tools import SQL

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
    def _get_simple_currency_table(self, companies_or_options):
        # Odoo 18 Global Defensive Fix V6.4:
        # We must ensure that companies inside options are recordsets
        # AND we must pass the correct type to super()
        
        if isinstance(companies_or_options, dict):
            options = companies_or_options
            companies_data = options.get('companies')
            if companies_data is not None:
                # Force companies in options to be Recordset
                options['companies'] = self._normalize_to_company_recordset(companies_data)
            return super()._get_simple_currency_table(options)
        
        # If not a dict, it must be the 'companies' recordset (Community/Internal)
        companies = self._normalize_to_company_recordset(companies_or_options)
        return super()._get_simple_currency_table(companies)

    @api.model
    def _get_query_currency_table(self, options):
        """ Enterprise compatibility bridge. 
        Returns the currency table with the 'currency_table' alias.
        """
        ct_sql_base = self._get_simple_currency_table(options)
        return SQL("(%(subquery)s) AS currency_table", subquery=ct_sql_base)

    @api.model
    def _check_currency_table_monocurrency(self, companies):
        # Extra safety V6.4
        companies_rs = self._normalize_to_company_recordset(companies)
        return super()._check_currency_table_monocurrency(companies_rs)


    facturas_por_actualizar = fields.Boolean(compute="_facturas_por_actualizar")

    # habilitar sincronización automatica
    sincronizar = fields.Boolean(string="Sincronizar", default=False)

    def _facturas_por_actualizar(self):
        for rec in self:
            facturas = self.env['account.move'].search_count([('state', '=', 'posted'), ('factura_por_actualizar', '=', True), ('currency_id', '=', rec.id)])
            if facturas > 0:
                rec.facturas_por_actualizar = True
            else:
                rec.facturas_por_actualizar = False
