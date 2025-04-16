# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.addons.purchase_stock.models.stock_move import StockMove
from odoo.tools.float_utils import float_is_zero, float_round, float_compare

class StockPicking(models.Model):
    _inherit = "stock.picking"

    expedition_note = fields.Html(string='Expedition Note')
    manual_purchase_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Manual Purchase Order',
        help='Reference to the manually linked purchase order'
    )
    is_manual_create_picking = fields.Boolean(string="Manual Create Picking", default=False, copy=False)

    @api.onchange("partner_id")
    def _onchange_picking_partner_id(self):
        for transfer in self:
            transfer.expedition_note = transfer.partner_id.expedition_note

    def button_validate(self):
        StockMove = self.env['stock.move']
        sale_line_price_map = {}

        for picking in self:
            moves = StockMove.search([
                ('picking_id', '=', picking.id),
                ('sale_line_id', '!=', False),
            ])
            for move in moves:
                sale_line = move.sale_line_id
                if sale_line and sale_line.id not in sale_line_price_map:
                    sale_line_price_map[sale_line.id] = sale_line.price_unit

        res = super(StockPicking, self).button_validate()

        StockMove = self.env['stock.move']

        for picking in self:
            is_incoming = picking.picking_type_code == 'incoming'
            is_outgoing = picking.picking_type_code == 'outgoing'

            sale_line_ids = StockMove.search([
                ('picking_id', '=', picking.id),
                ('sale_line_id', '!=', False),
            ]).mapped('sale_line_id')

            for sale_line in sale_line_ids:
                done_moves = StockMove.search([
                    ('sale_line_id', '=', sale_line.id),
                    ('state', '=', 'done'),
                ])
                total_qty = sum([
                    move.product_uom_qty if move.picking_id.picking_type_code == 'outgoing' else -move.product_uom_qty
                    for move in done_moves
                ])
                original_price = sale_line_price_map.get(sale_line.id, sale_line.price_unit)
                sale_line.write({'product_uom_qty': total_qty, 'price_unit': original_price})

            purchase_line_ids = StockMove.search([
                ('picking_id', '=', picking.id),
                ('purchase_line_id', '!=', False),
            ]).mapped('purchase_line_id')

            for purchase_line in purchase_line_ids:
                done_moves = StockMove.search([
                    ('purchase_line_id', '=', purchase_line.id),
                    ('state', '=', 'done'),
                ])
                total_qty = sum([
                    move.product_uom_qty if move.picking_id.picking_type_code == 'incoming' else -move.product_uom_qty
                    for move in done_moves
                ])
                purchase_line.write({'product_qty': total_qty})

        return res

    @api.model
    def create(self, vals):
        if "expedition_note" not in vals:
            partner_id = vals.get("partner_id")
            if partner_id:
                partner = self.env["res.partner"].browse(partner_id)
                vals["expedition_note"] = partner.expedition_note
        res = super(StockPicking, self).create(vals)
        if self.env.context.get('force_manual_create_picking'):
            res['is_manual_create_picking'] = True
        if self.env.context.get('linked_sale_order_id'):
            res['sale_id'] = self.env.context['linked_sale_order_id']
        return res

    def write(self, vals):
        if "partner_id" in vals and "expedition_note" not in vals:
            partner = self.env["res.partner"].browse(vals["partner_id"])
            vals["expedition_note"] = partner.expedition_note
        return super(StockPicking, self).write(vals)

class StockMove(models.Model):
    _inherit = "stock.move"

    secondary_qty = fields.Float(string="Secondary Quantity", digits="Product Unit of Measure")
    secondary_product_uom = fields.Many2one("uom.uom", string="Secondary Unit")

    @api.onchange('purchase_line_id')
    def _onchange_purchase_line_id(self):
        for move in self:
            if move.purchase_line_id:
                move.sale_line_id = False
                move.price_unit = move.purchase_line_id.price_unit

    @api.onchange('sale_line_id')
    def _onchange_sale_line_id(self):
        for move in self:
            if move.sale_line_id:
                move.purchase_line_id = False

    def _should_ignore_pol_price(self):
        self.ensure_one()
        return (
            self.origin_returned_move_id
            or not self.purchase_line_id
            or not self.product_id
            or self.purchase_line_id.product_id != self.product_id
            or self.purchase_line_id.product_id.detailed_type == 'service'
        )
    
    def _get_price_unit(self):
        """ Returns the unit price for the move"""
        self.ensure_one()
        if self._should_ignore_pol_price():
            print(self._should_ignore_pol_price(),'self._should_ignore_pol_price()')
            return super(StockMove, self)._get_price_unit()
        price_unit_prec = self.env['decimal.precision'].precision_get('Product Price')
        line = self.purchase_line_id
        order = line.order_id
        received_qty = line.qty_received
        if self.state == 'done':
            received_qty -= self.product_uom._compute_quantity(self.quantity, line.product_uom, rounding_method='HALF-UP')
        if float_compare(line.qty_invoiced, received_qty, precision_rounding=line.product_uom.rounding) > 0:
            move_layer = line.move_ids.sudo().stock_valuation_layer_ids
            invoiced_layer = line.sudo().invoice_lines.stock_valuation_layer_ids
            # value on valuation layer is in company's currency, while value on invoice line is in order's currency
            receipt_value = 0
            if move_layer:
                receipt_value += sum(move_layer.mapped(lambda l: l.currency_id._convert(
                    l.value, order.currency_id, order.company_id, l.create_date, round=False)))
            if invoiced_layer:
                receipt_value += sum(invoiced_layer.mapped(lambda l: l.currency_id._convert(
                    l.value, order.currency_id, order.company_id, l.create_date, round=False)))
            invoiced_value = 0
            invoiced_qty = 0
            for invoice_line in line.sudo().invoice_lines:
                if invoice_line.tax_ids:
                    invoiced_value += invoice_line.tax_ids.with_context(round=False).compute_all(
                        invoice_line.price_unit, currency=invoice_line.currency_id, quantity=invoice_line.quantity)['total_void']
                else:
                    invoiced_value += invoice_line.price_unit * invoice_line.quantity
                invoiced_qty += invoice_line.product_uom_id._compute_quantity(invoice_line.quantity, line.product_id.uom_id)
            # TODO currency check
            remaining_value = invoiced_value - receipt_value
            # TODO qty_received in product uom
            remaining_qty = invoiced_qty - line.product_uom._compute_quantity(received_qty, line.product_id.uom_id)
            price_unit = float_round(remaining_value / remaining_qty, precision_digits=price_unit_prec)
        else:
            price_unit = self.price_unit if self.price_unit < 0 else line._get_gross_price_unit()
        if order.currency_id != order.company_id.currency_id:
            # The date must be today, and not the date of the move since the move move is still
            # in assigned state. However, the move date is the scheduled date until move is
            # done, then date of actual move processing. See:
            # https://github.com/odoo/odoo/blob/2f789b6863407e63f90b3a2d4cc3be09815f7002/addons/stock/models/stock_move.py#L36
            price_unit = order.currency_id._convert(
                price_unit, order.company_id.currency_id, order.company_id, fields.Date.context_today(self), round=False)
        return price_unit
    
    @api.constrains('product_id')
    def _change_product_id_secondary_uom(self):
        for move in self:
            if move.product_id and move.product_id.secondary_product_uom_id:
                move.secondary_product_uom = move.product_id.secondary_product_uom_id.id

    @api.onchange('product_id')
    def _onchange_product_id_secondary_uom(self):
        for move in self:
            if move.product_id and move.product_id.secondary_product_uom_id:
                move.secondary_product_uom = move.product_id.secondary_product_uom_id.id


class StockMoveDetailPackage(models.Model):
    _name = 'stock.move.detail.package'
    _description = "Stock Move Detail Package"

    stock_move_id = fields.Many2one("stock.move", string="Stock Move", ondelete='cascade', default=lambda self: self.env.context.get('active_id'))
    product_id = fields.Many2one("product.product", string="Product")
    quantity = fields.Float(string="Quantity", digits="Product Unit of Measure", compute='_compute_reserved')
    product_uom = fields.Many2one("uom.uom", string="Unit", required=True)
    secondary_qty = fields.Float(string="Secondary Quantity", digits="Product Unit of Measure", compute='_compute_reserved')
    secondary_product_uom = fields.Many2one("uom.uom", string="Secondary Unit", required=True)
    line_ids = fields.One2many(
        'stock.move.detail.package.line',
        'package_id',
        string="Details",
        help="Breakdown of the product into PCS, and yards.",
    )

    @api.model
    def default_get(self, fields):
        res = super(StockMoveDetailPackage, self).default_get(fields)
        stock_move = self.env['stock.move'].browse(self.env.context.get('active_id'))
        if stock_move:
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
            stock_move.product_uom = package.product_uom
            stock_move.secondary_qty = package.secondary_qty
            stock_move.secondary_product_uom = package.secondary_product_uom

class StockMoveDetailPackageLine(models.Model):
    _name = 'stock.move.detail.package.line'
    _description = "Stock Move Detail Package Line"

    package_id = fields.Many2one(
        'stock.move.detail.package',
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