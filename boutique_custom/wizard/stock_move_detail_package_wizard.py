# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import format_date, frozendict


class StockMoveDetailPackageWizard(models.TransientModel):
    _name = 'stock.move.detail.package.wizard'
    _description = "Stock Move Detail Package Wizard"

    stock_move_id = fields.Many2one("stock.move", string="Stock Move", default=lambda self: self.env.context.get('active_id'))
    product_id = fields.Many2one("product.product", string="Product")
    quantity = fields.Float(string="Quantity", digits="Product Unit of Measure", compute='_compute_reserved')
    product_uom = fields.Many2one("uom.uom", string="Unit", required=True)
    secondary_qty = fields.Float(string="Secondary Quantity", digits="Product Unit of Measure", compute='_compute_reserved')
    secondary_product_uom = fields.Many2one("uom.uom", string="Secondary Unit", required=True)
    line_ids = fields.One2many(
        'stock.move.detail.package.wizard.line',
        'package_id',
        string="Details",
        help="Breakdown of the product into PCS, and yards.",
    )

    @api.model
    def default_get(self, fields):
        res = super(StockMoveDetailPackageWizard, self).default_get(fields)
        stock_move = self.env['stock.move'].browse(self.env.context.get('active_id'))
        stock_move_details = self.env['stock.move.detail.package'].search([('stock_move_id', '=', stock_move.id)])
        
        if len(stock_move_details) > 1:
            raise UserError(_('There should be only one stock move detail package per stock move.'))
        
        if stock_move_details:
            stock_move_detail = stock_move_details[0]
            res.update({
                'product_id': stock_move_detail.product_id.id,
                'product_uom': stock_move_detail.product_uom.id,
                'secondary_product_uom': stock_move_detail.secondary_product_uom.id,
                'quantity': stock_move_detail.quantity,
                'secondary_qty': stock_move_detail.secondary_qty,
                'line_ids': [(0, 0, {
                    'sequence': line.sequence,
                    'quantity': line.quantity,
                    'product_uom': line.product_uom.id,
                }) for line in stock_move_detail.line_ids]
            })
        else:
            res.update({
                'product_id': stock_move.product_id.id,
                'product_uom': stock_move.product_uom.id,
                'secondary_product_uom': stock_move.secondary_product_uom.id,
            })
        return res

    @api.depends('line_ids', 'line_ids.quantity')
    def _compute_reserved(self):
        for package in self:
            package.quantity = sum(line.quantity for line in package.line_ids)
            package.secondary_qty = len(package.line_ids)

    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        self.line_ids._compute_line_number()

    def action_confirm(self):
        for package in self:
            stock_move = package.stock_move_id
            stock_move.quantity = package.quantity
            stock_move.product_uom_qty = package.quantity
            stock_move.product_uom = package.product_uom
            stock_move.secondary_qty = package.secondary_qty
            stock_move.secondary_product_uom = package.secondary_product_uom
            existing_packages = self.env['stock.move.detail.package'].search([('stock_move_id', '=', stock_move.id)])
            
            if len(existing_packages) > 1:
                raise UserError(_('There should be only one stock move detail package per stock move.'))
            
            if existing_packages:
                # Update existing stock.move.detail.package record
                existing_package = existing_packages[0]
                existing_package.write({
                    'product_id': package.product_id.id,
                    'quantity': package.quantity,
                    'product_uom': package.product_uom.id,
                    'secondary_qty': package.secondary_qty,
                    'secondary_product_uom': package.secondary_product_uom.id,
                    'line_ids': [(5, 0, 0)] + [(0, 0, {
                        'sequence': line.sequence,
                        'quantity': line.quantity,
                        'product_uom': line.product_uom.id,
                    }) for line in package.line_ids]
                })
            else:
                # Create a new stock.move.detail.package record
                self.env['stock.move.detail.package'].create({
                    'stock_move_id': stock_move.id,
                    'product_id': package.product_id.id,
                    'quantity': package.quantity,
                    'product_uom': package.product_uom.id,
                    'secondary_qty': package.secondary_qty,
                    'secondary_product_uom': package.secondary_product_uom.id,
                    'line_ids': [(0, 0, {
                        'sequence': line.sequence,
                        'quantity': line.quantity,
                        'product_uom': line.product_uom.id,
                    }) for line in package.line_ids]
                })


class StockMoveDetailPackageWizardLine(models.TransientModel):
    _name = 'stock.move.detail.package.wizard.line'
    _description = "Stock Move Detail Package Wizard Line"

    package_id = fields.Many2one(
        'stock.move.detail.package.wizard',
        string="Package Reference",
        required=True,
        ondelete='cascade',
        help="Reference to the Stock Move Detail Package.",
    )
    sequence = fields.Integer(string='Sequence', default=10)
    quantity = fields.Float(string="Quantity", digits="Product Unit of Measure")
    product_uom = fields.Many2one("uom.uom", string="Unit", related="package_id.product_uom", required=True)
    line_number = fields.Integer(
        string='Line Number',
        compute='_compute_line_number',
    )
    
    @api.depends('package_id', 'sequence')
    def _compute_line_number(self):
        for line in self:
            if line.package_id:
                package_lines = line.package_id.line_ids.sorted(key=lambda l: l.sequence)
                
                for index, line in enumerate(package_lines, start=1):
                    line.line_number = index