# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class ProductTemplate(models.Model):
    _inherit = "product.template"

    parent_product_id = fields.Many2one("product.product", string="Parent Product")
    secondary_product_uom_id = fields.Many2one("uom.uom", string="Secondary Unit")
    col = fields.Char(string="COL")
