# -*- coding: utf-8 -*-

from collections import defaultdict
from odoo import models, fields, api, _
from odoo.tools import float_compare
import logging
import json
import base64

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = 'pos.order'

    # Fields existing
    vit_trxid = fields.Char(string='Transaction ID', tracking=True)
    vit_id = fields.Char(string='Document ID', tracking=True)
    is_integrated = fields.Boolean(string="Integrated", default=False, readonly=True, tracking=True)
    vit_pos_store = fields.Char(
        string='POS Store Location',
        readonly=True,
        help='Location source from delivery picking (complete name)'
    )
    
    # New field for gift card code
    gift_card_code = fields.Char(
        string='Gift Card Code',
        copy=False,
        readonly=True,
        help='Gift Card code generated for DP order'
    )

    # ------------------------------------------------------------
    # MAIN FIX: confirm_coupon_programs dengan gift_card_code save
    # ------------------------------------------------------------
    def confirm_coupon_programs(self, coupon_data):
        """
        This is called after the order is created.
        This will create all necessary coupons and link them to their line orders etc..
        It will also return the points of all concerned coupons to be updated in the cache.
        """
        _logger.info("="*80)
        _logger.info("🎁 START confirm_coupon_programs - ORDER: %s", self.name)
        _logger.info("🎁 Order ID: %s, Amount Paid: %s", self.id, self.amount_paid)
        _logger.info("🎁 Coupon Data keys: %s", coupon_data.keys() if coupon_data else 'No data')
        
        if coupon_data:
            _logger.info("🎁 Coupon Data sample (first 2): %s", dict(list(coupon_data.items())[:2]))
        
        # Helper function for partner
        def get_partner_id(partner_id):
            return partner_id and self.env['res.partner'].browse(partner_id).exists() and partner_id or False
        
        # Convert keys to int
        coupon_data = {int(k): v for k, v in coupon_data.items()} if coupon_data else {}
        
        # Check existing loyalty cards
        self._check_existing_loyalty_cards(coupon_data)
        
        # Map coupon IDs
        coupon_new_id_map = {k: k for k in coupon_data.keys() if k > 0}
        
        # Create coupons that were awarded by the order
        coupons_to_create = {k: v for k, v in coupon_data.items() if k < 0 and not v.get('giftCardId')}
        
        _logger.info("🎁 Coupons to create count: %s", len(coupons_to_create))
        if coupons_to_create:
            _logger.info("🎁 Coupons to create details: %s", coupons_to_create)
        
        # ------------------------------------------------------------
        # CALCULATE GIFT CARD AMOUNTS
        # ------------------------------------------------------------
        gift_card_lines = self.lines.filtered(
            lambda l: l.reward_id and l.reward_id.program_id.program_type == 'gift_card'
        )
        
        _logger.info("🎁 Gift card lines found: %s", len(gift_card_lines))
        for idx, line in enumerate(gift_card_lines):
            _logger.info("🎁   Line %s: %s (qty: %s, price: %s, total: %s)", 
                       idx+1, line.product_id.name, line.qty, line.price_unit, 
                       line.price_unit * line.qty)
        
        # Calculate total gift card amount
        total_gift_card_amount = 0
        gift_card_program_amounts = {}
        
        if gift_card_lines and coupons_to_create:
            for line in gift_card_lines:
                program_id = line.reward_id.program_id.id
                amount = abs(line.price_unit * line.qty)
                
                if program_id in gift_card_program_amounts:
                    gift_card_program_amounts[program_id] += amount
                else:
                    gift_card_program_amounts[program_id] = amount
                
                total_gift_card_amount += amount
        
        _logger.info("🎁 Total gift card amount: %s", total_gift_card_amount)
        _logger.info("🎁 Gift card program amounts: %s", gift_card_program_amounts)
        
        # Count gift cards per program
        program_gift_card_count = {}
        for key, p in coupons_to_create.items():
            program_id = p.get('program_id')
            if program_id:
                if program_id in program_gift_card_count:
                    program_gift_card_count[program_id] += 1
                else:
                    program_gift_card_count[program_id] = 1
        
        _logger.info("🎁 Gift card count per program: %s", program_gift_card_count)
        
        # ------------------------------------------------------------
        # CREATE COUPON VALUES
        # ------------------------------------------------------------
        coupon_create_vals = []
        for key, p in coupons_to_create.items():
            points = 0
            program_id = p.get('program_id')
            
            # Calculate points for gift cards
            if program_id:
                program = self.env['loyalty.program'].browse(program_id)
                if program.program_type == 'gift_card':
                    program_amount = gift_card_program_amounts.get(program_id, 0)
                    count = program_gift_card_count.get(program_id, 1)
                    
                    if program_amount > 0 and count > 0:
                        points = program_amount / count
                    
                    if points == 0:
                        if len(coupons_to_create) == 1:
                            points = self.amount_paid
                        else:
                            points = total_gift_card_amount / len(coupons_to_create) if coupons_to_create else 0
                    
                    points = round(points, 2)
                    
                    _logger.info("🎁 Setting gift card points - Program: %s, Points: %s, Count: %s", 
                               program.name, points, count)
            
            coupon_create_vals.append({
                'program_id': program_id,
                'partner_id': get_partner_id(p.get('partner_id', False)),
                'code': p.get('barcode') or self.env['loyalty.card']._generate_code(),
                'points': points,
                'expiration_date': p.get('date_to', False),
                'source_pos_order_id': self.id,
            })
        
        _logger.info("🎁 Coupon create vals count: %s", len(coupon_create_vals))
        
        # ------------------------------------------------------------
        # CREATE COUPONS
        # ------------------------------------------------------------
        new_coupons = self.env['loyalty.card'].with_context(action_no_send_mail=True).sudo().create(coupon_create_vals)
        
        _logger.info("🎁 New coupons created: %s", len(new_coupons))
        for coupon in new_coupons:
            _logger.info("🎁   Coupon ID: %s, Code: %s, Points: %s", 
                       coupon.id, coupon.code, coupon.points)
        
        # ------------------------------------------------------------
        # ⭐⭐⭐ CRITICAL FIX: SAVE GIFT CARD CODE IMMEDIATELY ⭐⭐⭐
        # ------------------------------------------------------------
        gift_card_codes = []
        for coupon in new_coupons:
            if coupon.program_id.program_type == 'gift_card':
                gift_card_codes.append(coupon.code)
        
        if gift_card_codes:
            gift_card_code_str = ', '.join(gift_card_codes)
            
            # METHOD 1: Direct SQL (guaranteed)
            self.env.cr.execute(
                "UPDATE pos_order SET gift_card_code = %s WHERE id = %s",
                (gift_card_code_str, self.id)
            )
            
            # METHOD 2: Force commit
            self.env.cr.commit()
            
            # METHOD 3: Update cache
            self._invalidate_cache(['gift_card_code'], [self.id])
            
            # METHOD 4: Write to object
            self.write({'gift_card_code': gift_card_code_str})
            
            _logger.info("✅✅✅ [GIFT CARD SAVED] Code saved to order %s: %s", 
                       self.name, gift_card_code_str)
        else:
            _logger.warning("⚠️ No gift card codes to save")
        
        # ------------------------------------------------------------
        # UPDATE EXISTING GIFT CARDS
        # ------------------------------------------------------------
        gift_cards_to_update = [v for v in coupon_data.values() if v.get('giftCardId')]
        updated_gift_cards = self.env['loyalty.card']
        
        for coupon_vals in gift_cards_to_update:
            gift_card = self.env['loyalty.card'].browse(coupon_vals.get('giftCardId'))
            gift_card.write({
                'points': coupon_vals['points'],
                'source_pos_order_id': self.id,
                'partner_id': get_partner_id(coupon_vals.get('partner_id', False)),
            })
            updated_gift_cards |= gift_card
        
        # ------------------------------------------------------------
        # MAP NEW COUPONS
        # ------------------------------------------------------------
        for old_id, new_id in zip(coupons_to_create.keys(), new_coupons):
            coupon_new_id_map[new_id.id] = old_id
        
        # Process all coupons
        all_coupons = self.env['loyalty.card'].sudo().browse(coupon_new_id_map.keys()).exists()
        
        # Link coupons to order lines
        lines_per_reward_code = defaultdict(lambda: self.env['pos.order.line'])
        for line in self.lines:
            if not line.reward_identifier_code:
                continue
            lines_per_reward_code[line.reward_identifier_code] |= line
        
        for coupon in all_coupons:
            if coupon.id in coupon_new_id_map:
                old_id = coupon_new_id_map[coupon.id]
                is_newly_created = old_id < 0
                is_gift_card = coupon.program_id.program_type == 'gift_card'
                
                if not (is_newly_created and is_gift_card):
                    coupon.points += coupon_data[old_id]['points']
            
            for reward_code in coupon_data[coupon_new_id_map[coupon.id]].get('line_codes', []):
                lines_per_reward_code[reward_code].coupon_id = coupon
        
        # Send creation email
        new_coupons.with_context(action_no_send_mail=False)._send_creation_communication()
        
        # Prepare reports
        report_per_program = {}
        coupon_per_report = defaultdict(list)
        
        for coupon in new_coupons | updated_gift_cards:
            if coupon.program_id not in report_per_program:
                report_per_program[coupon.program_id] = coupon.program_id.communication_plan_ids.\
                    filtered(lambda c: c.trigger == 'create').pos_report_print_id
            for report in report_per_program[coupon.program_id]:
                coupon_per_report[report.id].append(coupon.id)
        
        # ------------------------------------------------------------
        # ⭐⭐⭐ PREPARE RESPONSE WITH GIFT CARD CODE ⭐⭐⭐
        # ------------------------------------------------------------
        result = {
            'coupon_updates': [{
                'old_id': coupon_new_id_map[coupon.id],
                'id': coupon.id,
                'points': coupon.points,
                'code': coupon.code,
                'program_id': coupon.program_id.id,
                'partner_id': coupon.partner_id.id,
            } for coupon in all_coupons if coupon.program_id.is_nominative],
            'program_updates': [{
                'program_id': program.id,
                'usages': program.total_order_count,
            } for program in all_coupons.program_id],
            'new_coupon_info': [{
                'program_name': coupon.program_id.name,
                'expiration_date': coupon.expiration_date,
                'code': coupon.code,
            } for coupon in new_coupons if (
                coupon.program_id.applies_on == 'future'
                and coupon.program_id.program_type not in ['gift_card', 'ewallet']
            )],
            'coupon_report': coupon_per_report,
            # ⭐⭐⭐ MOST IMPORTANT: SEND GIFT CARD CODE ⭐⭐⭐
            'gift_card_code': self.gift_card_code or gift_card_code_str or '',
        }
        
        _logger.info("✅ Sending response with gift_card_code: %s", result.get('gift_card_code'))
        _logger.info("="*80)
        _logger.info("🎁 END confirm_coupon_programs - SUCCESS")
        _logger.info("="*80)
        
        return result

    # ------------------------------------------------------------
    # FIXED: create_from_ui with robust validation
    # ------------------------------------------------------------
    @api.model
    def create_from_ui(self, orders, draft=False):
        """
        ✅ OVERRIDE: Tambahkan gift_card_code ke response create_from_ui
        """
        _logger.info("="*80)
        _logger.info("🚀 START create_from_ui")
        _logger.info("🚀 Input type: %s", type(orders))
        _logger.info("🚀 Input value: %s", orders)
        _logger.info("🚀 Draft: %s", draft)
        
        # ============================================================
        # ⭐⭐⭐ CRITICAL FIX 1: VALIDATE INPUT ⭐⭐⭐
        # ============================================================
        if orders is False:
            _logger.error("❌❌❌ CRITICAL ERROR: orders parameter is FALSE!")
            _logger.error("❌❌❌ This happens when frontend sends wrong data")
            _logger.error("❌❌❌ Returning empty list to prevent crash")
            return []
        
        if orders is None:
            _logger.warning("⚠️ Orders parameter is None, using empty list")
            orders = []
        
        if not isinstance(orders, (list, tuple)):
            _logger.error("❌ Orders is not list/tuple! Type: %s", type(orders))
            if isinstance(orders, dict):
                orders = [orders]
            else:
                _logger.error("❌ Cannot convert to list, returning empty")
                return []
        
        if len(orders) == 0:
            _logger.warning("⚠️ Orders list is empty")
            return []
        
        _logger.info("🚀 Processing %s orders", len(orders))
        
        # ============================================================
        # Call parent method
        # ============================================================
        try:
            result = super(PosOrder, self).create_from_ui(orders, draft)
        except Exception as e:
            _logger.error("❌❌❌ ERROR in parent create_from_ui: %s", str(e))
            _logger.error("❌❌❌ Traceback:", exc_info=True)
            # Return minimal response to prevent frontend crash
            return [{'success': False, 'error': str(e)}]
        
        _logger.info("🚀 Parent result type: %s", type(result))
        _logger.info("🚀 Parent result value: %s", result)
        
        # ============================================================
        # ⭐⭐⭐ CRITICAL FIX 2: PROCESS RESULT ⭐⭐⭐
        # ============================================================
        if not isinstance(result, list):
            _logger.error("❌ Result is not a list! Type: %s", type(result))
            return []
        
        _logger.info("🚀 Processing %s results", len(result))
        
        for i, res in enumerate(result):
            _logger.info("🚀 Result[%s]: %s (type: %s)", i, res, type(res))
            
            order_id = None
            order_obj = None
            
            # Determine order_id from result
            if isinstance(res, dict) and 'id' in res:
                order_id = res['id']
                _logger.info("🚀   Found order_id in dict: %s", order_id)
            elif isinstance(res, int):
                order_id = res
                # Convert to dict for consistency
                result[i] = {'id': order_id}
                res = result[i]
                _logger.info("🚀   Converted int to dict with id: %s", order_id)
            elif isinstance(res, dict) and 'order_id' in res:
                order_id = res['order_id']
                _logger.info("🚀   Found order_id as 'order_id': %s", order_id)
            else:
                _logger.warning("⚠️   Cannot find order_id in result[%s]", i)
                continue
            
            if not order_id:
                _logger.warning("⚠️   order_id is None/False")
                continue
            
            # Fetch order and add gift_card_code
            try:
                order_obj = self.browse(order_id)
                if not order_obj.exists():
                    _logger.error("❌ Order %s does not exist!", order_id)
                    res['gift_card_code'] = ''
                    continue
                
                # Force refresh from database
                order_obj._invalidate_cache(['gift_card_code'])
                self.env.cr.execute("SELECT gift_card_code FROM pos_order WHERE id = %s", (order_id,))
                db_gift_card_code = self.env.cr.fetchone()
                
                gift_card_code = ''
                if db_gift_card_code and db_gift_card_code[0]:
                    gift_card_code = db_gift_card_code[0]
                elif order_obj.gift_card_code:
                    gift_card_code = order_obj.gift_card_code
                
                # Add to result
                res['gift_card_code'] = gift_card_code
                
                if gift_card_code:
                    _logger.info("✅ Added gift_card_code to result[%s]: %s", i, gift_card_code)
                else:
                    _logger.info("⚠️ No gift_card_code for order %s", order_id)
                    
            except Exception as e:
                _logger.error("❌ Error processing order %s: %s", order_id, str(e))
                res['gift_card_code'] = ''
        
        _logger.info("="*80)
        _logger.info("🚀 END create_from_ui - Success")
        _logger.info("="*80)
        
        return result

    # ------------------------------------------------------------
    # FIXED: _process_order
    # ------------------------------------------------------------
    def _process_order(self, order, draft, existing_order):
        """
        ✅ OVERRIDE: Process order and return ID
        """
        _logger.info("🔄 START _process_order")
        _logger.info("🔄 Order data type: %s", type(order))
        
        if isinstance(order, dict):
            _logger.info("🔄 Order keys: %s", order.keys())
            if 'data' in order:
                _logger.info("🔄 Order name: %s", order.get('data', {}).get('name', 'Unknown'))
        
        # Call parent
        try:
            order_id = super(PosOrder, self)._process_order(order, draft, existing_order)
        except Exception as e:
            _logger.error("❌ ERROR in _process_order: %s", str(e))
            raise
        
        _logger.info("🔄 Parent returned order_id: %s (type: %s)", order_id, type(order_id))
        
        if order_id:
            try:
                order_obj = self.browse(order_id)
                _logger.info("🔄 Created order: %s", order_obj.name)
                _logger.info("🔄 Order gift_card_code: %s", order_obj.gift_card_code)
            except Exception as e:
                _logger.error("❌ Error fetching order %s: %s", order_id, str(e))
        
        _logger.info("🔄 END _process_order")
        
        return order_id

    # ------------------------------------------------------------
    # FIXED: _export_for_ui
    # ------------------------------------------------------------
    def _export_for_ui(self, order):
        """
        ✅ OVERRIDE: Export order data for UI
        """
        result = super(PosOrder, self)._export_for_ui(order)
        
        # Add gift_card_code
        if order and order.gift_card_code:
            result['gift_card_code'] = order.gift_card_code
            _logger.info("📤 Exported gift_card_code for %s: %s", 
                       order.name, order.gift_card_code)
        else:
            result['gift_card_code'] = ''
        
        return result

    # ------------------------------------------------------------
    # RECOVERY METHOD
    # ------------------------------------------------------------
    def _recover_gift_card_codes(self):
        """
        Recovery method to fetch gift card codes if missed
        """
        _logger.info("🔄 START _recover_gift_card_codes")
        
        for order in self:
            if not order.gift_card_code:
                # Find loyalty cards related to this order
                gift_cards = self.env['loyalty.card'].search([
                    ('source_pos_order_id', '=', order.id),
                    ('program_id.program_type', '=', 'gift_card')
                ])
                
                if gift_cards:
                    codes = gift_cards.mapped('code')
                    if codes:
                        gift_card_code_str = ', '.join(codes)
                        
                        # Update using SQL
                        self.env.cr.execute(
                            "UPDATE pos_order SET gift_card_code = %s WHERE id = %s",
                            (gift_card_code_str, order.id)
                        )
                        
                        order._invalidate_cache(['gift_card_code'])
                        order.gift_card_code = gift_card_code_str
                        
                        _logger.info("✅ Recovered gift card code for %s: %s", 
                                   order.name, gift_card_code_str)
        
        _logger.info("🔄 END _recover_gift_card_codes")
        
    # ------------------------------------------------------------
    # DEBUG METHOD
    # ------------------------------------------------------------
    def debug_order_flow(self):
        """
        Debug comprehensive order flow
        """
        _logger.info("="*80)
        _logger.info("🔍 DEBUG ORDER FLOW START")
        _logger.info("="*80)
        
        # Check recent orders
        recent_orders = self.search([], limit=10, order='id desc')
        _logger.info("🔍 Recent orders: %s", len(recent_orders))
        
        for o in recent_orders:
            _logger.info("🔍 Order: %s (ID: %s)", o.name, o.id)
            _logger.info("🔍   Amount: %s, Gift Code: %s", o.amount_total, o.gift_card_code)
            
            # Check associated gift cards
            gift_cards = self.env['loyalty.card'].search([
                ('source_pos_order_id', '=', o.id)
            ])
            _logger.info("🔍   Associated gift cards: %s", len(gift_cards))
            for gc in gift_cards:
                _logger.info("🔍     - %s: %s points (Program: %s)", 
                           gc.code, gc.points, gc.program_id.name)
        
        _logger.info("="*80)
        _logger.info("🔍 DEBUG ORDER FLOW END")
        _logger.info("="*80)
        return True