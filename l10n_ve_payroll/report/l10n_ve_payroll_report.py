
from odoo import models, api, fields, _
from odoo.tools.misc import formatLang, format_date, xlsxwriter
from odoo.tools import config, date_utils, get_lang, float_compare, float_is_zero
import pandas as pd
import locale
#locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
class VenezuelaReportCustomHandler(models.AbstractModel):
    _name = 'l10n_ve_payroll.report.handler'
    _inherit = 'account.report.custom.handler'
    _description = 'Venezuela Report Custom Handler'

    @api.model
    def is_zero(self, amount, currency=False, figure_type=None, digits=1):
        if figure_type == 'monetary':
            currency = currency or self.env.company.currency_id
            return currency.is_zero(amount)

        if figure_type == 'integer':
            digits = 0
        return float_is_zero(amount, precision_digits=digits)

    @api.model
    def format_value(self, value, currency=False, blank_if_zero=True, figure_type=None, digits=2):
        """ Formats a value for display in a report (not especially numerical). figure_type provides the type of formatting we want.
        """
        if figure_type == 'none':
            return value

        if value is None:
            return ''

        if figure_type == 'monetary':
            currency = currency or self.env.company.currency_id
            if self._context.get('currency_dif'):
                if self._context.get('currency_dif') == self._context.get('currency_id_company_name'):
                    currency = self.env.company.currency_id
                else:
                    currency = self.env.company.currency_id_dif
            digits = None
        elif figure_type in ('date', 'datetime'):
            return format_date(self.env, value)
        else:
            currency = None

        if self.is_zero(value, currency=currency, figure_type=figure_type, digits=digits):
            if blank_if_zero:
                return ''
            # don't print -0.0 in reports
            value = abs(value)

        if self._context.get('no_format'):
            return value

        formatted_amount = formatLang(self.env, value, currency_obj=currency, digits=digits)

        if figure_type == 'percentage':
            return f"{formatted_amount}%"

        return formatted_amount