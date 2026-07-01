from datetime import datetime

import xlsxwriter
from odoo import _, api, fields, models
from odoo.osv import expression

import logging

_logger = logging.getLogger(__name__)


class WizardAccountingReports(models.TransientModel):
    _inherit = "wizard.accounting.reports"

    def _determinate_resume_retention_books(self, moves):
        retention_resume_lines = []
        retention_moves = moves.filtered(lambda m: bool(m.retention_iva_line_ids.ids))
        credit_notes = retention_moves.filtered(
            lambda m: m.move_type in ["out_refund", "in_refund"]
        )
        retention_moves -= credit_notes

        retention_resume_lines.append(0.0)
        retention_resume_lines.append(
            sum(
                [
                    self._sum_retention_total(
                        move.retention_iva_line_ids.filtered(
                            lambda x: x.retention_id.state == "emitted"
                            and not self._check_future_retention_dates(
                                x.retention_id.date_accounting
                            )
                        )
                    )
                    for move in retention_moves
                ]
            )
        )
        retention_resume_lines.append(0.0)
        retention_resume_lines.append(
            sum(
                [
                    self._sum_retention_total(
                        move.retention_iva_line_ids.filtered(
                            lambda x: x.retention_id.state == "emitted"
                            and not self._check_future_retention_dates(
                                x.retention_id.date_accounting
                            )
                        )
                    )
                    * -1
                    for move in credit_notes
                ]
            )
        )

        return retention_resume_lines

    def _resume_sale_book_fields(self, moves):
        res_book = super()._resume_sale_book_fields(moves)
        res_book.extend(
            [
                {
                    "name": "Total Retenciones",
                    "format": "number",
                    "values": self._determinate_resume_retention_books(moves),
                }
            ]
        )

        return res_book

    def _resume_purchase_book_fields(self, moves):
        res_book = super()._resume_purchase_book_fields(moves)
        res_book.extend(
            [
                {
                    "name": "Total Retenciones",
                    "format": "number",
                    "values": self._determinate_resume_retention_books(moves),
                }
            ]
        )
        return res_book

    def sale_book_fields(self):
        fields = super().sale_book_fields()
        fields.extend(
            [
                {
                    "name": "Fecha Retención",
                    "field": "date_retention",
                    "size": 20,
                },
                {
                    "name": "N° Retención",
                    "field": "number_retention",
                    "size": 20,
                },
                {"name": "IVA retenido", "field": "iva_retained", "format": "number"},
            ]
        )
        return fields

    def purchase_book_fields(self):
        fields = super().purchase_book_fields()
        fields.extend(
            [
                {
                    "name": "Fecha Retención",
                    "field": "date_retention",
                    "size": 20,
                },
                {
                    "name": "N° Retención",
                    "field": "number_retention",
                    "size": 20,
                },
                {"name": "IVA retenido", "field": "iva_retained", "format": "number"},
            ]
        )
        return fields

    def _get_retention_domain(self):
        is_purchase = self.report == "purchase"
        field_date = "date_accounting"
        move_type = (
            ["out_invoice", "out_refund"] if not is_purchase else ["in_invoice", "in_refund"]
        )

        domain = [
            (field_date, ">=", self.date_from),
            (field_date, "<=", self.date_to),
            ("type", "in", move_type),
            ("type_retention", "=", "iva"),
            ("state", "=", "emitted"),
            ("company_id", "=", self.company_id.id),
        ]
        return domain

    def search_moves(self):
        # Rutina de self-healing para retenciones corruptas en base de datos (retention_amount = 0.0 y foreign_retention_amount > 0.0)
        corrupt_iva_lines = self.env["account.retention.iva.line"].search([
            ("retention_amount", "=", 0.0),
            ("foreign_retention_amount", ">", 0.0)
        ])
        for line in corrupt_iva_lines:
            rate = line.foreign_currency_rate or line.move_id.tax_today or line.move_id.company_id.currency_id_dif.inverse_rate or 1.0
            line.write({
                "retention_amount": line.foreign_retention_amount * rate
            })

        retention = self.env["account.retention"]
        res_moves = super().search_moves()

        domain = self._get_retention_domain()
        retention_ids = retention.search(domain)
        moves = retention_ids.mapped("retention_line_ids.move_id")
        res_moves |= moves

        return res_moves

    def parse_sale_book_data(self):
        data = super().parse_sale_book_data()
        for move in data:
            date = move.get("accounting_date", False)
            if move.get("vat", "") != "RESUMEN" and (
                not date
                or self._check_future_retention_dates(
                    datetime.strptime(move.get("accounting_date"), "%d/%m/%Y").date()
                )
            ):
                move.update(
                    {
                        "total_sales_iva": 0,
                        "total_sales_not_iva": 0,
                        "amount_reduced_aliquot": 0,
                        "amount_general_aliquot": 0,
                        "tax_base_reduced_aliquot": 0,
                        "tax_base_general_aliquot": 0,
                    }
                )
            retention_data = self.get_retention_iva_values(move.get("_id"))
            move.update(retention_data)

        return data

    def parse_purchase_book_data(self):
        data = super().parse_purchase_book_data()
        for move in data:
            move_date = datetime.strptime(move.get("accounting_date"), "%d/%m/%Y").date()
            if self._check_future_retention_dates(move_date):
                move.update(
                    {
                        "total_purchases_iva": 0,
                        "total_purchases_not_iva": 0,
                        "amount_reduced_aliquot": 0,
                        "amount_general_aliquot": 0,
                        "amount_extend_aliquot": 0,
                        "tax_base_reduced_aliquot": 0,
                        "tax_base_general_aliquot": 0,
                        "tax_base_extend_aliquot": 0,
                    }
                )
            retention_data = self.get_retention_iva_values(move.get("_id"))
            move.update(retention_data)

        return data

    def get_retention_iva_values(self, move_id):
        move = self.env["account.move"].browse(move_id)
        is_purchase = self.report == "purchase"
        multiplier = -1 if move.move_type in ["out_refund", "in_refund"] else 1
        ret_lines = (
            move.retention_iva_line_ids.filtered(lambda x: x.retention_id.state == "emitted")
            if move.state == "posted"
            else move.retention_iva_line_ids
        )
        retention = ret_lines.mapped("retention_id")
        ret_vals = {
                    "date_retention": "",
                    "number_retention": "",
                    "iva_retained": 0,
                }

        if not ret_lines:
            return ret_vals
        
        for ret_line in ret_lines:

            if ret_line and self._check_future_retention_dates(ret_line.retention_id.date_accounting):
                continue

            ret_vals["date_retention"] = self._format_date(ret_line.retention_id.date_accounting)
            ret_vals["number_retention"] = ret_line.retention_id.number or move.iva_voucher_number
            ret_vals["iva_retained"] = ret_vals["iva_retained"] + (
                self._sum_retention_total(ret_line) * multiplier
                if ret_line.move_id.state != "cancel"
                else 0
            )

        return ret_vals

    def _sum_retention_total(self, lines):
        total_local = 0.0
        total_foreign = 0.0

        for line in lines:
            retention = line.retention_id
            if (
                self.report == "purchase"
                and retention
                and self._check_future_retention_dates(retention.date_accounting)
                or line.move_id.state == "cancel"
            ):
                continue

            amount1 = abs(line.retention_amount)
            amount2 = abs(line.foreign_retention_amount)
            
            local_amt = max(amount1, amount2)
            foreign_amt = min(amount1, amount2)

            sign = -1.0 if (line.retention_amount < 0 or line.foreign_retention_amount < 0) else 1.0

            if foreign_amt == 0.0 and local_amt > 0.0:
                company = line.move_id.company_id
                local_curr = company.currency_id
                foreign_curr = company.currency_id_dif or self.env.company.currency_id_dif
                if foreign_curr and local_curr != foreign_curr:
                    foreign_amt = local_curr._convert(
                        local_amt, foreign_curr, company, line.move_id.invoice_date or fields.Date.today()
                    )
            elif local_amt == 0.0 and foreign_amt > 0.0:
                company = line.move_id.company_id
                local_curr = company.currency_id
                foreign_curr = company.currency_id_dif or self.env.company.currency_id_dif
                if foreign_curr and local_curr != foreign_curr:
                    local_amt = foreign_curr._convert(
                        foreign_amt, local_curr, company, line.move_id.invoice_date or fields.Date.today()
                    )

            total_local += local_amt * sign
            total_foreign += foreign_amt * sign

        if not self.currency_system:
            return total_foreign

        return total_local

    def _check_future_retention_dates(self, cmp_date):
        return cmp_date < self.date_from or cmp_date > self.date_to
