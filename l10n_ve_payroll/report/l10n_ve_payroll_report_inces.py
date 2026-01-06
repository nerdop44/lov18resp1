
from odoo import models, api, fields, _
from odoo.tools.misc import formatLang, format_date, xlsxwriter
from odoo.tools import config, date_utils, get_lang, float_compare, float_is_zero
import pandas as pd
import locale
#locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
class VenezuelaReportCustomHandlerInces(models.AbstractModel):
    _name = 'l10n_ve_payroll.report.handler.inces'
    _inherit = 'l10n_ve_payroll.report.handler'
    _description = 'Venezuela Inces Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options=None):

        # options['buttons'].append({
        #           'name': 'Imprimir Planillas',
        #           'sequence': 10,
        #           'action': 'export_file',
        #           'action_param': 'export_to_pdf',
        #           'file_export_type': 'PDF'
        #         })


        super()._custom_options_initializer(report, options, previous_options=previous_options)

        meses = pd.date_range(options['date']['date_from'], options['date']['date_to'], freq="1D").strftime(
            "%B").drop_duplicates().tolist()

        for i in range(len(meses)):
            meses[i] = meses[i]
            options['columns'].append({
                'name': meses[i],
                'no_format': meses[i],
                'class': 'number',
                'style': 'width: 100px;',
                'expression_label': meses[i],
                'figure_type': 'monetary',
                'column_group_key': list(options['column_groups'].keys())[0],
            })
        options['columns'].append({
            'name': 'Total',
            'no_format': 'Total',
            'class': 'number',
            'style': 'width: 100px;',
            'expression_label': 'Total',
            'figure_type': 'monetary',
            'column_group_key': list(options['column_groups'].keys())[0],
        })
        options['meses'] = meses

    def _get_domain(self, report, options):
        domain = []
        return domain

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals):
        print('options', options)
        currency_company = self.env.company.currency_id
        trm = 1
        currency_dif = options['currency_dif']
        if not currency_dif == self.env.company.currency_id.symbol:
            trm = self.env.company.currency_id_dif.rate
        lines = []
        #buscar todas las lineas de hr_payslip_line con código APORINCES
        lines_APORINCES = self.env['hr.payslip.line'].search([('slip_id.state','in',['done','paid', 'verify']),('code','=','APORINCES'),('slip_id.date_from','>=',options['date']['date_from']),('slip_id.date_to','<=',options['date']['date_to'])])
        lines_RINCES = self.env['hr.payslip.line'].search([('slip_id.state','in',['done','paid', 'verify']),('code','=','RINCES'),('slip_id.date_from','>=',options['date']['date_from']),('slip_id.date_to','<=',options['date']['date_to'])])
        lines_inces = lines_APORINCES + lines_RINCES

        x = 1
        if lines_inces:
            #primera agrupación por departamento
            departamentos = lines_inces.mapped('department_id')
            for d in departamentos:
                line_id = report._get_generic_line_id('hr.department', d.id)
                meses_data = []
                total = 0
                columns_departamento = []
                for m in options['meses']:
                    mes = lines_inces.filtered(lambda x: x.department_id.id == d.id and x.slip_id.date_from.strftime("%B") == m).mapped('total')
                    meses_data.append({
                        m: sum(mes) * trm
                    })
                    total += (sum(mes) * trm)
                    columns_departamento.append({'name': self.format_value(sum(mes) * trm, currency=currency_company, blank_if_zero=True, figure_type='monetary'),  'class': 'number'})

                lines.append((0, {
                    'id': line_id,
                    'name': d.name,
                    'style': 'background-color: #f2f2f2;',
                    'level': 1,
                    'unfoldable': False,
                    'unfolded': line_id in options.get('unfolded_lines'),
                    'expand_function': None,
                    'columns': columns_departamento + [{'name': self.format_value(total, currency=currency_company, blank_if_zero=True, figure_type='monetary'),  'class': 'number'}],
                }))


                #agrupar por empleado
                lines_employee = lines_inces.filtered(lambda x: x.department_id.id == d.id).mapped('employee_id')
                for l in lines_employee:
                    line_id = report._get_generic_line_id('hr.employee', l.id)
                    meses_data = []
                    total = 0
                    columns = []
                    for m in options['meses']:
                        mes = lines_inces.filtered(lambda x: x.employee_id.id == l.id and x.slip_id.date_from.strftime("%B") == m).mapped('total')
                        meses_data.append({
                            m: sum(mes) * trm
                        })
                        total += (sum(mes) * trm)

                    for m in meses_data:
                        columns.append({'name': self.format_value(list(m.values())[0], currency=currency_company, blank_if_zero=True, figure_type='monetary'),  'class': 'number'})

                    lines.append((x, {
                        'id': line_id,
                        'name': '%s  %s' % (l.rif,l.name),
                        'level': 3,
                        'unfoldable': False,
                        'unfolded': line_id in options.get('unfolded_lines'),
                        'expand_function': None,
                        'columns': columns + [{'name': self.format_value(total, currency=currency_company, blank_if_zero=True, figure_type='monetary'),  'class': 'number'}],
                    }))
                    x += 1

            #agregar linea a nivel total
            columns_total = []
            total = 0
            for m in options['meses']:
                mes = lines_inces.filtered(lambda x: x.slip_id.date_from.strftime("%B") == m).mapped('total')
                total += (sum(mes) * trm)
                columns_total.append({'name': self.format_value(sum(mes) * trm, currency=currency_company, blank_if_zero=True, figure_type='monetary'),  'class': 'number'})
            columns_total.append({'name': self.format_value(total, currency=currency_company, blank_if_zero=True, figure_type='monetary'),  'class': 'number'})

            x += 1

            trm = round(1 / trm, self.env.company.currency_id_dif.decimal_places)
            lines.append((x, {
                'id': report._get_generic_line_id(None, None, markup='total'),
                'name': ('Total %s' % ('(TRM: %s)' % trm)) if not currency_dif == self.env.company.currency_id.symbol else 'Total',
                'class': 'total',
                'level': 1,
                'columns': columns_total,
            }))

        return lines



