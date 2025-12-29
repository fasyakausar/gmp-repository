import requests
from datetime import datetime, timedelta
import pytz
from odoo import models, fields, api, SUPERUSER_ID
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)

class ReportSaleDetailsInherit(models.AbstractModel):
    _inherit = "report.point_of_sale.report_saledetails"

    def get_sale_details(self, date_start=False, date_stop=False, config_ids=False, session_ids=False):
        # 🔹 Panggil bawaan dulu
        res = super().get_sale_details(date_start, date_stop, config_ids, session_ids)

        sessions = self.env["pos.session"].browse(session_ids) if session_ids else []
        for session in sessions:
            # 🔹 Ambil total modal semua shift dalam session
            modal_total = sum(self.env["end.shift"].search([("session_id", "=", session.id)]).mapped("modal"))

            for payment in res.get("payments", []):
                if payment.get("session") == session.id and payment.get("cash"):
                    # final_count asli + modal_total
                    payment["final_count"] = (payment.get("final_count") or 0.0) + modal_total
                    # difference harus ikut update
                    payment["money_difference"] = (payment.get("money_counted") or 0.0) - payment["final_count"]

        return res

class PosSession(models.Model):
    _inherit = 'pos.session'

    is_updated = fields.Boolean(string="Updated", default=False, readonly=True, tracking=True)
    name_session_pos = fields.Char(string="Name Session POS (Odoo Store)", tracking=True)

    def _pos_ui_models_to_load(self):
        res = super()._pos_ui_models_to_load()
        
        # Only add models that exist and are properly configured
        additional_models = []
        
        # Check if each model exists before adding
        model_checks = [
            'pos.order',  # ✅ TAMBAHAN: Load pos.order untuk gift_card_code
        ]
        
        for model_name in model_checks:
            try:
                if model_name in self.env:
                    # Test if model is accessible
                    self.env[model_name].check_access_rights('read', raise_exception=False)
                    additional_models.append(model_name)
                    _logger.info(f"✅ Added model {model_name} to POS UI models")
            except Exception as e:
                _logger.warning(f"⚠️ Skipping model {model_name}: {e}")
        
        res += additional_models
        return res

    # ============================================
    # ✅ TAMBAHAN: Loader untuk pos.order
    # ============================================

    def _loader_params_pos_order(self):
        """
        Load pos.order dengan field gift_card_code
        Hanya load order dari session yang sama dan sudah paid
        """
        return {
            'search_params': {
                'domain': [
                    ('session_id', '=', self.id),
                    ('state', 'in', ['paid', 'done', 'invoiced'])
                ],
                'fields': [
                    'id',
                    'name',
                    'pos_reference',
                    'date_order',
                    'partner_id',
                    'user_id',
                    'amount_total',
                    'amount_tax',
                    'amount_paid',
                    'amount_return',
                    'gift_card_code',  # ✅ FIELD PENTING
                    'state',
                    'account_move',
                    'to_invoice',
                ],
            }
        }

    def _get_pos_ui_pos_order(self, params):
        """
        Get pos.order records untuk POS UI
        """
        try:
            records = self.env['pos.order'].search_read(
                params['search_params'].get('domain', []),
                params['search_params']['fields'],
                limit=100,  # Limit untuk performa
                order='date_order DESC'
            )
            
            # Process relational fields
            for rec in records:
                # Handle partner_id
                if rec.get('partner_id'):
                    if isinstance(rec['partner_id'], int):
                        partner = self.env['res.partner'].browse(rec['partner_id'])
                        rec['partner_id'] = [rec['partner_id'], partner.name if partner.exists() else '']
                    elif isinstance(rec['partner_id'], list) and len(rec['partner_id']) >= 2:
                        rec['partner_id'] = [int(rec['partner_id'][0]), str(rec['partner_id'][1])]
                
                # Handle user_id
                if rec.get('user_id'):
                    if isinstance(rec['user_id'], int):
                        user = self.env['res.users'].browse(rec['user_id'])
                        rec['user_id'] = [rec['user_id'], user.name if user.exists() else '']
                    elif isinstance(rec['user_id'], list) and len(rec['user_id']) >= 2:
                        rec['user_id'] = [int(rec['user_id'][0]), str(rec['user_id'][1])]
                
                # ✅ Log gift_card_code untuk debugging
                if rec.get('gift_card_code'):
                    _logger.info(
                        f"📄 Order {rec['name']} has gift_card_code: {rec['gift_card_code']}"
                    )
            
            _logger.info(f"✅ Loaded {len(records)} pos.order records with gift_card_code field")
            return records
            
        except Exception as e:
            _logger.error(f"❌ Error loading pos.order: {e}")
            import traceback
            _logger.error(traceback.format_exc())
            return []

    def _pos_ui_pos_order(self, params):
        """
        Entry point untuk loader pos.order
        """
        return self._get_pos_ui_pos_order(params)