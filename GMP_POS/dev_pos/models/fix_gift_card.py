# # -*- coding: utf-8 -*-

# from collections import defaultdict
# from odoo import models, fields, api, _
# from odoo.tools import float_compare
# import logging

# _logger = logging.getLogger(__name__)

# class PosOrderGiftCardFix(models.Model):
#     _inherit = 'pos.order'

#     def confirm_coupon_programs(self, coupon_data):
#         """
#         ✅ FIXED: Kalkulasi gift card balance yang benar
#         """
#         _logger.info("="*80)
#         _logger.info("🎁 START confirm_coupon_programs - ORDER: %s", self.name)
#         _logger.info("🎁 Order ID: %s, Amount Paid: %s, Amount Total: %s", 
#                     self.id, self.amount_paid, self.amount_total)
        
#         # Helper function
#         def get_partner_id(partner_id):
#             return partner_id and self.env['res.partner'].browse(partner_id).exists() and partner_id or False
        
#         # Convert keys to int
#         coupon_data = {int(k): v for k, v in coupon_data.items()} if coupon_data else {}
        
#         # Check existing loyalty cards
#         self._check_existing_loyalty_cards(coupon_data)
        
#         # Map coupon IDs
#         coupon_new_id_map = {k: k for k in coupon_data.keys() if k > 0}
        
#         # Create coupons
#         coupons_to_create = {k: v for k, v in coupon_data.items() if k < 0 and not v.get('giftCardId')}
        
#         _logger.info("🎁 Coupons to create: %s", len(coupons_to_create))
        
#         # ============================================================
#         # ✅ FIX 1: KALKULASI GIFT CARD AMOUNT YANG BENAR
#         # ============================================================
#         gift_card_lines = self.lines.filtered(
#             lambda l: l.reward_id and l.reward_id.program_id.program_type == 'gift_card'
#         )
        
#         _logger.info("🎁 Gift card lines found: %s", len(gift_card_lines))
        
#         # Dictionary untuk menyimpan total per program
#         gift_card_program_totals = {}
        
#         for line in gift_card_lines:
#             program_id = line.reward_id.program_id.id
            
#             # ✅ PENTING: Gunakan price_subtotal_incl untuk total yang benar
#             line_amount = abs(line.price_subtotal_incl)
            
#             _logger.info("🎁 Line: %s | Qty: %s | Price Unit: %s | Subtotal: %s | Amount: %s", 
#                         line.product_id.name, 
#                         line.qty, 
#                         line.price_unit, 
#                         line.price_subtotal_incl,
#                         line_amount)
            
#             if program_id in gift_card_program_totals:
#                 gift_card_program_totals[program_id] += line_amount
#             else:
#                 gift_card_program_totals[program_id] = line_amount
        
#         _logger.info("🎁 Gift card totals per program: %s", gift_card_program_totals)
        
#         # Count gift cards per program
#         program_gift_card_count = {}
#         for key, p in coupons_to_create.items():
#             program_id = p.get('program_id')
#             if program_id:
#                 program_gift_card_count[program_id] = program_gift_card_count.get(program_id, 0) + 1
        
#         _logger.info("🎁 Gift card count per program: %s", program_gift_card_count)
        
#         # ============================================================
#         # ✅ FIX 2: BUAT COUPON DENGAN BALANCE YANG BENAR
#         # ============================================================
#         coupon_create_vals = []
        
#         for key, p in coupons_to_create.items():
#             program_id = p.get('program_id')
#             points = 0
            
#             if program_id:
#                 program = self.env['loyalty.program'].browse(program_id)
                
#                 if program.program_type == 'gift_card':
#                     # ✅ METODE BARU: Kalkulasi berdasarkan total program
#                     total_amount = gift_card_program_totals.get(program_id, 0)
#                     card_count = program_gift_card_count.get(program_id, 1)
                    
#                     if total_amount > 0:
#                         # Bagi rata jika ada multiple cards
#                         points = total_amount / card_count
#                     else:
#                         # Fallback: gunakan amount_paid
#                         _logger.warning("⚠️ No gift card lines found, using amount_paid")
#                         points = self.amount_paid / len(coupons_to_create) if coupons_to_create else self.amount_paid
                    
#                     # Round to 2 decimal
#                     points = round(points, 2)
                    
#                     _logger.info("✅ Gift Card Points Calculated:")
#                     _logger.info("   Program: %s", program.name)
#                     _logger.info("   Total Amount: %s", total_amount)
#                     _logger.info("   Card Count: %s", card_count)
#                     _logger.info("   Points per Card: %s", points)
            
#             coupon_create_vals.append({
#                 'program_id': program_id,
#                 'partner_id': get_partner_id(p.get('partner_id', False)),
#                 'code': p.get('barcode') or self.env['loyalty.card']._generate_code(),
#                 'points': points,
#                 'expiration_date': p.get('date_to', False),
#                 'source_pos_order_id': self.id,
#             })
        
#         _logger.info("🎁 Creating %s coupons with values: %s", len(coupon_create_vals), coupon_create_vals)
        
#         # ============================================================
#         # CREATE COUPONS
#         # ============================================================
#         new_coupons = self.env['loyalty.card'].with_context(action_no_send_mail=True).sudo().create(coupon_create_vals)
        
#         _logger.info("✅ Created %s coupons", len(new_coupons))
#         for coupon in new_coupons:
#             _logger.info("   Coupon: %s | Code: %s | Balance: %s", 
#                         coupon.program_id.name, coupon.code, coupon.points)
        
#         # ============================================================
#         # SAVE GIFT CARD CODE
#         # ============================================================
#         gift_card_codes = []
#         for coupon in new_coupons:
#             if coupon.program_id.program_type == 'gift_card':
#                 gift_card_codes.append(coupon.code)
        
#         if gift_card_codes:
#             gift_card_code_str = ', '.join(gift_card_codes)
            
#             # Direct SQL update
#             self.env.cr.execute(
#                 "UPDATE pos_order SET gift_card_code = %s WHERE id = %s",
#                 (gift_card_code_str, self.id)
#             )
#             self.env.cr.commit()
            
#             # Update cache
#             self._invalidate_cache(['gift_card_code'], [self.id])
#             self.write({'gift_card_code': gift_card_code_str})
            
#             _logger.info("✅ Gift card codes saved: %s", gift_card_code_str)
        
#         # ============================================================
#         # UPDATE EXISTING GIFT CARDS
#         # ============================================================
#         gift_cards_to_update = [v for v in coupon_data.values() if v.get('giftCardId')]
#         updated_gift_cards = self.env['loyalty.card']
        
#         for coupon_vals in gift_cards_to_update:
#             gift_card = self.env['loyalty.card'].browse(coupon_vals.get('giftCardId'))
#             gift_card.write({
#                 'points': coupon_vals['points'],
#                 'source_pos_order_id': self.id,
#                 'partner_id': get_partner_id(coupon_vals.get('partner_id', False)),
#             })
#             updated_gift_cards |= gift_card
        
#         # ============================================================
#         # MAP NEW COUPONS
#         # ============================================================
#         for old_id, new_id in zip(coupons_to_create.keys(), new_coupons):
#             coupon_new_id_map[new_id.id] = old_id
        
#         # Process all coupons
#         all_coupons = self.env['loyalty.card'].sudo().browse(coupon_new_id_map.keys()).exists()
        
#         # Link to order lines
#         lines_per_reward_code = defaultdict(lambda: self.env['pos.order.line'])
#         for line in self.lines:
#             if not line.reward_identifier_code:
#                 continue
#             lines_per_reward_code[line.reward_identifier_code] |= line
        
#         for coupon in all_coupons:
#             if coupon.id in coupon_new_id_map:
#                 old_id = coupon_new_id_map[coupon.id]
#                 is_newly_created = old_id < 0
#                 is_gift_card = coupon.program_id.program_type == 'gift_card'
                
#                 # ✅ FIX: Jangan tambahkan points untuk gift card baru
#                 if not (is_newly_created and is_gift_card):
#                     coupon.points += coupon_data[old_id]['points']
            
#             for reward_code in coupon_data[coupon_new_id_map[coupon.id]].get('line_codes', []):
#                 lines_per_reward_code[reward_code].coupon_id = coupon
        
#         # Send emails
#         new_coupons.with_context(action_no_send_mail=False)._send_creation_communication()
        
#         # Prepare reports
#         report_per_program = {}
#         coupon_per_report = defaultdict(list)
        
#         for coupon in new_coupons | updated_gift_cards:
#             if coupon.program_id not in report_per_program:
#                 report_per_program[coupon.program_id] = coupon.program_id.communication_plan_ids.\
#                     filtered(lambda c: c.trigger == 'create').pos_report_print_id
#             for report in report_per_program[coupon.program_id]:
#                 coupon_per_report[report.id].append(coupon.id)
        
#         # ============================================================
#         # PREPARE RESPONSE
#         # ============================================================
#         result = {
#             'coupon_updates': [{
#                 'old_id': coupon_new_id_map[coupon.id],
#                 'id': coupon.id,
#                 'points': coupon.points,
#                 'code': coupon.code,
#                 'program_id': coupon.program_id.id,
#                 'partner_id': coupon.partner_id.id,
#             } for coupon in all_coupons if coupon.program_id.is_nominative],
#             'program_updates': [{
#                 'program_id': program.id,
#                 'usages': program.total_order_count,
#             } for program in all_coupons.program_id],
#             'new_coupon_info': [{
#                 'program_name': coupon.program_id.name,
#                 'expiration_date': coupon.expiration_date,
#                 'code': coupon.code,
#                 'balance': coupon.points,  # ✅ Tambahkan balance
#             } for coupon in new_coupons if (
#                 coupon.program_id.applies_on == 'future'
#                 and coupon.program_id.program_type not in ['gift_card', 'ewallet']
#             )],
#             'coupon_report': coupon_per_report,
#             'gift_card_code': self.gift_card_code or gift_card_code_str or '',
#         }
        
#         _logger.info("="*80)
#         _logger.info("✅ confirm_coupon_programs COMPLETED")
#         _logger.info("✅ Result: %s", result)
#         _logger.info("="*80)
        
#         return result

#     # ============================================================
#     # ✅ TAMBAHAN: Method untuk debug gift card
#     # ============================================================
#     def debug_gift_card_balance(self):
#         """
#         Method untuk debug gift card balance
#         """
#         _logger.info("="*80)
#         _logger.info("🔍 DEBUG GIFT CARD BALANCE")
#         _logger.info("="*80)
        
#         for order in self:
#             _logger.info("📋 Order: %s (ID: %s)", order.name, order.id)
#             _logger.info("   Amount Total: %s", order.amount_total)
#             _logger.info("   Amount Paid: %s", order.amount_paid)
            
#             # Check order lines
#             gift_card_lines = order.lines.filtered(
#                 lambda l: l.reward_id and l.reward_id.program_id.program_type == 'gift_card'
#             )
            
#             _logger.info("   Gift Card Lines: %s", len(gift_card_lines))
#             for line in gift_card_lines:
#                 _logger.info("      Line: %s", line.product_id.name)
#                 _logger.info("         Qty: %s", line.qty)
#                 _logger.info("         Price Unit: %s", line.price_unit)
#                 _logger.info("         Price Subtotal: %s", line.price_subtotal)
#                 _logger.info("         Price Subtotal Incl: %s", line.price_subtotal_incl)
            
#             # Check loyalty cards
#             loyalty_cards = self.env['loyalty.card'].search([
#                 ('source_pos_order_id', '=', order.id)
#             ])
            
#             _logger.info("   Loyalty Cards: %s", len(loyalty_cards))
#             for card in loyalty_cards:
#                 _logger.info("      Card: %s", card.code)
#                 _logger.info("         Program: %s", card.program_id.name)
#                 _logger.info("         Type: %s", card.program_id.program_type)
#                 _logger.info("         Balance: %s", card.points)
        
#         _logger.info("="*80)
#         return True

#     # ============================================================
#     # ✅ RECOVERY: Method untuk fix existing orders
#     # ============================================================
#     def fix_gift_card_balance(self):
#         """
#         Method untuk fix gift card balance yang salah
#         """
#         _logger.info("="*80)
#         _logger.info("🔧 FIXING GIFT CARD BALANCE")
#         _logger.info("="*80)
        
#         for order in self:
#             # Find gift card lines
#             gift_card_lines = order.lines.filtered(
#                 lambda l: l.reward_id and l.reward_id.program_id.program_type == 'gift_card'
#             )
            
#             if not gift_card_lines:
#                 _logger.info("⚠️ Order %s has no gift card lines", order.name)
#                 continue
            
#             # Calculate correct amount
#             gift_card_program_totals = {}
#             for line in gift_card_lines:
#                 program_id = line.reward_id.program_id.id
#                 line_amount = abs(line.price_subtotal_incl)
                
#                 if program_id in gift_card_program_totals:
#                     gift_card_program_totals[program_id] += line_amount
#                 else:
#                     gift_card_program_totals[program_id] = line_amount
            
#             # Find and update loyalty cards
#             loyalty_cards = self.env['loyalty.card'].search([
#                 ('source_pos_order_id', '=', order.id),
#                 ('program_id.program_type', '=', 'gift_card')
#             ])
            
#             if not loyalty_cards:
#                 _logger.info("⚠️ Order %s has no loyalty cards", order.name)
#                 continue
            
#             # Count cards per program
#             program_card_count = {}
#             for card in loyalty_cards:
#                 program_id = card.program_id.id
#                 program_card_count[program_id] = program_card_count.get(program_id, 0) + 1
            
#             # Update each card
#             for card in loyalty_cards:
#                 program_id = card.program_id.id
#                 total_amount = gift_card_program_totals.get(program_id, 0)
#                 card_count = program_card_count.get(program_id, 1)
                
#                 correct_balance = round(total_amount / card_count, 2)
                
#                 if card.points != correct_balance:
#                     _logger.info("🔧 Fixing card %s: %s -> %s", 
#                                 card.code, card.points, correct_balance)
#                     card.write({'points': correct_balance})
#                 else:
#                     _logger.info("✅ Card %s already correct: %s", 
#                                 card.code, card.points)
        
#         _logger.info("="*80)
#         _logger.info("✅ GIFT CARD BALANCE FIX COMPLETED")
#         _logger.info("="*80)
        
#         return True