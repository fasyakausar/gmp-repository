from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

class ReturnApprovalWizard(models.TransientModel):
    _name = 'return.approval.wizard'
    _description = 'Return Approval Action Wizard'

    action = fields.Selection([
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ], string='Action', required=True, default='approve')
    
    level = fields.Integer(string='Approval Level', default=1)
    
    notes = fields.Text(string='Notes/Comments')
    
    def action_confirm(self):
        """Execute the approval/rejection action"""
        self.ensure_one()
        
        # Get active return approval record
        active_id = self.env.context.get('active_id')
        if not active_id:
            raise UserError("No return approval record found.")
        
        return_approval = self.env['return.approval'].browse(active_id)
        
        # Execute action based on selection
        if self.action == 'approve':
            if self.level == 2:
                return_approval.with_context(
                    approval_notes=self.notes
                ).action_approve_level_2()
            elif self.level == 1:
                return_approval.with_context(
                    approval_notes=self.notes
                ).action_approve_level_1()
            else:
                raise UserError("Invalid approval level.")
        
        elif self.action == 'reject':
            return_approval.with_context(
                approval_notes=self.notes
            ).action_reject()
        
        return {'type': 'ir.actions.act_window_close'}

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    gm_use_multi_level_approval = fields.Boolean(
        string="Use Multi-Level Approval",
        config_parameter='return_approval.use_multi_level',
        help="Enable two-level approval for return approvals. "
             "If disabled, only Level 1 approval is required."
    )

class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'
    
    is_refund = fields.Boolean(
        string='Is Refund Payment Method',
        default=False,
        help='Check this if this payment method should be used for refunds/returns'
    )

class ReturnApproval(models.Model):
    _name = 'return.approval'
    _rec_name = 'gm_doc_num'
    _description = "Return Approval"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'gm_creation_date desc'

    gm_doc_num = fields.Char(
        string="Doc Number", 
        required=True, 
        copy=False, 
        readonly=True, 
        default='New',
        tracking=True
    )
    gm_pos_order_id = fields.Many2one(
        'pos.order', 
        string="Original POS Order",
        required=True,
        readonly=True,
        tracking=True
    )
    gm_requested_by = fields.Many2one(
        'res.users', 
        string="Requested By",
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
        tracking=True
    )
    gm_creation_date = fields.Datetime(
        string="Creation Date",
        default=fields.Datetime.now,
        required=True,
        readonly=True,
        tracking=True
    )
    gm_request_date = fields.Datetime(
        string="Request Date",
        default=fields.Datetime.now,
        required=True,
        readonly=True
    )
    gm_return_reason = fields.Text(
        string="Return Reason",
        required=True,
        tracking=True,
        states={'approved': [('readonly', True)], 'rejected': [('readonly', True)]}
    )
    gm_approval_by = fields.Many2many(
        'res.users', 
        'return_approval_users_rel',
        'approval_id',
        'user_id',
        string="Approved By",
        readonly=True,
        tracking=True
    )
    gm_approval_date = fields.Datetime(
        string="Final Approval Date",
        readonly=True,
        tracking=True
    )
    gm_status = fields.Selection([
        ('draft', 'Draft'),
        ('waiting_approval_1', 'Waiting Approval L1'),
        ('waiting_approval_2', 'Waiting Approval L2'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string="Status", default='draft', required=True, readonly=True, tracking=True)
    
    gm_line_ids = fields.One2many(
        'return.approval.line', 
        'return_approval_id', 
        string='Return Approval Lines',
        required=True,
        states={'approved': [('readonly', True)], 'rejected': [('readonly', True)]}
    )
    gm_history_ids = fields.One2many(
        'return.approval.history',
        'return_approval_id',
        string='Approval History',
        readonly=True
    )
    gm_refund_order_id = fields.Many2one(
        'pos.order',
        string="Refund Order",
        readonly=True,
        copy=False,
        tracking=True
    )
    
    # Computed fields
    gm_current_level = fields.Integer(
        string="Current Level",
        compute='_compute_current_level',
        store=True
    )
    gm_can_approve_level_1 = fields.Boolean(
        string="Can Approve Level 1",
        compute='_compute_can_approve'
    )
    gm_can_approve_level_2 = fields.Boolean(
        string="Can Approve Level 2",
        compute='_compute_can_approve'
    )
    gm_total_amount = fields.Monetary(
        string="Total Amount",
        compute='_compute_total_amount',
        store=True,
        currency_field='gm_currency_id'
    )
    gm_currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='gm_pos_order_id.currency_id',
        store=True,
        readonly=True
    )
    
    @api.depends('gm_line_ids.gm_qty', 'gm_line_ids.gm_product_id')
    def _compute_total_amount(self):
        for record in self:
            total = 0.0
            for line in record.gm_line_ids:
                # Get price from original order line
                original_line = record.gm_pos_order_id.lines.filtered(
                    lambda l: l.product_id.id == line.gm_product_id.id
                )
                if original_line:
                    total += abs(line.gm_qty * original_line[0].price_unit)
            record.gm_total_amount = total
    
    @api.depends('gm_status', 'gm_history_ids')
    def _compute_current_level(self):
        for record in self:
            if record.gm_status == 'waiting_approval_1':
                record.gm_current_level = 1
            elif record.gm_status == 'waiting_approval_2':
                record.gm_current_level = 2
            else:
                record.gm_current_level = 0
    
    @api.depends('gm_status')
    def _compute_can_approve(self):
        for record in self:
            record.gm_can_approve_level_1 = (
                record.gm_status == 'waiting_approval_1' and
                self.env.user.has_group('dev_pos.group_return_approval_level_1')
            )
            record.gm_can_approve_level_2 = (
                record.gm_status == 'waiting_approval_2' and
                self.env.user.has_group('dev_pos.group_return_approval_level_2')
            )
    
    @api.model
    def create(self, vals):
        if vals.get('gm_doc_num', 'New') == 'New':
            vals['gm_doc_num'] = self.env['ir.sequence'].next_by_code('return.approval') or 'New'
        return super(ReturnApproval, self).create(vals)
    
    def action_submit_approval(self):
        """Submit for approval"""
        self.ensure_one()
        if self.gm_status != 'draft':
            raise UserError("Only draft documents can be submitted for approval.")
        
        if not self.gm_line_ids:
            raise UserError("Please add at least one return line before submitting.")
        
        # Check if multi-level approval is enabled
        config = self.env['res.config.settings'].sudo().get_values()
        use_multi_level = config.get('gm_use_multi_level_approval', False)
        
        if use_multi_level:
            self.gm_status = 'waiting_approval_2'
        else:
            self.gm_status = 'waiting_approval_1'
        
        self.message_post(
            body=f"Return approval submitted by {self.env.user.name}",
            subject="Return Approval Submitted"
        )
    
    def action_approve_level_1(self):
        """Approve Level 1"""
        self.ensure_one()
        
        if self.gm_status != 'waiting_approval_1':
            raise UserError("This document is not waiting for Level 1 approval.")
        
        if not self.env.user.has_group('dev_pos.group_return_approval_level_1'):
            raise UserError("You don't have permission to approve at Level 1.")
        
        # Create approval history
        approval_notes = self.env.context.get('approval_notes', '')
        self._create_approval_history(1, 'approved', approval_notes)
        
        # Update status
        self.gm_status = 'approved'
        self.gm_approval_date = fields.Datetime.now()
        self.gm_approval_by = [(4, self.env.user.id)]
        
        # Create refund order with specific items
        self._create_refund_order()
        
        # Process payment and invoice
        self._process_refund_payment_and_invoice()
        
        self.message_post(
            body=f"Approved by {self.env.user.name} (Level 1)",
            subject="Return Approval - Level 1 Approved"
        )
    
    def action_approve_level_2(self):
        """Approve Level 2"""
        self.ensure_one()
        
        if self.gm_status != 'waiting_approval_2':
            raise UserError("This document is not waiting for Level 2 approval.")
        
        if not self.env.user.has_group('dev_pos.group_return_approval_level_2'):
            raise UserError("You don't have permission to approve at Level 2.")
        
        # Create approval history
        approval_notes = self.env.context.get('approval_notes', '')
        self._create_approval_history(2, 'approved', approval_notes)
        
        # Update to Level 1 approval
        self.gm_status = 'waiting_approval_1'
        self.gm_approval_by = [(4, self.env.user.id)]
        
        self.message_post(
            body=f"Approved by {self.env.user.name} (Level 2)",
            subject="Return Approval - Level 2 Approved"
        )
    
    def action_reject(self):
        """Reject the approval"""
        self.ensure_one()
        
        if self.gm_status not in ['waiting_approval_1', 'waiting_approval_2']:
            raise UserError("Only pending approvals can be rejected.")
        
        # Determine current level
        current_level = 1 if self.gm_status == 'waiting_approval_1' else 2
        
        # Check permission
        if current_level == 1 and not self.env.user.has_group('dev_pos.group_return_approval_level_1'):
            raise UserError("You don't have permission to reject at Level 1.")
        if current_level == 2 and not self.env.user.has_group('dev_pos.group_return_approval_level_2'):
            raise UserError("You don't have permission to reject at Level 2.")
        
        # Create approval history
        rejection_notes = self.env.context.get('approval_notes', '')
        self._create_approval_history(current_level, 'rejected', rejection_notes)
        
        # Update status
        self.gm_status = 'rejected'
        
        self.message_post(
            body=f"Rejected by {self.env.user.name} (Level {current_level})",
            subject=f"Return Approval - Level {current_level} Rejected"
        )
    
    def action_reset_to_draft(self):
        """Reset to draft for resubmission"""
        self.ensure_one()
        if self.gm_status != 'rejected':
            raise UserError("Only rejected documents can be reset to draft.")
        
        self.gm_status = 'draft'
        self.gm_approval_by = [(5, 0, 0)]  # Clear all approved users
        
        self.message_post(
            body=f"Reset to draft by {self.env.user.name}",
            subject="Return Approval Reset"
        )
    
    def _create_approval_history(self, level, action, notes=''):
        """Create approval history record"""
        self.env['return.approval.history'].create({
            'return_approval_id': self.id,
            'gm_level': level,
            'gm_user_id': self.env.user.id,
            'gm_action': action,
            'gm_action_date': fields.Datetime.now(),
            'gm_notes': notes or '',
        })
    
    def _create_refund_order(self):
        """Create POS refund order after final approval with specific items"""
        self.ensure_one()
        
        if not self.gm_pos_order_id:
            raise UserError("Original POS order not found.")
        
        if not self.gm_line_ids:
            raise UserError("No return lines found.")
        
        # Get the original order
        original_order = self.gm_pos_order_id
        
        # Create a copy of the order for refund
        refund_order_vals = {
            'name': original_order.name,
            'session_id': original_order.session_id.id,
            'partner_id': original_order.partner_id.id if original_order.partner_id else False,
            'date_order': fields.Datetime.now(),
            'fiscal_position_id': original_order.fiscal_position_id.id if original_order.fiscal_position_id else False,
            'pricelist_id': original_order.pricelist_id.id,
            'amount_tax': 0,
            'amount_total': 0,
            'amount_paid': 0,
            'amount_return': 0,
            'lines': [],
            'state': 'draft',
        }
        
        # Add only the approved return lines
        total_amount = 0
        total_tax = 0
        
        for return_line in self.gm_line_ids:
            # Find the original line
            original_line = original_order.lines.filtered(
                lambda l: l.product_id.id == return_line.gm_product_id.id
            )
            
            if not original_line:
                raise UserError(f"Product {return_line.gm_product_id.name} not found in original order.")
            
            original_line = original_line[0]
            
            # Calculate amounts (negative for refund)
            qty = -abs(return_line.gm_qty)
            price_unit = original_line.price_unit
            price_subtotal = qty * price_unit
            price_subtotal_incl = price_subtotal
            
            # Calculate tax
            if original_line.tax_ids_after_fiscal_position:
                taxes = original_line.tax_ids_after_fiscal_position.compute_all(
                    price_unit, 
                    original_order.pricelist_id.currency_id, 
                    abs(qty), 
                    product=return_line.gm_product_id, 
                    partner=original_order.partner_id
                )
                price_subtotal_incl = qty * taxes['total_included'] / abs(qty) if qty != 0 else 0
                line_tax = taxes['total_included'] - taxes['total_excluded']
                total_tax += line_tax
            
            total_amount += price_subtotal_incl
            
            # Create refund line
            refund_line_vals = {
                'product_id': return_line.gm_product_id.id,
                'qty': qty,
                'price_unit': price_unit,
                'price_subtotal': price_subtotal,
                'price_subtotal_incl': price_subtotal_incl,
                'discount': original_line.discount,
                'tax_ids_after_fiscal_position': [(6, 0, original_line.tax_ids_after_fiscal_position.ids)],
                'full_product_name': return_line.gm_product_id.display_name,
                'refunded_orderline_id': original_line.id,
            }
            
            refund_order_vals['lines'].append((0, 0, refund_line_vals))
        
        # Update totals
        refund_order_vals['amount_tax'] = total_tax
        refund_order_vals['amount_total'] = total_amount
        
        # Create the refund order
        refund_order = self.env['pos.order'].sudo().create(refund_order_vals)
        
        # Link refund order to this approval
        self.gm_refund_order_id = refund_order.id
        
        self.message_post(
            body=f"Refund order {refund_order.name} created with {len(self.gm_line_ids)} item(s)",
            subject="Refund Order Created"
        )
        
        return refund_order
    
    def _process_refund_payment_and_invoice(self):
        """Process payment using refund payment method and create invoice"""
        self.ensure_one()
        
        if not self.gm_refund_order_id:
            raise UserError("Refund order not found.")
        
        refund_order = self.gm_refund_order_id
        
        # Find refund payment method
        refund_payment_method = self.env['pos.payment.method'].search([
            ('is_refund', '=', True),
            ('config_ids', 'in', refund_order.session_id.config_id.id)
        ], limit=1)
        
        if not refund_payment_method:
            raise UserError(
                "No refund payment method found. Please configure a payment method "
                "with 'Is Refund Payment Method' flag enabled in POS Configuration."
            )
        
        # Calculate payment amount (negative for refund)
        payment_amount = refund_order.amount_total
        
        # Add payment to refund order
        refund_order.add_payment({
            'pos_order_id': refund_order.id,
            'amount': payment_amount,
            'name': f'Return Payment - {self.gm_doc_num}',
            'payment_method_id': refund_payment_method.id,
            'payment_date': fields.Datetime.now(),
        })
        
        # Mark order as paid
        try:
            refund_order.action_pos_order_paid()
        except Exception as e:
            raise UserError(f"Failed to process payment: {str(e)}")
        
        # Create invoice
        try:
            refund_order.action_pos_order_invoice()
            self.message_post(
                body=f"Refund payment processed using {refund_payment_method.name} and invoice created",
                subject="Payment and Invoice Processed"
            )
        except Exception as e:
            raise UserError(f"Failed to create invoice: {str(e)}")
    
    def action_view_refund_order(self):
        """Open refund order"""
        self.ensure_one()
        return {
            'name': 'Refund Order',
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'view_mode': 'form',
            'res_id': self.gm_refund_order_id.id,
            'target': 'current',
        }
    
    def action_view_original_order(self):
        """Open original order"""
        self.ensure_one()
        return {
            'name': 'Original Order',
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'view_mode': 'form',
            'res_id': self.gm_pos_order_id.id,
            'target': 'current',
        }


class ReturnApprovalLine(models.Model):
    _name = 'return.approval.line'
    _description = "Return Approval Line"

    return_approval_id = fields.Many2one(
        'return.approval', 
        string="Return Approval",
        required=True,
        ondelete='cascade'
    )
    gm_product_id = fields.Many2one(
        'product.product', 
        string="Product",
        required=True
    )
    gm_description = fields.Char(
        string="Description",
        compute='_compute_description',
        store=True
    )
    gm_qty = fields.Float(
        string="Qty",
        required=True,
        default=1.0
    )
    gm_uom_id = fields.Many2one(
        'uom.uom', 
        string="UOM",
        related='gm_product_id.uom_id',
        readonly=True
    )
    gm_price_unit = fields.Monetary(
        string="Unit Price",
        compute='_compute_price_unit',
        store=True,
        currency_field='gm_currency_id'
    )
    gm_subtotal = fields.Monetary(
        string="Subtotal",
        compute='_compute_subtotal',
        store=True,
        currency_field='gm_currency_id'
    )
    gm_currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='return_approval_id.gm_currency_id',
        store=True,
        readonly=True
    )
    
    @api.depends('gm_product_id')
    def _compute_description(self):
        for line in self:
            line.gm_description = line.gm_product_id.display_name if line.gm_product_id else ''
    
    @api.depends('gm_product_id', 'return_approval_id.gm_pos_order_id')
    def _compute_price_unit(self):
        for line in self:
            if line.return_approval_id.gm_pos_order_id and line.gm_product_id:
                original_line = line.return_approval_id.gm_pos_order_id.lines.filtered(
                    lambda l: l.product_id.id == line.gm_product_id.id
                )
                line.gm_price_unit = original_line[0].price_unit if original_line else 0.0
            else:
                line.gm_price_unit = 0.0
    
    @api.depends('gm_qty', 'gm_price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.gm_subtotal = abs(line.gm_qty * line.gm_price_unit)
    
    @api.constrains('gm_qty')
    def _check_qty(self):
        for line in self:
            if line.gm_qty <= 0:
                raise ValidationError("Quantity must be greater than zero.")
            
class ReturnApprovalHistory(models.Model):
    _name = 'return.approval.history'
    _description = "Return Approval History"
    _order = 'gm_action_date desc'

    return_approval_id = fields.Many2one(
        'return.approval',
        string="Return Approval",
        required=True,
        ondelete='cascade'
    )
    gm_level = fields.Integer(
        string="Approval Level",
        required=True
    )
    gm_user_id = fields.Many2one(
        'res.users',
        string="User",
        required=True
    )
    gm_action = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string="Action", required=True)
    gm_action_date = fields.Datetime(
        string="Action Date",
        required=True,
        default=fields.Datetime.now
    )
    gm_notes = fields.Text(string="Notes")