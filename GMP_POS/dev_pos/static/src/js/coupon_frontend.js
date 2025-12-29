/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

patch(PaymentScreen.prototype, {
    /**
     * ✅ SOLUSI: Override _postPushOrderResolve
     * Ikuti pattern Odoo - ambil gift_card_code dari payload confirm_coupon_programs
     */
    async _postPushOrderResolve(order, server_ids) {
        console.log("=".repeat(80));
        console.log("🎁🎁🎁 [GIFT CARD] _postPushOrderResolve START");
        console.log("🎁 [GIFT CARD] Order:", order ? order.name : 'No order');
        console.log("🎁 [GIFT CARD] Server IDs:", server_ids);
        console.log("🎁 [GIFT CARD] Order object:", order);
        
        if (!order) {
            console.error("❌❌❌ [GIFT CARD] No order object!");
            console.log("=".repeat(80));
            return await super._postPushOrderResolve(...arguments);
        }
        
        // ====================================================
        // STEP 1: Call parent first
        // ====================================================
        console.log("🎁 [GIFT CARD] Calling parent _postPushOrderResolve...");
        
        let result;
        try {
            result = await super._postPushOrderResolve(...arguments);
            console.log("🎁 [GIFT CARD] Parent returned result:", result);
        } catch (error) {
            console.error("❌❌❌ [GIFT CARD] Error in parent _postPushOrderResolve:", error);
            console.log("=".repeat(80));
            throw error;
        }
        
        // ====================================================
        // STEP 2: Get server_ids if not provided
        // ====================================================
        let orderId = null;
        
        if (!server_ids || server_ids.length === 0) {
            console.warn("⚠️ [GIFT CARD] No server_ids from parameter");
            
            // Try to get from result
            if (result && result.order_id) {
                orderId = result.order_id;
                console.log("🎁 [GIFT CARD] Got order_id from result:", orderId);
            }
            // Try to get from order
            else if (order.server_id) {
                orderId = order.server_id;
                console.log("🎁 [GIFT CARD] Got order_id from order.server_id:", orderId);
            }
            // Try to get from order.id
            else if (order.id && typeof order.id === 'number' && order.id > 0) {
                orderId = order.id;
                console.log("🎁 [GIFT CARD] Got order_id from order.id:", orderId);
            }
            else {
                console.error("❌❌❌ [GIFT CARD] Cannot find order ID anywhere!");
                console.log("🎁 [GIFT CARD] Checking result structure:", result);
                console.log("=".repeat(80));
                return result;
            }
        } else {
            orderId = server_ids[0];
            console.log("🎁 [GIFT CARD] Using server_ids[0]:", orderId);
        }
        
        console.log("🎁 [GIFT CARD] Final orderId to use:", orderId);
        
        // ====================================================
        // STEP 3: Wait a moment for order to be fully created
        // ====================================================
        console.log("🎁 [GIFT CARD] Waiting 1 second for order creation...");
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // ====================================================
        // STEP 4: Fetch loyalty cards from database
        // ====================================================
        console.log(`🎁 [GIFT CARD] Fetching loyalty cards for order ${orderId}...`);
        
        let giftCardCodes = [];
        
        try {
            // Method 1: Search loyalty cards
            const loyaltyCards = await this.orm.call(
                'loyalty.card',
                'search_read',
                [
                    [['source_pos_order_id', '=', orderId]], 
                    ['code', 'points', 'program_id', 'program_type']
                ],
                {}
            );
            
            console.log(`🎁 [GIFT CARD] Found ${loyaltyCards.length} loyalty cards:`, loyaltyCards);
            
            if (loyaltyCards && loyaltyCards.length > 0) {
                // Filter gift cards only
                giftCardCodes = loyaltyCards
                    .filter(card => {
                        const isGiftCard = card.program_id && 
                                          card.program_id.length >= 2 && 
                                          card.program_id[1] && 
                                          card.program_id[1].toLowerCase().includes('gift');
                        
                        if (isGiftCard && card.code) {
                            console.log(`🎁 [GIFT CARD] Found gift card: ${card.code}`);
                            return true;
                        }
                        return false;
                    })
                    .map(card => card.code);
                
                console.log(`🎁 [GIFT CARD] Gift card codes found:`, giftCardCodes);
            }
            
        } catch (error) {
            console.error(`❌ [GIFT CARD] Error fetching loyalty cards:`, error);
        }
        
        // ====================================================
        // STEP 5: Try alternative method if no codes found
        // ====================================================
        if (giftCardCodes.length === 0) {
            console.log("🎁 [GIFT CARD] No gift cards found via loyalty.card, trying pos.order...");
            
            try {
                // Directly fetch from pos.order
                const orderData = await this.orm.call(
                    'pos.order',
                    'search_read',
                    [
                        [['id', '=', orderId]], 
                        ['gift_card_code']
                    ],
                    {}
                );
                
                console.log("🎁 [GIFT CARD] Order data from database:", orderData);
                
                if (orderData && orderData.length > 0 && orderData[0].gift_card_code) {
                    const codes = orderData[0].gift_card_code.split(',').map(c => c.trim()).filter(c => c);
                    giftCardCodes = codes;
                    console.log(`🎁 [GIFT CARD] Got gift_card_code from order:`, giftCardCodes);
                }
                
            } catch (error) {
                console.error(`❌ [GIFT CARD] Error fetching order:`, error);
            }
        }
        
        // ====================================================
        // STEP 6: Set gift card code to order
        // ====================================================
        if (giftCardCodes.length > 0) {
            const giftCardCodeStr = giftCardCodes.join(', ');
            
            console.log(`✅✅✅ [GIFT CARD SUCCESS] Setting gift card code: ${giftCardCodeStr}`);
            
            // Set to order
            order.gift_card_code = giftCardCodeStr;
            
            // Force update receipt data
            if (order.export_for_printing) {
                const receiptData = order.export_for_printing();
                console.log("🎁 [RECEIPT] Updated receipt data with gift_card_code:", receiptData.gift_card_code);
            }
            
            // Show notification to user
            if (this.env.services.notification) {
                this.env.services.notification.add(
                    `Gift Card Created: ${giftCardCodeStr}`,
                    { type: 'success', title: 'Gift Card' }
                );
            }
        } else {
            console.warn("⚠️ [GIFT CARD] No gift card codes found for this order");
            order.gift_card_code = '';
        }
        
        // ====================================================
        // STEP 7: Debug final state
        // ====================================================
        console.log("🎁 [GIFT CARD] Final order state:");
        console.log("🎁 [GIFT CARD] - name:", order.name);
        console.log("🎁 [GIFT CARD] - gift_card_code:", order.gift_card_code);
        console.log("🎁 [GIFT CARD] - server_id:", order.server_id);
        
        if (order.export_for_printing) {
            const finalReceipt = order.export_for_printing();
            console.log("🎁 [RECEIPT] Final receipt gift_card_code:", finalReceipt.gift_card_code);
        }
        
        console.log("=".repeat(80));
        console.log("🎁🎁🎁 [GIFT CARD] _postPushOrderResolve COMPLETED");
        console.log("=".repeat(80));
        
        return result;
    },
    
    /**
     * ✅ NEW: Override _finalizeOrder to ensure gift card code is captured
     */
    async _finalizeOrder() {
        console.log("🎁 [FINALIZE] _finalizeOrder called");
        
        const result = await super._finalizeOrder(...arguments);
        
        console.log("🎁 [FINALIZE] Result:", result);
        
        // If there's a gift card in the order, ensure code is captured
        const order = this.currentOrder;
        if (order) {
            const hasGiftCard = order.get_orderlines().some(line => 
                line.reward_id && 
                line.reward_id.program_id && 
                line.reward_id.program_id.program_type === 'gift_card'
            );
            
            if (hasGiftCard && !order.gift_card_code) {
                console.log("🎁 [FINALIZE] Order has gift card but no code, setting placeholder");
                order.gift_card_code = 'Generating...';
            }
        }
        
        return result;
    },
    
    /**
     * ✅ NEW: Helper to check if order has gift card
     */
    _orderHasGiftCard(order) {
        if (!order || !order.get_orderlines) return false;
        
        const lines = order.get_orderlines();
        return lines.some(line => 
            line.reward_id && 
            line.reward_id.program_id && 
            line.reward_id.program_id.program_type === 'gift_card'
        );
    }
});