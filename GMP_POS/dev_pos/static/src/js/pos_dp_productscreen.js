/** @odoo-module **/

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
    /**
     * Override _getRewardLineValues to set gift card product price to 0
     * before the line is created
     */
    _getRewardLineValues(args) {
        const rewardLines = super._getRewardLineValues(args);
        const reward = args["reward"];
        
        // Check if this is a gift_card program
        if (reward && reward.program_id && reward.program_id.program_type === 'gift_card') {
            // If rewardLines is an array, set price to 0 for all lines
            if (Array.isArray(rewardLines)) {
                for (const line of rewardLines) {
                    line.price = 0;
                }
            }
        }
        
        return rewardLines;
    },

    /**
     * Override _getRewardLineValuesProduct specifically for product rewards
     */
    _getRewardLineValuesProduct(args) {
        const rewardLines = super._getRewardLineValuesProduct(args);
        const reward = args["reward"];
        
        // Check if this is a gift_card program
        if (reward && reward.program_id && reward.program_id.program_type === 'gift_card') {
            // If rewardLines is an array, set price to 0 for all lines
            if (Array.isArray(rewardLines)) {
                for (const line of rewardLines) {
                    line.price = 0;
                }
            }
        }
        
        return rewardLines;
    },

    /**
     * Override _applyReward to prevent duplicate gift card rewards
     */
    _applyReward(reward, coupon_id, args) {
        // Check if this is a gift_card program
        if (reward && reward.program_id && reward.program_id.program_type === 'gift_card') {
            // Check if this gift card reward is already applied for this coupon
            const existingRewardLine = this.get_orderlines().find(line => 
                line.is_reward_line && 
                line.reward_id === reward.id && 
                line.coupon_id === coupon_id
            );
            
            // If already exists, don't apply again
            if (existingRewardLine) {
                return true;
            }
        }
        
        // Call parent method
        return super._applyReward(reward, coupon_id, args);
    },

    /**
     * Override getClaimableRewards to prevent gift card from being auto-claimed repeatedly
     */
    getClaimableRewards(coupon_id = false, program_id = false, auto = false) {
        const claimableRewards = super.getClaimableRewards(coupon_id, program_id, auto);
        
        // Filter out gift card rewards that are already claimed
        return claimableRewards.filter(({ coupon_id, reward }) => {
            if (reward.program_id.program_type === 'gift_card') {
                // Check if this gift card reward is already in orderlines
                const alreadyClaimed = this.get_orderlines().some(line => 
                    line.is_reward_line && 
                    line.reward_id === reward.id && 
                    line.coupon_id === coupon_id
                );
                return !alreadyClaimed;
            }
            return true;
        });
    }
});