/* =============================================================================
   Corrugated Estimating – Customer form: Estimate History tab
   Adds a "Corrugated Estimates" section to the ERPNext Customer form showing
   all estimates linked to this customer.
   ============================================================================= */
frappe.ui.form.on("Customer", {
	refresh: function(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Corrugated Estimates"), function() {
			frappe.set_route("List", "Corrugated Estimate", { customer: frm.doc.name });
		}, __("View"));

		frm.add_custom_button(__("New Estimate"), function() {
			frappe.new_doc("Corrugated Estimate", { customer: frm.doc.name });
		}, __("Create"));

		// Inject estimate count badge
		frappe.call({
			method: "corrugated_estimating.corrugated_estimating.api.get_estimates_for_customer",
			args: { customer: frm.doc.name },
			callback: function(r) {
				if (!r.message) return;
				var estimates = r.message;
				if (!estimates.length) return;

				// Build a summary table
				var rows = estimates.slice(0, 10).map(function(e) {
					var dims = (e.length_inside && e.width_inside && e.depth_inside)
						? e.length_inside + " × " + e.width_inside + " × " + e.depth_inside
						: "—";
					return '<tr>' +
						'<td><a href="/app/corrugated-estimate/' + e.name + '">' + e.name + '</a></td>' +
						'<td>' + (e.estimate_date || "—") + '</td>' +
						'<td><span class="indicator-pill ' + _statusColor(e.status) + '">' + e.status + '</span></td>' +
						'<td>' + (e.box_style || "—") + '</td>' +
						'<td>' + dims + '</td>' +
					'</tr>';
				}).join("");

				var html = '<div class="ce-est-wrap" style="margin:16px 0;">' +
					'<h6 style="font-weight:700;color:#374151;margin-bottom:8px;">' +
						'📦 Corrugated Estimates (' + estimates.length + ')' +
					'</h6>' +
					'<table class="table table-bordered table-sm" style="font-size:12px;">' +
						'<thead><tr><th>Estimate</th><th>Date</th><th>Status</th><th>Style</th><th>Dimensions</th></tr></thead>' +
						'<tbody>' + rows + '</tbody>' +
					'</table>' +
					(estimates.length > 10
						? '<a href="/app/corrugated-estimate?customer=' + frm.doc.name + '" style="font-size:12px;">View all ' + estimates.length + ' estimates →</a>'
						: '') +
				'</div>';

				// Append after standard customer details
				frm.page.body.find(".ce-est-wrap").remove();
				frm.page.body.find(".form-page").append(html);
			}
		});
	}
});

function _statusColor(status) {
	var map = {
		"Draft": "gray",
		"Sent": "blue",
		"Accepted": "green",
		"Rejected": "red",
		"Expired": "orange",
	};
	return map[status] || "gray";
}
