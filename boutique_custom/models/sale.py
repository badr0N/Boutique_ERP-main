# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_create_delivery_order(self):
        StockPicking = self.env['stock.picking']
        ProductProduct = self.env['product.product']

        for order in self:
            group = order.procurement_group_id
            if not group:
                group = self.env['procurement.group'].create({
                    'name': order.name,
                    'move_type': order.picking_policy,
                    'sale_id': order.id,
                    'partner_id': order.partner_shipping_id.id,
                })
                order.procurement_group_id = group

            move_vals = []
            for line in order.order_line:
                parent_product = line.product_id
                related_products = ProductProduct.search([
                    ('parent_product_id', '=', parent_product.id)
                ]) if parent_product else ProductProduct.search([
                    ('parent_product_id', '=', False)
                ])

                for product in related_products:
                    move_vals.append((0, 0, {
                        'name': product.name,
                        'product_id': product.id,
                        'product_uom': product.uom_id.id,
                        'product_uom_qty': 1.0,
                        'secondary_product_uom': product.secondary_product_uom_id.id,
                        'group_id': group.id,
                        'secondary_qty': 1.0,
                        'location_id': order.warehouse_id.out_type_id.default_location_src_id.id,
                        'location_dest_id': order.partner_id.property_stock_customer.id,
                        'sale_line_id': line.id,
                    }))

            picking = StockPicking.create({
                'partner_id': order.partner_id.id,
                'origin': order.name,
                'picking_type_id': order.warehouse_id.out_type_id.id,
                'move_ids_without_package': move_vals,
                'is_manual_create_picking': True,
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'target': 'current',
            'res_id': picking.id,
        }
    
class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    secondary_product_qty = fields.Float(string='Secondary Quantity', digits='Product Unit of Measure')
    secondary_product_uom_id = fields.Many2one("uom.uom", string="Secondary UoM")

    @api.onchange("product_id")
    def _onchange_product_secondary_uom(self):
        if self.product_id:
            self.secondary_product_uom_id = self.product_id.secondary_product_uom_id