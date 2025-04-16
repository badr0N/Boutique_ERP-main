# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def action_create_receipt(self):
        ProductProduct = self.env['product.product']
        StockPicking = self.env['stock.picking']

        for order in self:
            if not order.group_id:
                group = self.env['procurement.group'].create({
                    'name': order.name,
                    'partner_id': order.partner_id.id,
                })
                order.group_id = group
            else:
                group = order.group_id

            move_lines = []
            for line in order.order_line:
                parent_product = line.product_id
                related_products = ProductProduct.search([
                    ('parent_product_id', '=', parent_product.id)
                ]) if parent_product else ProductProduct.search([
                    ('parent_product_id', '=', False)
                ])

                for product in related_products:
                    move_lines.append((0, 0, {
                        'name': product.name,
                        'product_id': product.id,
                        'product_uom': product.uom_id.id,
                        'product_uom_qty': 1.0,
                        'group_id': group.id,
                        'price_unit': line.price_unit,
                        'secondary_product_uom': product.secondary_product_uom_id.id,
                        'secondary_qty': 1.0,
                        'purchase_line_id': line.id,
                        'location_id': order.partner_id.property_stock_supplier.id,
                        'location_dest_id': order.picking_type_id.default_location_dest_id.id,
                    }))
            print(order.picking_type_id.default_location_src_id,'order.picking_type_id.default_location_src_id')

            picking = StockPicking.create({
                'partner_id': order.partner_id.id,
                'origin': order.name,
                'picking_type_id': order.picking_type_id.id,
                'manual_purchase_id': order.id,
                'move_ids_without_package': move_lines,
                'is_manual_create_picking': True,
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'target': 'current',
            'res_id': picking.id,
        }

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    secondary_product_qty = fields.Float(string='Secondary Quantity', digits='Product Unit of Measure')
    secondary_product_uom_id = fields.Many2one("uom.uom", string="Secondary UoM")

    @api.onchange("product_id")
    def _onchange_product_secondary_uom(self):
        if self.product_id:
            self.secondary_product_uom_id = self.product_id.secondary_product_uom_id

    @api.depends('name', 'order_id', 'product_id', 'partner_id')
    def _compute_display_name(self):
        for line in self:
            parts = []
            if line.order_id:
                parts.append(line.order_id.name)
            if line.product_id:
                parts.append(line.product_id.display_name)
            if line.partner_id:
                parts.append('(%s)' % line.partner_id.name)

            line.display_name = ' - '.join(parts)