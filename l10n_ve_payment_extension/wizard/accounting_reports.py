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
        retention = self.env["account.retention"]
        res_moves = super().search_moves()

        domain = self._get_retention_domain()
        retention_ids = retention.search(domain)
        
        # Self-healing routine: Automatically detect and repair historical zero values
        zero_lines = retention_ids.mapped("retention_line_ids").filtered(
            lambda l: l.retention_amount == 0.0 and l.foreign_retention_amount > 0.0
        )
        if zero_lines:
            _logger.warning("Self-healing: Found %s IVA retention lines with zero retention_amount. Repairing...", len(zero_lines))
            for line in zero_lines:
                company_currency = line.company_id.currency_id
                company_currency_is_vef = (
                    company_currency.name in ("VES", "VEF", "Bs.", "Bs.S", "Bs.D", "Bs.F")
                    or company_currency.symbol in ("Bs.", "Bs.S", "Bs.D", "Bs.F")
                )
                if company_currency_is_vef:
                    line.write({"retention_amount": line.foreign_retention_amount})
                else:
                    rate = line.foreign_currency_rate or 1.0
                    line.write({"retention_amount": line.foreign_retention_amount / rate if rate else 0.0})

        moves = retention_ids.mapped("retention_line_ids.move_id")
        res_moves |= moves

        return res_moves

    def parse_sale_book_data(self):
        data = super().parse_sale_book_data()
        for move_line in data:
            move_id = move_line.get("_id")
            retention_data = self.get_retention_iva_values(move_id)
            move_line.update(retention_data)
            
            # LOG DE TRAZABILIDAD DE RETENCIONES
            if retention_data.get("iva_retained", 0) != 0:
                _logger.warning("V70 [Retención Venta] Move ID: %s | Retención: %s | Comprobante: %s", 
                                move_id, retention_data["iva_retained"], retention_data["number_retention"])
        return data

    def parse_purchase_book_data(self):
        data = super().parse_purchase_book_data()
        for move_line in data:
            move_id = move_line.get("_id")
            retention_data = self.get_retention_iva_values(move_id)
            move_line.update(retention_data)
            
            # LOG DE TRAZABILIDAD DE RETENCIONES
            if retention_data.get("iva_retained", 0) != 0:
                _logger.warning("V70 [Retención Compra] Move ID: %s | Retención: %s | Comprobante: %s", 
                                move_id, retention_data["iva_retained"], retention_data["number_retention"])
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
        
        ret_vals = {
            "date_retention": "",
            "number_retention": "",
            "iva_retained": 0,
        }

        if not ret_lines:
            return ret_vals
        
        # Tomamos datos del primer comprobante válido encontrado
        main_ret = ret_lines[0].retention_id
        ret_vals["date_retention"] = self._format_date(main_ret.date_accounting)
        ret_vals["number_retention"] = move.iva_voucher_number or main_ret.number

        total_retained = 0
        for ret_line in ret_lines:
            ret_date = ret_line.retention_id.date_accounting
            if ret_line and self._check_future_retention_dates(ret_date):
                continue
            
            total_retained += self._sum_retention_total(ret_line)

        ret_vals["iva_retained"] = total_retained * multiplier if move.state != "cancel" else 0

        return ret_vals

    def _sum_retention_total(self, lines):
        is_check_currency_system = self.currency_system
        retention = lines.mapped("retention_id")
        is_purchase = self.report == "purchase"
        ret_date = retention.date_accounting

        if (
            retention
            and self._check_future_retention_dates(ret_date)
            or lines.move_id.state == "cancel"
        ):
            return 0.0

        company_currency = self.env.company.currency_id
        company_currency_is_vef = (
            company_currency.name in ("VES", "VEF", "Bs.", "Bs.S", "Bs.D", "Bs.F")
            or company_currency.symbol in ("Bs.", "Bs.S", "Bs.D", "Bs.F")
        )
        retention_amount = sum(lines.mapped("retention_amount"))
        foreign_retention_amount = sum(lines.mapped("foreign_retention_amount"))
        
        # 1. Obtain native exchange rate from Odoo database using _convert API
        move = lines[0].move_id
        invoice_currency = move.currency_id
        
        rate = 1.0
        if invoice_currency != company_currency:
            try:
                rate = invoice_currency._convert(
                    1.0,
                    company_currency,
                    move.company_id,
                    move.invoice_date or move.date or fields.Date.today()
                )
            except Exception:
                rate = move.tax_today or lines[0].foreign_currency_rate or move.foreign_rate or 1.0
        else:
            rate = 1.0
            
        if rate <= 0.0:
            rate = 1.0

        # 2. Magnitude-based classification and self-healing
        if abs(foreign_retention_amount - retention_amount) < 0.01:
            # If both fields are identical (corrupted USD-USD)
            if company_currency_is_vef:
                ves_val = retention_amount * rate if rate > 1.0 else retention_amount
                usd_val = retention_amount
            else:
                ves_val = retention_amount
                usd_val = retention_amount / rate if rate > 1.0 else retention_amount
        else:
            # Classification based on physical magnitude
            ves_val = max(retention_amount, foreign_retention_amount)
            usd_val = min(retention_amount, foreign_retention_amount)

        # 3. Reactively return according to requested currency
        if company_currency_is_vef:
            return ves_val if is_check_currency_system else usd_val
        else:
            return usd_val if is_check_currency_system else ves_val

    def _check_future_retention_dates(self, cmp_date):
        return cmp_date < self.date_from or cmp_date > self.date_to
