// /** @odoo-module **/

// import { patch } from "@web/core/utils/patch";
// import { PosStore } from "@point_of_sale/app/store/pos_store";

// patch(PosStore.prototype, {
//     /**
//      * ✅ SOLUSI: Fetch dari loyalty.card dengan wait & retry
//      * confirm_coupon_programs berjalan async SETELAH create_from_ui
//      */
//     async push_single_order(order, opts) {
//         console.log("🔍 [GIFT CARD] push_single_order START for:", order.name);
        
//         // Call parent method
//         const result = await super.push_single_order(...arguments);
        
//         console.log("🔍 [GIFT CARD] push_single_order END, result:", result);
        
//         if (result && result.length > 0 && result[0].id) {
//             const orderId = result[0].id;
            
//             console.log(`🔍 [GIFT CARD] Starting fetch process for order ${orderId}...`);
            
//             // ✅ RETRY MECHANISM: Coba beberapa kali dengan delay
//             const maxAttempts = 6; // 6 attempts
//             const delayMs = 500; // 500ms per attempt
            
//             for (let attempt = 1; attempt <= maxAttempts; attempt++) {
//                 console.log(`🔍 [GIFT CARD] Attempt ${attempt}/${maxAttempts} - waiting ${delayMs}ms...`);
                
//                 // Wait before each attempt
//                 await new Promise(resolve => setTimeout(resolve, delayMs));
                
//                 try {
//                     // Fetch dari loyalty.card berdasarkan source_pos_order_id
//                     const loyaltyCards = await this.orm.call(
//                         'loyalty.card',
//                         'search_read',
//                         [[['source_pos_order_id', '=', orderId]], ['code', 'points', 'program_id']],
//                         {}
//                     );
                    
//                     console.log(`🔍 [GIFT CARD] Attempt ${attempt} - Found loyalty cards:`, loyaltyCards);
                    
//                     if (loyaltyCards && loyaltyCards.length > 0) {
//                         // Ambil semua codes
//                         const giftCardCodes = loyaltyCards
//                             .filter(card => card.code)
//                             .map(card => card.code);
                        
//                         if (giftCardCodes.length > 0) {
//                             order.gift_card_code = giftCardCodes.join(', ');
//                             console.log(`🎁 [GIFT CARD SUCCESS] Got codes on attempt ${attempt}: ${order.gift_card_code}`);
//                             console.log(`🎁 [GIFT CARD SUCCESS] Total cards: ${giftCardCodes.length}`);
//                             break; // Berhasil, keluar dari loop
//                         }
//                     }
                    
//                     // Jika attempt terakhir dan masih belum ada
//                     if (attempt === maxAttempts) {
//                         console.log(`ℹ️ [GIFT CARD] No loyalty cards after ${maxAttempts} attempts (normal order)`);
//                     }
                    
//                 } catch (error) {
//                     console.error(`❌ [GIFT CARD] Error on attempt ${attempt}:`, error);
//                 }
//             }
//         }
        
//         console.log(`🔍 [GIFT CARD] Final order.gift_card_code: ${order.gift_card_code}`);
        
//         return result;
//     },
// });