/* =============================================================================
   Corrugated Estimate – form controller
   Handles client-side recalculation of blank size and quantity pricing.
   Server also recalculates on save via corrugated_estimate.py before_save().
   ============================================================================= */
frappe.ui.form.on("Corrugated Estimate", {

	// ── Trigger recalc when any dimension changes ──────────────────────────────
	length_inside: function(frm) { frm.trigger("recalc_blank"); },
	width_inside:  function(frm) { frm.trigger("recalc_blank"); },
	depth_inside:  function(frm) { frm.trigger("recalc_blank"); },
	flute_type:    function(frm) { frm.trigger("recalc_blank"); },
	box_style:     function(frm) { frm.trigger("recalc_blank"); },

	recalc_blank: function(frm) {
		var L = frm.doc.length_inside, W = frm.doc.width_inside, D = frm.doc.depth_inside;
		if (!L || !W || !D) return;

		frappe.call({
			method: "corrugated_estimating.corrugated_estimating.api.get_blank_size",
			args: {
				box_style: frm.doc.box_style || "RSC",
				length_inside: L,
				width_inside:  W,
				depth_inside:  D,
				flute_type: frm.doc.flute_type || "",
			},
			callback: function(r) {
				if (r.message) {
					frm.set_value("blank_length",    r.message.blank_length);
					frm.set_value("blank_width",     r.message.blank_width);
					frm.set_value("blank_area_sqft", r.message.blank_area_sqft);
					frm.trigger("recalc_all_rows");
				}
			}
		});
	},

	// ── Trigger pricing recalc when print method or colors change ─────────────
	print_method: function(frm) { frm.trigger("recalc_all_rows"); },
	num_colors:   function(frm) { frm.trigger("recalc_all_rows"); },

	recalc_all_rows: function(frm) {
		(frm.doc.quantities || []).forEach(function(row) {
			frm.trigger_child("Corrugated Estimate Quantity", "quantity", row.name);
		});
	},
});

// ── Child table – recalc a single row when board cost or markup changes ───────
frappe.ui.form.on("Corrugated Estimate Quantity", {
	quantity:      function(frm, cdt, cdn) { _recalc_row(frm, cdt, cdn); },
	board_cost_msf: function(frm, cdt, cdn) { _recalc_row(frm, cdt, cdn); },
	markup_pct:    function(frm, cdt, cdn) { _recalc_row(frm, cdt, cdn); },
	die_charge:    function(frm, cdt, cdn) { _recalc_row(frm, cdt, cdn); },
	setup_charge:  function(frm, cdt, cdn) { _recalc_row(frm, cdt, cdn); },
});

function _recalc_row(frm, cdt, cdn) {
	var row = frappe.get_doc(cdt, cdn);
	var qty = parseInt(row.quantity) || 0;
	if (!qty) return;

	var blank_area = parseFloat(frm.doc.blank_area_sqft) || 0;
	var board_cost = parseFloat(row.board_cost_msf) || 0;
	var num_colors = parseInt(frm.doc.num_colors) || 0;
	var markup     = parseFloat(row.markup_pct) || 30;

	// Material cost
	var mat_cost = (blank_area / 1000) * board_cost * qty;
	frappe.model.set_value(cdt, cdn, "material_cost", Math.round(mat_cost * 100) / 100);

	// Fetch print method charges then complete calc
	if (frm.doc.print_method) {
		frappe.db.get_doc("Corrugated Print Method", frm.doc.print_method).then(function(pm) {
			var plates = num_colors * (pm.per_color_plate_charge || 0);
			frappe.model.set_value(cdt, cdn, "plate_charges", Math.round(plates * 100) / 100);
			_finish_row_calc(cdt, cdn, mat_cost, plates, row.die_charge, row.setup_charge, qty, markup);
		});
	} else {
		_finish_row_calc(cdt, cdn, mat_cost, row.plate_charges, row.die_charge, row.setup_charge, qty, markup);
	}
}

function _finish_row_calc(cdt, cdn, mat_cost, plate_charges, die_charge, setup_charge, qty, markup) {
	var total = (mat_cost || 0) + (plate_charges || 0) + (die_charge || 0) + (setup_charge || 0);
	var sell  = total * (1 + (markup / 100));

	frappe.model.set_value(cdt, cdn, "total_cost",      Math.round(total * 100) / 100);
	frappe.model.set_value(cdt, cdn, "sell_price_m",    Math.round((sell / qty) * 1000 * 100) / 100);
	frappe.model.set_value(cdt, cdn, "sell_price_unit", Math.round((sell / qty) * 1000000) / 1000000);
	frappe.model.set_value(cdt, cdn, "extended_total",  Math.round(sell * 100) / 100);
}
