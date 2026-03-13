// sales_order_estimate.js
// Adds Corrugated Estimate context on Sales Order forms

frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        if (!frm.doc.corrugated_estimate_ref) return;

        const ref = frm.doc.corrugated_estimate_ref;

        // Show green banner
        frm.dashboard.add_comment(
            `📦 From Corrugated Estimate: <a href="/app/corrugated-estimate/${ref}"><b>${ref}</b></a>`,
            "green", true
        );

        // View Estimate button
        frm.add_custom_button(__("View Estimate"), () => {
            frappe.set_route("Form", "Corrugated Estimate", ref);
        }, __("Corrugated"));

        // View all estimates for this customer
        if (frm.doc.customer) {
            frm.add_custom_button(__("Customer Estimates"), () => {
                frappe.route_options = { customer: frm.doc.customer };
                frappe.set_route("List", "Corrugated Estimate", "List");
            }, __("Corrugated"));
        }
    },
});
