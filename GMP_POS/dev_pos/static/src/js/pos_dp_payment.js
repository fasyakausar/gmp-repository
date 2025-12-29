/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    /**
     * Override onMounted to auto-select payment method with gm_is_dp = True
     * and auto-input the amount based on gift card balance
     */
    async onMounted() {
        super.onMounted();
        
        // Use async approach for online mode
        await this._autoSelectGiftCardPayment();
    },

    /**
     * Check if there are redeemed gift cards and auto-select payment method
     */
    async _autoSelectGiftCardPayment() {
        const order = this.pos.get_order();
        
        console.log('[DEBUG] Starting auto-select gift card payment...');
        
        // Check if there are any redeemed gift cards
        const hasRedeemedGiftCard = this._hasRedeemedGiftCard(order);
        console.log('[DEBUG] Has redeemed gift card:', hasRedeemedGiftCard);
        
        if (!hasRedeemedGiftCard) {
            return; // No gift card redeemed, proceed with normal flow
        }
        
        // Find payment method with gm_is_dp = True using ORM
        const dpPaymentMethod = await this._findDpPaymentMethodOnline();
        console.log('[DEBUG] DP Payment method found:', dpPaymentMethod);
        
        if (!dpPaymentMethod) {
            console.log('[DEBUG] No payment method with gm_is_dp = True found');
            return; // No payment method with gm_is_dp = True found
        }
        
        // Calculate total balance from all redeemed gift cards
        const totalBalance = await this._calculateTotalGiftCardBalance(order);
        console.log('[DEBUG] Total gift card balance:', totalBalance);
        
        if (totalBalance <= 0) {
            console.log('[DEBUG] No balance available');
            return; // No balance available
        }
        
        // Use the full gift card balance as the payment amount
        const orderDue = order.get_due();
        const amountToInput = totalBalance; // Use full balance, not minimum
        console.log('[DEBUG] Order due:', orderDue);
        console.log('[DEBUG] Gift card balance (amount to input):', amountToInput);
        
        // Add payment line with the calculated amount
        this._addGiftCardPaymentLine(dpPaymentMethod, amountToInput);
        console.log('[DEBUG] Payment line added successfully');
    },

    /**
     * Check if order has redeemed gift cards
     */
    _hasRedeemedGiftCard(order) {
        // Check in couponPointChanges
        if (order.couponPointChanges) {
            for (const pe of Object.values(order.couponPointChanges)) {
                const program = this.pos.program_by_id[pe.program_id];
                if (program && program.program_type === 'gift_card') {
                    console.log('[DEBUG] Found gift card in couponPointChanges:', program.name);
                    return true;
                }
            }
        }
        
        // Check in codeActivatedCoupons
        if (order.codeActivatedCoupons && order.codeActivatedCoupons.length > 0) {
            for (const coupon of order.codeActivatedCoupons) {
                const program = this.pos.program_by_id[coupon.program_id];
                if (program && program.program_type === 'gift_card') {
                    console.log('[DEBUG] Found gift card in codeActivatedCoupons:', program.name);
                    return true;
                }
            }
        }
        
        // Also check if there's a gift card product in orderlines with Rp 0.00
        const orderlines = order.get_orderlines();
        for (const line of orderlines) {
            if (line.is_reward_line && line.reward_id) {
                const reward = this.pos.reward_by_id[line.reward_id];
                if (reward && reward.program_id && reward.program_id.program_type === 'gift_card') {
                    console.log('[DEBUG] Found gift card reward line in orderlines');
                    return true;
                }
            }
        }
        
        return false;
    },

    /**
     * Find payment method with gm_is_dp = True using ORM (Online Mode)
     * Returns null if not found or if multiple methods found
     */
    async _findDpPaymentMethodOnline() {
        try {
            console.log('[DEBUG] Searching for payment method with gm_is_dp = True via ORM...');
            
            // Get payment methods configured for this POS
            const configPaymentMethodIds = this.pos.config.payment_method_ids;
            console.log('[DEBUG] Config payment method IDs:', configPaymentMethodIds);
            
            // Search for payment methods with gm_is_dp = True
            const dpMethodIds = await this.orm.search(
                'pos.payment.method',
                [
                    ['id', 'in', configPaymentMethodIds],
                    ['gm_is_dp', '=', true]
                ],
                { limit: 2 } // Limit to 2 to check if there's more than 1
            );
            
            console.log('[DEBUG] DP method IDs found:', dpMethodIds);
            
            // Only proceed if exactly one method found
            if (dpMethodIds.length !== 1) {
                console.log('[DEBUG] Expected 1 method, found:', dpMethodIds.length);
                return null;
            }
            
            // Get the payment method object from local cache
            const dpMethod = this.payment_methods_from_config.find(
                (method) => method.id === dpMethodIds[0]
            );
            
            console.log('[DEBUG] DP Payment method object:', dpMethod);
            return dpMethod;
            
        } catch (error) {
            console.error('[ERROR] Failed to find DP payment method:', error);
            return null;
        }
    },

    /**
     * Calculate total balance from all redeemed gift cards using ORM
     */
    async _calculateTotalGiftCardBalance(order) {
        let totalBalance = 0;
        const couponIds = [];
        
        // Collect all gift card coupon IDs
        if (order.couponPointChanges) {
            for (const pe of Object.values(order.couponPointChanges)) {
                const program = this.pos.program_by_id[pe.program_id];
                if (program && program.program_type === 'gift_card' && pe.coupon_id > 0) {
                    couponIds.push(pe.coupon_id);
                }
            }
        }
        
        if (order.codeActivatedCoupons && order.codeActivatedCoupons.length > 0) {
            for (const coupon of order.codeActivatedCoupons) {
                const program = this.pos.program_by_id[coupon.program_id];
                if (program && program.program_type === 'gift_card' && coupon.id > 0) {
                    couponIds.push(coupon.id);
                }
            }
        }
        
        console.log('[DEBUG] Gift card coupon IDs to fetch:', couponIds);
        
        if (couponIds.length === 0) {
            return 0;
        }
        
        try {
            // Fetch coupon data from backend using ORM
            const coupons = await this.orm.call(
                'loyalty.card',
                'read',
                [couponIds, ['id', 'points', 'code']]
            );
            
            console.log('[DEBUG] Fetched coupons from backend:', coupons);
            
            // Sum all balances
            for (const coupon of coupons) {
                if (coupon.points) {
                    totalBalance += coupon.points;
                    console.log('[DEBUG] Coupon', coupon.code, 'balance:', coupon.points);
                }
            }
            
            console.log('[DEBUG] Total balance calculated:', totalBalance);
            
        } catch (error) {
            console.error('[ERROR] Failed to fetch coupon balances:', error);
        }
        
        return totalBalance;
    },

    /**
     * Add payment line with gift card payment method and amount
     */
    _addGiftCardPaymentLine(paymentMethod, amount) {
        console.log('[DEBUG] Adding payment line for method:', paymentMethod.name, 'with amount:', amount);
        
        // Check if there are existing payment lines
        const existingLines = [...this.paymentLines];
        console.log('[DEBUG] Existing payment lines:', existingLines.length);
        
        // Remove existing payment lines if any
        for (const line of existingLines) {
            console.log('[DEBUG] Removing existing payment line:', line.cid);
            this.deletePaymentLine(line.cid);
        }
        
        // Add new payment line
        const result = this.addNewPaymentLine(paymentMethod);
        console.log('[DEBUG] Add payment line result:', result);
        
        if (result) {
            // Set the amount after adding the line
            const newLine = this.selectedPaymentLine;
            console.log('[DEBUG] Selected payment line:', newLine);
            
            if (newLine) {
                newLine.set_amount(amount);
                console.log('[DEBUG] Amount set to:', amount);
            }
        }
        
        // Reset number buffer
        this.numberBuffer.reset();
    }
});