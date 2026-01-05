import requests
from datetime import datetime, timedelta
import pytz
from odoo import models, fields, api, SUPERUSER_ID
from odoo.exceptions import UserError
import random

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_integrated = fields.Boolean(string="Integrated", default=False, readonly=True, tracking=True)
    is_closed = fields.Boolean(string="Closed", default=False, readonly=True, tracking=True)
    vit_trxid = fields.Char(string="Transaction ID", default=False, tracking=True)
    target_location = fields.Many2one('stock.location', string="Target Location")
    stock_type = fields.Many2one('master.type', string="Stock Type")
    related_picking_id = fields.Many2one('stock.picking', string="Related Transfer", readonly=True, tracking=True)
    gm_type_transfer = fields.Selection([
        ('ts_out', 'TS Out'),
        ('ts_in', 'TS In'),
    ], string="Transfer Type", compute="_compute_gm_type_transfer", store=True, tracking=True)

    @api.depends('location_id', 'location_dest_id', 'location_id.usage', 'location_dest_id.usage')
    def _compute_gm_type_transfer(self):
        """
        Automatically determine transfer type based on Transit location:
        - If destination location usage is 'transit' -> TS Out
        - If source location usage is 'transit' -> TS In
        """
        for record in self:
            gm_type = False
            
            # Check if destination location usage is 'transit'
            if record.location_dest_id and record.location_dest_id.usage == 'transit':
                gm_type = 'ts_out'
            # Check if source location usage is 'transit'
            elif record.location_id and record.location_id.usage == 'transit':
                gm_type = 'ts_in'
            
            record.gm_type_transfer = gm_type

    # def write(self, vals):
    #     # Cek jika status sudah ready atau done dan mencoba mengubah field yang dibatasi
    #     restricted_states = ['assigned', 'done']  # ready = assigned, done = done
        
    #     for record in self:
    #         if record.state in restricted_states:
    #             # Field yang tidak boleh diubah ketika ready/done
    #             restricted_fields = ['target_location', 'stock_type', 'location_id', 'location_dest_id']
    #             for field in restricted_fields:
    #                 if field in vals:
    #                     raise UserError("Cannot modify field '%s' when transfer is in %s state." % (field, record.state))
                
    #             # Cek jika ada perubahan pada move lines (tambah/hapus item)
    #             if 'move_ids_without_package' in vals:
    #                 move_operations = vals.get('move_ids_without_package', [])
                    
    #                 for operation in move_operations:
    #                     # (0, 0, values) - CREATE new line
    #                     # (2, id, 0) - DELETE existing line
    #                     # (1, id, values) - UPDATE existing line (termasuk qty)
    #                     if operation[0] in (0, 2, 1):
    #                         if operation[0] == 0:
    #                             action = "add new items"
    #                         elif operation[0] == 2:
    #                             action = "delete items" 
    #                         else:
    #                             action = "modify items or quantities"
                            
    #                         raise UserError("Cannot %s when transfer is in %s state." % (action, record.state))
        
    #     return super(StockPicking, self).write(vals)

    def button_validate(self):
        # Check if the operation type is 'Internal Transfers'
        if self.picking_type_id.code == 'internal':
            # Check if the source and destination locations are the same
            if self.location_id.id == self.location_dest_id.id:
                raise UserError("Cannot validate this operation: Source and destination locations are the same.")
        
        # 🔥 NEW: Auto create TS In when validating TS Out
        ts_out_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('name', 'ilike', 'TS Out')
        ], limit=1)
        
        if self.picking_type_id.id == ts_out_type.id and self.target_location:
            # Validate TS Out first
            res = super(StockPicking, self).button_validate()
            
            # Create TS In after validation
            self._create_ts_in_transfer()
            
            return res
        
        # Call the super method for other cases
        res = super(StockPicking, self).button_validate()
        return res

    def _create_ts_in_transfer(self):
        """
        Create TS In transfer automatically from TS Out
        location_id = TR/Stock (from TS Out location_dest_id)
        location_dest_id = target_location (from TS Out)
        """
        self.ensure_one()
        
        # Find TS In operation type
        ts_in_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('name', 'ilike', 'TS In'),
            ('warehouse_id', '=', self.picking_type_id.warehouse_id.id)
        ], limit=1)
        
        if not ts_in_type:
            raise UserError("TS In operation type not found for this warehouse.")
        
        # Prepare picking values
        picking_vals = {
            'picking_type_id': ts_in_type.id,
            'location_id': self.location_dest_id.id,  # TR/Stock from TS Out
            'location_dest_id': self.target_location.id,  # S02/Stock from target_location
            'origin': self.name,  # Reference to TS Out document
            'scheduled_date': fields.Datetime.now(),
            'stock_type': self.stock_type.id if self.stock_type else False,
            'target_location': False,  # TS In doesn't need target_location
            'related_picking_id': self.id,  # Link back to TS Out
        }
        
        # Create new picking
        new_picking = self.env['stock.picking'].create(picking_vals)
        
        # Create move lines based on TS Out moves
        for move in self.move_ids_without_package:
            move_vals = {
                'name': move.product_id.name,
                'product_id': move.product_id.id,
                'product_uom_qty': move.product_uom_qty,
                'product_uom': move.product_uom.id,
                'picking_id': new_picking.id,
                'location_id': new_picking.location_id.id,
                'location_dest_id': new_picking.location_dest_id.id,
                'vit_line_number_sap': move.vit_line_number_sap,
            }
            self.env['stock.move'].create(move_vals)
        
        # Confirm the picking to make it ready
        new_picking.action_confirm()
        new_picking.action_assign()
        
        # Store reference to TS In in TS Out
        self.related_picking_id = new_picking.id
        
        # Show notification message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'TS In Created',
                'message': f'TS In document {new_picking.name} has been created automatically.',
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'stock.picking',
                    'res_id': new_picking.id,
                    'views': [[False, 'form']],
                }
            }
        }

class StockMove(models.Model):
    _inherit = 'stock.move'

    vit_line_number_sap = fields.Integer(string='Line Number SAP')

    # def write(self, vals):
    #     # Cek jika picking terkait sudah ready atau done
    #     for record in self:
    #         if record.picking_id and record.picking_id.state in ['assigned', 'done']:
    #             raise UserError("Cannot modify stock moves when transfer is in %s state." % record.picking_id.state)
        
    #     return super(StockMove, self).write(vals)
    
    # def unlink(self):
    #     # Cek jika picking terkait sudah ready atau done
    #     for record in self:
    #         if record.picking_id and record.picking_id.state in ['assigned', 'done']:
    #             raise UserError("Cannot delete stock moves when transfer is in %s state." % record.picking_id.state)
        
    #     return super(StockMove, self).unlink()