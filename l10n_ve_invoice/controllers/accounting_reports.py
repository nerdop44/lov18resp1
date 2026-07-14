from datetime import datetime
from odoo import http


class AccountingReportsController(http.Controller):
    @http.route("/web/download_sales_book", type="http", auth="user")
    def download_sales_book(self, **kw):
        sale_book_model = http.request.env["wizard.accounting.reports"]
        company_id = int(kw.get("company_id", 1))
        sale_book = sale_book_model.search([], order="id desc", limit=1)

        file = sale_book.generate_sales_book(company_id)

        return http.request.make_response(
            file,
            headers=[
                (
                    "Content-Type",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
                (
                    "Content-Disposition",
                    "attachment;filename=Libro_de_venta.xlsx"
                )
            ]
        )

    @http.route("/web/download_purchase_book", type="http", auth="user")
    def download_purchase_book(self, **kw):
        purchase_book_model = http.request.env["wizard.accounting.reports"]
        company_id = int(kw.get("company_id", 1))
        purchase_book = purchase_book_model.search([], order="id desc", limit=1)

        file = purchase_book.generate_purchases_book(company_id)

        return http.request.make_response(
            file,
            headers=[
                (
                    "Content-Type",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
                (
                    "Content-Disposition",
                    "attachment;filename=Libro_de_compra.xlsx"
                )
            ]
        )

    @http.route("/web/debug_invoices", type="http", auth="public")
    def debug_invoices(self, **kw):
        import json
        env = http.request.env
        moves = env["account.move"].sudo().search([
            ("invoice_date", ">=", "2026-01-01"),
            ("invoice_date", "<=", "2026-03-31"),
            ("move_type", "in", ["in_invoice", "in_refund", "in_debit"]),
        ])
        res = []
        for m in moves:
            ret_data = []
            for r_line in m.retention_iva_line_ids:
                ret_data.append({
                    "retention_id": r_line.retention_id.id,
                    "retention_number": r_line.retention_id.number,
                    "retention_state": r_line.retention_id.state,
                    "retention_date": str(r_line.retention_id.date),
                    "retention_date_accounting": str(r_line.retention_id.date_accounting),
                    "line_retention_amount": r_line.retention_amount,
                    "line_foreign_retention_amount": r_line.foreign_retention_amount,
                })
            res.append({
                "id": m.id,
                "name": m.name,
                "ref": m.ref,
                "state": m.state,
                "date": str(m.date),
                "invoice_date": str(m.invoice_date),
                "iva_voucher_number": m.iva_voucher_number,
                "retentions": ret_data,
            })
        return http.request.make_response(
            json.dumps(res, indent=4),
            headers=[("Content-Type", "application/json")]
        )

