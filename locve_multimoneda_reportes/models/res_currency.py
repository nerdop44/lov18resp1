# [LocVe] RC Multi-Moneda: Override de res.currency
# Solo contiene _get_query_currency_table para los reportes contables.

from odoo import api, models
from odoo.tools import SQL


class ResCurrencyReports(models.Model):
    _inherit = 'res.currency'

    @api.model
    def _normalize_to_company_recordset(self, data):
        """Helper: fuerza cualquier input a un recordset de res.company."""
        if hasattr(data, 'currency_id'):
            return data
        c_ids = []
        if isinstance(data, list):
            c_ids = [
                c['id'] if isinstance(c, dict) else (c.id if hasattr(c, 'id') else c)
                for c in data
            ]
        elif isinstance(data, dict) and 'id' in data:
            c_ids = [data['id']]
        elif isinstance(data, (int,)):
            c_ids = [data]
        elif hasattr(data, 'ids'):
            c_ids = data.ids
        if c_ids:
            return self.env['res.company'].browse(c_ids)
        return self.env.company

    @api.model
    def _get_query_currency_table(self, options):
        """
        V7.0 Universal: Tabla de moneda con las 7 columnas de Enterprise + precision.
        Columnas: company_id, period_key, date_from, date_next, rate_type, rate, precision
        """
        companies = self._normalize_to_company_recordset(
            options.get('companies') if isinstance(options, dict) else options
        )
        rows = []
        for company in companies:
            rows.append(SQL(
                "(%(company_id)s, NULL, NULL, NULL, NULL, 1.0, %(precision)s)",
                company_id=company.id,
                precision=company.currency_id.decimal_places or 2
            ))
        if not rows:
            rows = [SQL(
                "(%(company_id)s, NULL, NULL, NULL, NULL, 1.0, 2)",
                company_id=self.env.company.id
            )]
        return SQL(
            "(VALUES %(rows)s) AS currency_table(company_id, period_key, date_from, date_next, rate_type, rate, precision)",
            rows=SQL(', ').join(rows)
        )
