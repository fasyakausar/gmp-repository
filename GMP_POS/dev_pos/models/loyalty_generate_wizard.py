# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class LoyaltyGenerateWizard(models.TransientModel):
    _inherit = 'loyalty.generate.wizard'

    # Override default value for mode field to use 'selected' instead of 'anonymous'
    mode = fields.Selection(
        selection=[
            ('anonymous', 'Anonymous Customers'),
            ('selected', 'Selected Customers')
        ],
        string='For',
        required=True,
        default='selected'  # Changed from 'anonymous' to 'selected'
    )

    def _get_coupon_values(self, partner):
        """
        Override to ensure partner_id is always set for gift cards and ewallets
        """
        self.ensure_one()
        values = super()._get_coupon_values(partner)
        
        # For gift_card and ewallet programs, always assign partner_id
        if self.program_id.program_type in ['gift_card', 'ewallet']:
            # If mode is 'selected', partner should be a res.partner record
            if self.mode == 'selected' and hasattr(partner, 'id'):
                values['partner_id'] = partner.id
            elif self.mode == 'anonymous':
                # For anonymous mode, we keep partner_id as False
                # It will be assigned later from the POS order
                values['partner_id'] = False
        
        return values

    @api.constrains('mode', 'program_id')
    def _check_gift_card_requires_partner(self):
        """
        Optional: Add validation to warn user if generating gift card without partner
        """
        for wizard in self:
            if wizard.program_id.program_type == 'gift_card' and wizard.mode == 'anonymous':
                # Just a warning, not blocking
                # If you want to force selected mode, raise UserError here
                pass

    def generate_coupons(self):
        """
        Override to add custom logic after coupon generation if needed
        """
        # Call parent method to generate coupons
        result = super().generate_coupons()
        
        # Optional: Add custom notification or logging
        if self.program_id.program_type == 'gift_card' and self.mode == 'selected':
            # Log or notify that gift cards were generated with partners
            partners_count = len(self._get_partners()) if self.mode == 'selected' else self.coupon_qty
            # You can add notification here if needed
            pass
        
        return result