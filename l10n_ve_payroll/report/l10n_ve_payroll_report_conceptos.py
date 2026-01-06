
from odoo import models, api, fields, _
from odoo.tools.misc import formatLang, format_date, xlsxwriter
from odoo.tools import config, date_utils, get_lang, float_compare, float_is_zero
import datetime
import pandas as pd
import locale
#locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
class VenezuelaReportCustomHandlerConceptos(models.AbstractModel):
    _name = 'l10n_ve_payroll.report.handler.conceptos'
    _inherit = 'l10n_ve_payroll.report.handler'
    _description = 'Venezuela Payroll Report Conceptos'

    def _custom_options_initializer(self, report, options, previous_options=None):
        if previous_options:
            if 'slip_ids' in previous_options:
                del previous_options['slip_ids']

        if self.env.context.get('previous_options', False):
            previous_options = None
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        if 'date' in options:
            date_from_context = self.env.context.get('date_from')
            date_to_context = self.env.context.get('date_to')
            if date_from_context and date_to_context:
                options['date']['date_from'] = date_from_context
                options['date']['date_to'] = date_to_context
                options['date']['mode'] = 'range'
                options['date']['filter'] = 'custom'
                options['date']['string'] = 'Desde %s - Hasta %s' % (
                datetime.datetime.strptime(date_from_context, "%Y-%m-%d").strftime("%d/%m/%Y"),
                datetime.datetime.strptime(date_to_context, "%Y-%m-%d").strftime("%d/%m/%Y"))

                options['column_headers'] = [
                    [{'name': options['date']['string'],
                      'forced_options': {
                          'date': options['date'],
                      }
                      }],
                ]
            else:
                if 'date' in previous_options:
                    del previous_options['date']
        slip_ids = self.env.context.get('slip_ids')
        if slip_ids:
            options['slip_ids'] = slip_ids
        else:
            if 'slip_ids' in previous_options:
                del previous_options['slip_ids']
        self.env.context = dict(self.env.context, date_from=None, date_to=None, slip_ids=None)


    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals):
        company_id = self.env.context.get('company_id') or self.env.company.id
        company_id = self.env['res.company'].browse(company_id)
        currency_company = company_id.currency_id
        date_from = options['date']['date_from']
        date_to = options['date']['date_to']
        slip_ids = options['slip_ids'] if 'slip_ids' in options else self.env.context.get('slip_ids')
        campo_total = 'total'
        currency_dif = options['currency_dif']
        if not currency_dif == self.env.company.currency_id.symbol:
            campo_total = 'total_usd'
        lines = []
        payslip_line_ids = self.env['hr.payslip.line'].search(
            [('date_from', '>=', date_from), ('date_to', '<=', date_to),
             ('slip_id.state', 'in', ['done', 'paid', 'verify']),
             ('slip_id.company_id', '=', company_id.id)])
        if slip_ids:
            payslip_line_ids = payslip_line_ids.filtered(lambda x: x.slip_id.id in slip_ids)

        x = 1
        if payslip_line_ids:
            # primera agrupación por categoría
            category_ids = payslip_line_ids.mapped('category_id')
            for c in category_ids:
                line_id = report._get_generic_line_id('hr.salary.rule.category', c.id)
                total = payslip_line_ids.filtered(lambda x: x.category_id.id == c.id).mapped(campo_total)

                lines.append((x, {
                    'id': line_id,
                    'name': c.name,
                    'style': 'background-color: #f2f2f2;',
                    'level': 1,
                    'unfoldable': False,
                    'unfolded': False,
                    'columns': [
                                {'name': self.format_value(sum(total), currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'}],
                }))
                x += 1

                # segunda agrupación por reglas
                reglas_code = payslip_line_ids.filtered(lambda x: x.category_id.id == c.id).mapped('code')
                #colocar reglas agrupados como unicos
                reglas_code = list(set(reglas_code))
                for r in reglas_code:
                    rule_ids = payslip_line_ids.filtered(lambda x: x.category_id.id == c.id).filtered(lambda x: x.code == r)
                    line_id = report._get_generic_line_id('hr.salary.rule', rule_ids[0].id)
                    codigo_concepto = r
                    descripcion = rule_ids[0].name
                    total = payslip_line_ids.filtered(lambda x: x.code == r).mapped(campo_total)
                    columns_rule = [

                                    {'name': self.format_value(sum(total), currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'}]

                    lines.append((x, {
                        'id': line_id,
                        'name': descripcion,
                        'level': 3,
                        'unfoldable': False,
                        'unfolded': False,
                        'columns': columns_rule,
                    }))
                    x += 1

        return lines


