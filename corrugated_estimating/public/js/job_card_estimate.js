// job_card_estimate.js
// Adds Corrugated Estimate context on Job Card forms — shows box spec details
// so production team has the exact dimensions/specs while running the job.

frappe.ui.form.on("Job Card", {
    refresh(frm) {
        if (!frm.doc.corrugated_estimate_ref) return;

        const ref = frm.doc.corrugated_estimate_ref;

        // Show banner with estimate ref
        frm.dashboard.add_comment(
            `📦 Corrugated Estimate: <a href="/app/corrugated-estimate/${ref}"><b>${ref}</b></a>`,
            "blue", true
        );

        // View Estimate button
        frm.add_custom_button(__("View Estimate"), () => {
            frappe.set_route("Form", "Corrugated Estimate", ref);
        }, __("Corrugated"));

        // Inline spec card — load estimate and show box spec inline
        frm.add_custom_button(__("Show Box Spec"), () => {
            _show_box_spec(ref);
        }, __("Corrugated"));
    },
});

function _show_box_spec(estimate_name) {
    frappe.call({
        method: "frappe.client.get",
        args: { doctype: "Corrugated Estimate", name: estimate_name },
        callback(r) {
            if (!r.message) return;
            const e = r.message;
            const dims = [
                e.length_inside ? `L ${e.length_inside}"` : null,
                e.width_inside  ? `W ${e.width_inside}"` : null,
                e.depth_inside  ? `D ${e.depth_inside}"` : null,
            ].filter(Boolean).join(" × ");

            frappe.msgprint({
                title: __("Box Spec — {0}", [estimate_name]),
                message: `
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
                        <div>
                            <h6 style="color:#555;font-weight:600">Box Specification</h6>
                            <table class="table table-condensed" style="font-size:12px">
                                <tr><td><b>Style</b></td><td>${e.box_style || "—"}</td></tr>
                                <tr><td><b>Flute</b></td><td>${e.flute_type || "—"}</td></tr>
                                <tr><td><b>Grade</b></td><td>${e.board_grade || "—"}</td></tr>
                                <tr><td><b>Dimensions (ID)</b></td><td>${dims || "—"}</td></tr>
                                <tr><td><b>Blank Size</b></td><td>${e.blank_length || "?"}" × ${e.blank_width || "?"}"</td></tr>
                                <tr><td><b>Area</b></td><td>${e.blank_area_sqft ? e.blank_area_sqft.toFixed(3) + " ft²" : "—"}</td></tr>
                            </table>
                        </div>
                        <div>
                            <h6 style="color:#555;font-weight:600">Print Specification</h6>
                            <table class="table table-condensed" style="font-size:12px">
                                <tr><td><b>Colors</b></td><td>${e.num_colors || 0}</td></tr>
                                <tr><td><b>Method</b></td><td>${e.print_method || "—"}</td></tr>
                                <tr><td><b>Coating</b></td><td>${e.coating || "None"}</td></tr>
                                <tr><td><b>Wax/Water</b></td><td>${e.wax_water_resist ? "Yes" : "No"}</td></tr>
                                <tr><td><b>Die-Cut</b></td><td>${e.die_cut_special ? "Yes" : "No"}</td></tr>
                            </table>
                        </div>
                    </div>
                    ${e.customer_notes ? `<div style="margin-top:12px;background:#fffdf0;padding:10px;border-radius:6px;font-size:12px"><b>Customer Notes:</b> ${e.customer_notes}</div>` : ""}
                    <div style="margin-top:8px">
                        <a href="/app/corrugated-estimate/${estimate_name}" class="btn btn-xs btn-default">
                            Open Full Estimate
                        </a>
                    </div>
                `,
                indicator: "blue",
            });
        },
    });
}
