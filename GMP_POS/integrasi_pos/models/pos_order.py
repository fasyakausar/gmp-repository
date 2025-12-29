import requests
from datetime import datetime, timedelta
import pytz
from odoo import models, fields, api, SUPERUSER_ID, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_repr
import random

import logging
_logger = logging.getLogger(__name__)

class POSIntegration(models.Model):
    _inherit = 'pos.order'

    vit_trxid = fields.Char(string='Transaction ID', tracking=True)
    is_integrated = fields.Boolean(string="Integrated", default=False, readonly=True, tracking=True)
    id_mc = fields.Char(string="ID MC", tracking=True)
    vit_pos_store = fields.Char(
        string='POS Store Location',
        readonly=True,
        help='Location source from delivery picking (complete name)'
    )

    is_printed = fields.Boolean(string="Printed", default=False, readonly=True, tracking=True)

    def _create_order_picking(self):
        """
        Override method untuk menambahkan logic save location_id ke vit_pos_store
        """
        # Call parent method dulu untuk create picking
        result = super(POSIntegration, self)._create_order_picking()
        
        # Setelah picking dibuat, ambil location_id dan simpan ke vit_pos_store
        self._save_location_to_vit_pos_store()
        
        return result

    def _save_location_to_vit_pos_store(self):
        """
        Method untuk menyimpan location source dari picking ke field vit_pos_store
        """
        for order in self:
            if not order.picking_ids:
                _logger.warning(
                    f"⚠️ Order {order.name} tidak memiliki picking, "
                    f"vit_pos_store tidak diisi"
                )
                continue
            
            # Filter picking dengan tipe outgoing
            outgoing_pickings = order.picking_ids.filtered(
                lambda p: p.picking_type_id.code == 'outgoing'
            )
            
            # Jika tidak ada outgoing, ambil semua picking
            pickings_to_process = outgoing_pickings if outgoing_pickings else order.picking_ids
            
            if pickings_to_process:
                # Ambil picking pertama
                first_picking = pickings_to_process[0]
                
                # Ambil complete_name dari location source
                if first_picking.location_id:
                    location_complete_name = first_picking.location_id.complete_name
                    
                    # Update vit_pos_store
                    order.vit_pos_store = location_complete_name
                    
                    _logger.info(
                        f"✅ Order {order.name}: vit_pos_store set to "
                        f"'{location_complete_name}' from picking {first_picking.name}"
                    )
                else:
                    _logger.warning(
                        f"⚠️ Picking {first_picking.name} tidak memiliki location_id"
                    )
            else:
                _logger.warning(
                    f"⚠️ Order {order.name} tidak memiliki picking untuk diproses"
                )

    def _process_saved_order(self, draft):
        """
        Override untuk memastikan vit_pos_store terisi setelah order diproses
        """
        order_id = super(POSIntegration, self)._process_saved_order(draft)
        
        # Pastikan location sudah tersimpan setelah picking dibuat
        if not draft and self.picking_ids and not self.vit_pos_store:
            self._save_location_to_vit_pos_store()
        
        return order_id

    @api.model
    def _get_invoice_lines_values(self, line_values, pos_order_line):
        """Override untuk menambahkan user_id ke invoice lines"""
        res = super()._get_invoice_lines_values(line_values, pos_order_line)
        
        # Tambahkan user_id dari pos order line ke invoice line
        if pos_order_line.user_id:
            res['user_id'] = pos_order_line.user_id.id
        
        return res
    
    def _prepare_invoice_lines(self):
        """Override lengkap untuk memastikan user_id terkirim ke invoice lines"""
        sign = 1 if self.amount_total >= 0 else -1
        line_values_list = self._prepare_tax_base_line_values(sign=sign)
        invoice_lines = []
        
        for line_values in line_values_list:
            line = line_values['record']
            invoice_lines_values = self._get_invoice_lines_values(line_values, line)
            
            # Pastikan user_id dari orderline terkirim
            if hasattr(line, 'user_id') and line.user_id:
                invoice_lines_values['user_id'] = line.user_id.id
            
            invoice_lines.append((0, None, invoice_lines_values))
            
            # Tambahkan note untuk price discount jika ada
            if line.order_id.pricelist_id.discount_policy == 'without_discount' and float_compare(
                line.price_unit, 
                line.product_id.lst_price, 
                precision_rounding=self.currency_id.rounding
            ) < 0:
                invoice_lines.append((0, None, {
                    'name': _('Price discount from %s -> %s',
                              float_repr(line.product_id.lst_price, self.currency_id.decimal_places),
                              float_repr(line.price_unit, self.currency_id.decimal_places)),
                    'display_type': 'line_note',
                }))
            
            # Tambahkan customer note jika ada
            if line.customer_note:
                invoice_lines.append((0, None, {
                    'name': line.customer_note,
                    'display_type': 'line_note',
                }))

        return invoice_lines