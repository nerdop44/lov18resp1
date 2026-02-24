from odoo import api, fields, models

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Campo existente (mantener)
    ciu_id = fields.Many2one(
        "economic.activity", 
        string="CIU", 
         
        store=True, 
        readonly=False
    )

    # Nuevo campo para el parche de seguridad
    is_manually_modified = fields.Boolean(
        string="Modified Manually (Technical)",
        
        search="_search_dummy_modified",
        store=False,
        help="Technical field to prevent synchronization errors"
    )

#     @api.depends("product_id.ciu_ids")
#     def _compute_ciu_id(self):
#         """Método existente para CIU"""
#         for line in self:
#             if not line.product_id or line.ciu_id or not line.product_id.ciu_ids:
#                 continue
#             line.ciu_id = line.product_id.ciu_ids[0]
# 
#     def _compute_dummy_modified(self):
#         """Siempre retorna False para el campo técnico"""
#         for line in self:
#             line.is_manually_modified = False
# 
#     def _search_dummy_modified(self, operator, value):
#         """Nunca retorna resultados para búsquedas"""
#         return [('id', '=', False)]# from odoo import api, fields, models
# 
# 
# class AccountMoveLine(models.Model):
#     _inherit = "account.move.line"

#     ciu_id = fields.Many2one(
#         "economic.activity", string="CIU",  store=True, readonly=False
#     )

#     @api.depends("product_id.ciu_ids")
#     def _compute_ciu_id(self):
#         for line in self:
#             if not line.product_id or line.ciu_id or not line.product_id.ciu_ids:
#                 continue
#             line.ciu_id = line.product_id.ciu_ids[0]
