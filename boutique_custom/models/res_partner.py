# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class Partner(models.Model):
    _inherit = "res.partner"

    expedition_note = fields.Html(string='Expedition Note')