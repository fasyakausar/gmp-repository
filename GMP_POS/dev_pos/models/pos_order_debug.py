# -*- coding: utf-8 -*-

from odoo import models, api
import logging
import json

_logger = logging.getLogger(__name__)

class PosOrderDebug(models.Model):
    _inherit = 'pos.order'

    @api.model
    def create_from_ui(self, orders, draft=False):
        """Debug: Log semua yang terjadi di create_from_ui"""
        _logger.info("="*80)
        _logger.info("🔍🔍🔍 [DEBUG] create_from_ui CALLED")
        _logger.info("🔍 [DEBUG] Input orders type: %s", type(orders))
        _logger.info("🔍 [DEBUG] Input orders value: %s", orders)
        _logger.info("🔍 [DEBUG] Draft parameter: %s", draft)
        
        # ============================================================
        # EXTENSIVE VALIDATION
        # ============================================================
        if orders is False:
            _logger.error("❌❌❌ [DEBUG CRITICAL] Orders is FALSE! Frontend sent wrong data.")
            _logger.error("❌❌❌ [DEBUG CRITICAL] This will cause TypeError in parent method.")
            return []
        
        if orders is None:
            _logger.warning("⚠️ [DEBUG] Orders is None, converting to empty list")
            orders = []
        
        if not isinstance(orders, (list, tuple)):
            _logger.error("❌ [DEBUG] Orders is not list/tuple! Type: %s", type(orders))
            if isinstance(orders, dict):
                _logger.warning("⚠️ [DEBUG] Orders is dict, converting to list with single element")
                orders = [orders]
            else:
                _logger.error("❌ [DEBUG] Cannot convert, returning empty list")
                return []
        
        _logger.info("🔍 [DEBUG] Validated orders count: %s", len(orders))
        
        # ============================================================
        # CALL PARENT
        # ============================================================
        try:
            _logger.info("🔍 [DEBUG] Calling parent create_from_ui...")
            result = super(PosOrderDebug, self).create_from_ui(orders, draft)
            _logger.info("🔍 [DEBUG] Parent returned successfully")
        except Exception as e:
            _logger.error("❌❌❌ [DEBUG] ERROR in parent create_from_ui: %s", str(e))
            _logger.error("❌❌❌ [DEBUG] Full traceback:", exc_info=True)
            return [{'success': False, 'error': str(e), 'debug': True}]
        
        # ============================================================
        # PROCESS RESULT
        # ============================================================
        _logger.info("🔍 [DEBUG] Result type: %s", type(result))
        _logger.info("🔍 [DEBUG] Result value: %s", result)
        
        if not isinstance(result, list):
            _logger.error("❌ [DEBUG] Result is not list! Type: %s", type(result))
            if isinstance(result, dict):
                _logger.warning("⚠️ [DEBUG] Converting dict to list")
                result = [result]
            else:
                _logger.error("❌ [DEBUG] Cannot process result")
                return []
        
        _logger.info("🔍 [DEBUG] Number of results: %s", len(result))
        
        for i, res in enumerate(result):
            _logger.info("🔍 [DEBUG] Processing result[%s]: %s (type: %s)", i, res, type(res))
            
            order_id = None
            
            # Extract order_id
            if isinstance(res, dict):
                if 'id' in res:
                    order_id = res['id']
                    _logger.info("🔍 [DEBUG]   Found order_id in 'id': %s", order_id)
                elif 'order_id' in res:
                    order_id = res['order_id']
                    _logger.info("🔍 [DEBUG]   Found order_id in 'order_id': %s", order_id)
                elif 'pos_order_id' in res:
                    order_id = res['pos_order_id']
                    _logger.info("🔍 [DEBUG]   Found order_id in 'pos_order_id': %s", order_id)
            elif isinstance(res, int):
                order_id = res
                result[i] = {'id': order_id}
                res = result[i]
                _logger.info("🔍 [DEBUG]   Converted int to dict: %s", order_id)
            
            if not order_id:
                _logger.warning("⚠️ [DEBUG]   No order_id found in result[%s]", i)
                if isinstance(res, dict):
                    res['gift_card_code'] = ''
                continue
            
            # Fetch order and add gift_card_code
            try:
                order_obj = self.browse(order_id)
                if not order_obj.exists():
                    _logger.error("❌ [DEBUG] Order %s does not exist in database", order_id)
                    res['gift_card_code'] = ''
                    continue
                
                # Get gift_card_code from database
                self.env.cr.execute(
                    "SELECT gift_card_code FROM pos_order WHERE id = %s",
                    (order_id,)
                )
                db_result = self.env.cr.fetchone()
                gift_card_code = db_result[0] if db_result and db_result[0] else ''
                
                if not gift_card_code and order_obj.gift_card_code:
                    gift_card_code = order_obj.gift_card_code
                
                # Add to result
                res['gift_card_code'] = gift_card_code
                
                if gift_card_code:
                    _logger.info("✅ [DEBUG] Added gift_card_code to result[%s]: %s", i, gift_card_code)
                else:
                    _logger.info("⚠️ [DEBUG] No gift_card_code for order %s", order_id)
                    
            except Exception as e:
                _logger.error("❌ [DEBUG] Error processing order %s: %s", order_id, str(e))
                if isinstance(res, dict):
                    res['gift_card_code'] = ''
        
        _logger.info("="*80)
        _logger.info("🔍🔍🔍 [DEBUG] create_from_ui COMPLETED")
        _logger.info("="*80)
        
        return result

    def _process_order(self, order, draft, existing_order):
        """Debug: Log _process_order"""
        _logger.info("="*80)
        _logger.info("🔍🔍🔍 [DEBUG] _process_order CALLED")
        _logger.info("🔍 [DEBUG] Order parameter type: %s", type(order))
        
        if isinstance(order, dict):
            _logger.info("🔍 [DEBUG] Order dict keys: %s", order.keys())
            if 'data' in order:
                data = order['data']
                _logger.info("🔍 [DEBUG] Order data keys: %s", data.keys() if isinstance(data, dict) else 'Not dict')
                if isinstance(data, dict):
                    _logger.info("🔍 [DEBUG] Order name: %s", data.get('name', 'Unknown'))
        else:
            _logger.info("🔍 [DEBUG] Order is not dict: %s", order)
        
        _logger.info("🔍 [DEBUG] Draft: %s", draft)
        _logger.info("🔍 [DEBUG] Existing order: %s", existing_order)
        
        try:
            # Call parent
            order_id = super(PosOrderDebug, self)._process_order(order, draft, existing_order)
            _logger.info("🔍 [DEBUG] Parent returned order_id: %s (type: %s)", order_id, type(order_id))
        except Exception as e:
            _logger.error("❌❌❌ [DEBUG] ERROR in _process_order: %s", str(e))
            _logger.error("❌❌❌ [DEBUG] Full traceback:", exc_info=True)
            raise
        
        if order_id:
            try:
                order_record = self.browse(order_id)
                _logger.info("🔍 [DEBUG] Created order record: %s", order_record.name)
                
                # Check gift_card_code
                order_record._invalidate_cache(['gift_card_code'])
                _logger.info("🔍 [DEBUG] Order gift_card_code: %s", order_record.gift_card_code)
                
                # Check if there are gift card lines
                gift_card_lines = order_record.lines.filtered(
                    lambda l: l.reward_id and l.reward_id.program_id.program_type == 'gift_card'
                )
                _logger.info("🔍 [DEBUG] Gift card lines count: %s", len(gift_card_lines))
                
            except Exception as e:
                _logger.error("❌ [DEBUG] Error fetching order: %s", e)
        
        _logger.info("="*80)
        _logger.info("🔍🔍🔍 [DEBUG] _process_order COMPLETED")
        _logger.info("="*80)
        
        return order_id

    def _export_for_ui(self, order):
        """Debug: Log _export_for_ui"""
        _logger.info("🔍 [DEBUG] _export_for_ui called for order: %s", order.name if order else 'None')
        
        if order:
            _logger.info("🔍 [DEBUG] Order ID: %s", order.id)
            _logger.info("🔍 [DEBUG] Order amount: %s", order.amount_total)
        
        result = super(PosOrderDebug, self)._export_for_ui(order)
        
        if order:
            # Add gift_card_code
            result['gift_card_code'] = order.gift_card_code or ''
            _logger.info("🔍 [DEBUG] Added gift_card_code to export: %s", result['gift_card_code'])
        else:
            result['gift_card_code'] = ''
            _logger.warning("⚠️ [DEBUG] Order is None in _export_for_ui")
        
        return result