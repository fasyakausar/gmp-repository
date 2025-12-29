/** @odoo-module */

import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { TextInputPopup } from "@point_of_sale/app/utils/input_popups/text_input_popup";

patch(TicketScreen.prototype, {
    
    async onDoRefund() {
        const order = this.getSelectedOrder();

        if (!order) {
            this._state.ui.highlightHeaderNote = !this._state.ui.highlightHeaderNote;
            return;
        }

        // Check if order is locked (synced/paid)
        if (!order.locked) {
            await this.popup.add(ErrorPopup, {
                title: _t("Cannot Create Return Approval"),
                body: _t("Only paid orders can be returned. Please complete the payment first."),
            });
            return;
        }

        // Get partner
        const partner = order.get_partner();

        // Get refundable details using the existing method from base code
        const allToRefundDetails = this._getRefundableDetails(partner);
        
        if (allToRefundDetails.length === 0) {
            this._state.ui.highlightHeaderNote = !this._state.ui.highlightHeaderNote;
            await this.popup.add(ErrorPopup, {
                title: _t("No Items Selected"),
                body: _t("Please select items to return by clicking on them and setting the quantity."),
            });
            return;
        }

        // Prompt for return reason
        const { confirmed, payload: returnReason } = await this.popup.add(TextInputPopup, {
            title: _t("Return Reason"),
            placeholder: _t("Please provide a reason for this return..."),
            rows: 4,
        });

        if (!confirmed || !returnReason || returnReason.trim() === '') {
            await this.popup.add(ErrorPopup, {
                title: _t("Return Reason Required"),
                body: _t("You must provide a reason for the return."),
            });
            return;
        }

        // Prepare return approval line data from refundable details
        const lineData = allToRefundDetails.map(detail => {
            return [0, 0, {
                gm_product_id: detail.orderline.productId,
                gm_qty: Math.abs(detail.qty), // Ensure positive quantity
            }];
        });

        // Prepare return approval data
        const returnApprovalData = {
            gm_pos_order_id: order.backendId, // Use backendId for synced orders
            gm_return_reason: returnReason.trim(),
            gm_line_ids: lineData,
        };

        console.log("Creating return approval with data:", returnApprovalData);

        try {
            // Create return approval document using ORM service
            const returnApprovalId = await this.orm.call(
                'return.approval',
                'create',
                [returnApprovalData]
            );

            console.log("Return approval created with ID:", returnApprovalId);

            // Show success message
            await this.popup.add(ErrorPopup, {
                title: _t("Success"),
                body: _t("Return approval document has been created successfully. Document will be processed after approval."),
            });

            // Clear the refund selections for this order
            for (const detail of allToRefundDetails) {
                if (this.pos.toRefundLines[detail.orderline.id]) {
                    delete this.pos.toRefundLines[detail.orderline.id];
                }
            }

            // Refresh the order list if viewing synced orders
            if (this._state.ui.filter === "SYNCED") {
                await this._fetchSyncedOrders();
            }

            // Close ticket screen and return to product screen
            this.closeTicketScreen();

        } catch (error) {
            console.error("Error creating return approval:", error);
            
            // Extract error message
            let errorMessage = "Unknown error";
            if (error.data && error.data.message) {
                errorMessage = error.data.message;
            } else if (error.message) {
                errorMessage = error.message;
            }
            
            await this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: _t("Failed to create return approval: %s", errorMessage),
            });
        }
    },

});