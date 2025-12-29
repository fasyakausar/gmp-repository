/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Order } from "@point_of_sale/app/store/models";

patch(Order.prototype, {
    /**
     * ✅ SOLUSI: Tambahkan gift_card_code ke init_from_JSON
     * Ini akan dipanggil ketika order di-load dari database
     */
    init_from_JSON(json) {
        console.log("🎁 [ORDER] init_from_JSON called");
        console.log("🎁 [ORDER] JSON keys:", Object.keys(json));
        
        super.init_from_JSON(json);
        
        // ✅ Set gift_card_code jika ada di JSON
        this.gift_card_code = json.gift_card_code || '';
        
        if (this.gift_card_code) {
            console.log(`🎁 [ORDER INIT] Gift card code loaded: ${this.gift_card_code}`);
        } else {
            console.log(`🎁 [ORDER INIT] No gift card code in JSON`);
        }
        
        // Debug: log all properties
        console.log("🎁 [ORDER] Current order properties:");
        console.log("🎁 [ORDER] - name:", this.name);
        console.log("🎁 [ORDER] - id:", this.id);
        console.log("🎁 [ORDER] - server_id:", this.server_id);
        console.log("🎁 [ORDER] - gift_card_code:", this.gift_card_code);
    },
    
    /**
     * ✅ SOLUSI: Tambahkan gift_card_code ke export_for_printing
     * Ini akan memastikan gift_card_code tersedia di receipt
     */
    export_for_printing() {
        console.log("🎁 [RECEIPT] export_for_printing called");
        
        const result = super.export_for_printing(...arguments);
        
        // ✅ Tambahkan gift_card_code ke data receipt
        result.gift_card_code = this.gift_card_code || '';
        
        console.log("🎁 [RECEIPT] Exporting with gift_card_code:", result.gift_card_code);
        console.log("🎁 [RECEIPT] Full receipt data keys:", Object.keys(result));
        
        return result;
    },
    
    /**
     * ✅ SOLUSI: Tambahkan gift_card_code ke export_as_JSON
     * Ini untuk menyimpan ke localStorage
     */
    export_as_JSON() {
        console.log("🎁 [EXPORT] export_as_JSON called");
        
        const json = super.export_as_JSON(...arguments);
        
        // ✅ Simpan gift_card_code
        json.gift_card_code = this.gift_card_code || '';
        
        console.log("🎁 [EXPORT] Saving gift_card_code to JSON:", json.gift_card_code);
        
        return json;
    },
    
    /**
     * ✅ NEW: Method to set gift card code
     */
    setGiftCardCode(code) {
        console.log(`🎁 [SET] Setting gift card code: ${code}`);
        this.gift_card_code = code;
        
        // Trigger update
        if (this._setGiftCardCode) {
            this._setGiftCardCode(code);
        }
    },
    
    /**
     * ✅ NEW: Method to get gift card code
     */
    getGiftCardCode() {
        return this.gift_card_code || '';
    }
});