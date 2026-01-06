
from odoo import models, api, fields, _
from odoo.tools.misc import formatLang, format_date, xlsxwriter
from odoo.tools import config, date_utils, get_lang, float_compare, float_is_zero
import datetime
import pandas as pd
import locale
#locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
class VenezuelaReportCustomHandlerFaov(models.AbstractModel):
    _name = 'l10n_ve_payroll.report.handler.faov'
    _inherit = 'l10n_ve_payroll.report.handler'
    _description = 'Venezuela FAOV Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        if 'date' in options:
            date_from_context = self.env.context.get('date_from')
            date_to_context = self.env.context.get('date_to')
            if date_from_context and date_to_context:
                options['date']['date_from'] = date_from_context
                options['date']['date_to'] = date_to_context
                options['date']['mode'] = 'range'
                options['date']['filter'] = 'custom'
                options['date']['string'] = 'Desde %s - Hasta %s' % (datetime.datetime.strptime(date_from_context, "%Y-%m-%d").strftime("%d/%m/%Y"), datetime.datetime.strptime(date_to_context, "%Y-%m-%d").strftime("%d/%m/%Y"))

                options['column_headers'] = [
                    [{'name': options['date']['string'],
                      'forced_options': {
                          'date': options['date'],
                      }
                      }],
                ]
                self.env.context = dict(self.env.context, date_from=None, date_to=None)
        structure_ids = self.env.context.get('structure_ids')
        rule_employee_integral_ids = self.env.context.get('rule_employee_integral_ids')
        rule_employee_retenido_ids = self.env.context.get('rule_employee_retenido_ids')
        rule_company_aporte_ids = self.env.context.get('rule_company_aporte_ids')
        if structure_ids:
            options['structure_ids'] = structure_ids
        if rule_employee_integral_ids:
            options['rule_employee_integral_ids'] = rule_employee_integral_ids
        if rule_employee_retenido_ids:
            options['rule_employee_retenido_ids'] = rule_employee_retenido_ids
        if rule_company_aporte_ids:
            options['rule_company_aporte_ids'] = rule_company_aporte_ids

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals):
        options['column_headers'] = [
            [{'name': options['date']['string'],
              'forced_options': {
                  'date': options['date'],
              }
              }],
        ]

        company_id = self.env.context.get('company_id') or self.env.company.id
        company_id = self.env['res.company'].browse(company_id)
        currency_company = company_id.currency_id

        trm = 1
        currency_dif = options['currency_dif']
        if not currency_dif == self.env.company.currency_id.symbol:
            trm = self.env.company.currency_id_dif.rate
        lines = []

        structure_ids = options['structure_ids'] if 'structure_ids' in options else self.env.context.get('structure_ids')
        rule_employee_integral_ids = options['rule_employee_integral_ids'] if 'rule_employee_integral_ids' in options else self.env.context.get('rule_employee_integral_ids')
        rule_employee_retenido_ids = options['rule_employee_retenido_ids'] if 'rule_employee_retenido_ids' in options else self.env.context.get('rule_employee_retenido_ids')
        rule_company_aporte_ids = options['rule_company_aporte_ids'] if 'rule_company_aporte_ids' in options else self.env.context.get('rule_company_aporte_ids')
        date_from = options['date']['date_from']
        date_to = options['date']['date_to']

        reglas = rule_employee_integral_ids + rule_employee_retenido_ids + rule_company_aporte_ids

        payslip_line_ids = self.env['hr.payslip.line'].search(
            [('date_from', '>=', date_from), ('date_to', '<=', date_to),
             ('salary_rule_id', 'in', reglas),
             ('slip_id.struct_id', 'in', structure_ids), ('slip_id.state', 'in', ['done', 'paid', 'verify']),
             ('slip_id.company_id', '=', company_id.id)])

        x = 1
        if payslip_line_ids:
            # primera agrupación por departamento
            departamentos = payslip_line_ids.mapped('department_id')
            for d in departamentos:
                line_id = report._get_generic_line_id('hr.department', d.id)
                meses_data = []
                total_integral = payslip_line_ids.filtered(lambda x: x.department_id.id == d.id and x.salary_rule_id.id in rule_employee_integral_ids).mapped('total')
                total_retenido = payslip_line_ids.filtered(lambda x: x.department_id.id == d.id and x.salary_rule_id.id in rule_employee_retenido_ids).mapped('total')
                total_aporte = payslip_line_ids.filtered(lambda x: x.department_id.id == d.id and x.salary_rule_id.id in rule_company_aporte_ids).mapped('total')
                total = sum(total_retenido) + sum(total_aporte)
                columns_departamento = [{'name': self.format_value(sum(total_integral), currency=currency_company,
                                                                   blank_if_zero=True, figure_type='monetary'),
                                         'class': 'number'},
                                        {'name': self.format_value(sum(total_retenido), currency=currency_company,
                                                                   blank_if_zero=True, figure_type='monetary'),
                                         'class': 'number'},
                                        {'name': self.format_value(sum(total_aporte), currency=currency_company,
                                                                   blank_if_zero=True, figure_type='monetary'),
                                         'class': 'number'},
                                        {'name': self.format_value(total, currency=currency_company,
                                                                   blank_if_zero=True, figure_type='monetary'),
                                         'class': 'number'}]

                lines.append((0, {
                    'id': line_id,
                    'name': d.name,
                    'style': 'background-color: #f2f2f2;',
                    'level': 1,
                    'unfoldable': False,
                    'unfolded': line_id in options.get('unfolded_lines'),
                    'expand_function': None,
                    'columns': columns_departamento,
                }))

                # agrupar por empleado
                lines_employee = payslip_line_ids.filtered(lambda x: x.department_id.id == d.id).mapped('employee_id')
                for l in lines_employee:
                    line_id = report._get_generic_line_id('hr.employee', l.id)
                    meses_data = []
                    total_integral = payslip_line_ids.filtered(lambda x: x.employee_id.id == l.id and x.salary_rule_id.id in rule_employee_integral_ids).mapped('total')
                    total_retenido = payslip_line_ids.filtered(lambda x: x.employee_id.id == l.id and x.salary_rule_id.id in rule_employee_retenido_ids).mapped('total')
                    total_aporte = payslip_line_ids.filtered(lambda x: x.employee_id.id == l.id and x.salary_rule_id.id in rule_company_aporte_ids).mapped('total')
                    total = sum(total_retenido) + sum(total_aporte)
                    columns = [{'name': self.format_value(sum(total_integral), currency=currency_company,
                                                                   blank_if_zero=True, figure_type='monetary'),
                                         'class': 'number'},
                                        {'name': self.format_value(sum(total_retenido), currency=currency_company,
                                                                   blank_if_zero=True, figure_type='monetary'),
                                         'class': 'number'},
                                        {'name': self.format_value(sum(total_aporte), currency=currency_company,
                                                                   blank_if_zero=True, figure_type='monetary'),
                                         'class': 'number'},
                                        {'name': self.format_value(total, currency=currency_company,
                                                                   blank_if_zero=True, figure_type='monetary'),
                                         'class': 'number'}]

                    lines.append((x, {
                        'id': line_id,
                        'name': '%s  %s' % (l.rif,l.name),
                        'level': 3,
                        'unfoldable': False,
                        'unfolded': line_id in options.get('unfolded_lines'),
                        'expand_function': None,
                        'columns': columns,
                    }))
                    x += 1

            x += 1

            # agregar linea a nivel total
            total_integral = payslip_line_ids.filtered(lambda x: x.salary_rule_id.id in rule_employee_integral_ids).mapped('total')
            total_retenido = payslip_line_ids.filtered(lambda x: x.salary_rule_id.id in rule_employee_retenido_ids).mapped('total')
            total_aporte = payslip_line_ids.filtered(lambda x: x.salary_rule_id.id in rule_company_aporte_ids).mapped('total')
            total = sum(total_retenido) + sum(total_aporte)
            columns_total = [{'name': self.format_value(sum(total_integral), currency=currency_company,
                                                                      blank_if_zero=True, figure_type='monetary'),
                                          'class': 'number'},
                                         {'name': self.format_value(sum(total_retenido), currency=currency_company,
                                                                     blank_if_zero=True, figure_type='monetary'),
                                          'class': 'number'},
                                         {'name': self.format_value(sum(total_aporte), currency=currency_company,
                                                                     blank_if_zero=True, figure_type='monetary'),
                                          'class': 'number'},
                                         {'name': self.format_value(total, currency=currency_company,
                                                                     blank_if_zero=True, figure_type='monetary'),
                                          'class': 'number'}]

            lines.append((x, {
                'id': report._get_generic_line_id(None, None, markup='total', parent_line_id=None),
                'name': 'Total',
                'level': 1,
                'unfoldable': False,
                'unfolded': False,
                'expand_function': None,
                'columns': columns_total,
            }))

        return lines



