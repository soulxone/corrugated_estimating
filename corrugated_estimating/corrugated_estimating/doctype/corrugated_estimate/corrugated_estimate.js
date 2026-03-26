/* =============================================================================
   Corrugated Estimate – Form Controller  (v2 Full Cost Model)
   ============================================================================
   Mirrors the Welch Wyse Box Estimator HTML tool inside Frappe.

   Cost model:  Material → Converting → Overhead → Amort.Fixed → Freight → COGS
   Sell price:  COGS / (1 − target_margin%)   or   COGS × (1 + markup%)

   All recalculation is driven server-side via API (uses Settings machine rates).
   The form responds instantly to any change that affects the cost breakdown.
   ============================================================================= */

// ── Field trigger lists ──────────────────────────────────────────────────────

const _BLANK_TRIGGERS = [
    "length_inside", "width_inside", "depth_inside", "flute_type", "box_style",
];

const _ROW_TRIGGERS = [
    "waste_pct", "overhead_pct", "target_margin_pct",
    "print_addon_per_color_msf", "num_colors", "print_method",
    "tooling_cost", "setup_cost",
    "freight_mode", "freight_manual_per_unit",
    "wax_water_resist", "die_cut_special",
    "board_grade",
];

// ── Parent form handlers ──────────────────────────────────────────────────────

frappe.ui.form.on("Corrugated Estimate", {

    // ── On form load: apply default cost model values ──────────────────────
    onload: function(frm) {
        if (frm.is_new()) {
            frappe.call({
                method: "corrugated_estimating.corrugated_estimating.api.get_estimating_settings",
                callback: function(r) {
                    if (!r.message) return;
                    var s = r.message;
                    if (!frm.doc.waste_pct)              frm.set_value("waste_pct",              s.default_waste_pct         || 8);
                    if (!frm.doc.overhead_pct)           frm.set_value("overhead_pct",           s.default_overhead_pct      || 15);
                    if (!frm.doc.target_margin_pct)      frm.set_value("target_margin_pct",      s.default_target_margin_pct || 35);
                    if (!frm.doc.board_cost_default_msf) frm.set_value("board_cost_default_msf", s.default_board_cost_msf    || 180);
                    if (!frm.doc.print_addon_per_color_msf) frm.set_value("print_addon_per_color_msf", s.print_addon_default || 4);
                }
            });
        }
    },

    // ── Custom buttons ─────────────────────────────────────────────────────
    refresh: function(frm) {
        if (!frm.is_new()) {
            // ── Routing & Layout buttons ──────────────────────────────────
            frm.add_custom_button(__("Compute Routing"), function() {
                frappe.call({
                    method: "corrugated_estimating.corrugated_estimating.api.get_machine_routing",
                    args: { estimate_name: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Computing machine routing..."),
                    callback: function(r) {
                        frm.reload_doc();
                        if (r.message) {
                            frappe.show_alert({
                                message: __("Routing computed: {0} step(s)", [r.message.steps.length]),
                                indicator: "green"
                            }, 5);
                        }
                    }
                });
            }, __("Routing"));

            if (frm.doc.die_layout_outs) {
                frm.add_custom_button(__("View Die Layout"), function() {
                    window.location.href = "/app/die-layout-viewer?estimate=" + encodeURIComponent(frm.doc.name);
                }, __("Routing"));
            }

            frm.add_custom_button(__("Capable Machines"), function() {
                _show_capable_machines(frm);
            }, __("Routing"));

            frm.add_custom_button(__("Routing Summary"), function() {
                _show_routing_summary(frm);
            }, __("Routing"));

            // ── CAD File buttons ──────────────────────────────────────────
            frm.add_custom_button(__("Generate CAD"), function() {
                frappe.call({
                    method: "corrugated_estimating.corrugated_estimating.api.generate_cad_file",
                    args: { estimate_name: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Generating DXF file..."),
                    callback: function(r) {
                        if (r.message && r.message.status === "success") {
                            frappe.show_alert({message: __("CAD file generated"), indicator: "green"}, 5);
                            frm.reload_doc();
                        } else {
                            frappe.msgprint(r.message ? r.message.message : "Generation failed");
                        }
                    }
                });
            }, __("CAD"));

            if (frm.doc.cad_file) {
                frm.add_custom_button(__("Download DXF"), function() {
                    window.open(frm.doc.cad_file);
                }, __("CAD"));
            }

            frm.add_custom_button(__("Die Line Studio"), function() {
                window.location.href = "/app/die-line-studio?estimate=" + encodeURIComponent(frm.doc.name);
            }, __("CAD"));

            // ── Estimating tools ──────────────────────────────────────────
            frm.add_custom_button(__("Sensitivity Analysis"), function() {
                _show_sensitivity_dialog(frm);
            }, __("Estimating"));

            frm.add_custom_button(__("Print Cost Report"), function() {
                _print_cost_report(frm);
            }, __("Estimating"));

            // ── Integration buttons ─────────────────────────────────────
            // Convert to Sales Order
            if (frm.doc.status !== "Rejected" && !frm.doc.sales_order_ref) {
                frm.add_custom_button(__("Convert to Sales Order"), function() {
                    _convert_to_sales_order(frm);
                }, __("Integrate"));
            }
            if (frm.doc.sales_order_ref) {
                frm.add_custom_button(__("View Sales Order"), function() {
                    frappe.set_route("Form", "Sales Order", frm.doc.sales_order_ref);
                }, __("Integrate"));
                frm.dashboard.add_comment(
                    `✓ Sales Order: <a href="/app/sales-order/${frm.doc.sales_order_ref}">${frm.doc.sales_order_ref}</a>`,
                    "green", true
                );
            }

            // CRM links
            if (frm.doc.crm_lead) {
                frm.add_custom_button(__("View CRM Lead"), function() {
                    window.open(`/crm/leads/${frm.doc.crm_lead}`, "_blank");
                }, __("Integrate"));
            }
            if (frm.doc.crm_deal) {
                frm.add_custom_button(__("View CRM Deal"), function() {
                    window.open(`/crm/deals/${frm.doc.crm_deal}`, "_blank");
                }, __("Integrate"));
            }

            // Job Cards linked to this estimate
            frm.add_custom_button(__("Job Cards"), function() {
                frappe.route_options = { corrugated_estimate_ref: frm.doc.name };
                frappe.set_route("List", "Job Card", "List");
            }, __("Integrate"));

            // Inventory check for board material
            if (frm.doc.board_grade) {
                frm.add_custom_button(__("Check Board Stock"), function() {
                    _check_board_stock(frm);
                }, __("Integrate"));
            }
        }

        // Status badge colors
        const statusColors = {
            "Draft":    "grey",
            "Sent":     "blue",
            "Accepted": "green",
            "Rejected": "red",
            "Expired":  "orange"
        };
        if (frm.doc.status && statusColors[frm.doc.status]) {
            frm.page.set_indicator(frm.doc.status, statusColors[frm.doc.status]);
        }
    },

    // ── Blank-size triggers ────────────────────────────────────────────────
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
                box_style:     frm.doc.box_style || "RSC",
                length_inside: L,
                width_inside:  W,
                depth_inside:  D,
                flute_type:    frm.doc.flute_type || "",
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

    // ── Cost-model triggers ────────────────────────────────────────────────
    waste_pct:                function(frm) { frm.trigger("recalc_all_rows"); },
    overhead_pct:             function(frm) { frm.trigger("recalc_all_rows"); },
    target_margin_pct:        function(frm) { frm.trigger("recalc_all_rows"); },
    print_addon_per_color_msf:function(frm) { frm.trigger("recalc_all_rows"); },
    num_colors:               function(frm) { frm.trigger("recalc_all_rows"); },
    print_method:             function(frm) { frm.trigger("recalc_all_rows"); },
    tooling_cost:             function(frm) { frm.trigger("recalc_all_rows"); },
    setup_cost:               function(frm) { frm.trigger("recalc_all_rows"); },
    freight_mode:             function(frm) { frm.trigger("recalc_all_rows"); },
    freight_manual_per_unit:  function(frm) { frm.trigger("recalc_all_rows"); },
    wax_water_resist:         function(frm) { frm.trigger("recalc_all_rows"); },
    die_cut_special:          function(frm) { frm.trigger("recalc_all_rows"); },
    board_grade:              function(frm) { frm.trigger("recalc_all_rows"); },
    board_cost_default_msf:   function(frm) { frm.trigger("recalc_all_rows"); },

    recalc_all_rows: function(frm) {
        if (!frm.doc.blank_area_sqft) return;
        (frm.doc.quantities || []).forEach(function(row) {
            _recalc_row(frm, row.doctype, row.name);
        });
    },
});


// ── Child table handlers ──────────────────────────────────────────────────────

frappe.ui.form.on("Corrugated Estimate Quantity", {
    quantity:      function(frm, cdt, cdn) { _recalc_row(frm, cdt, cdn); },
    board_cost_msf:function(frm, cdt, cdn) { _recalc_row(frm, cdt, cdn); },
    markup_pct:    function(frm, cdt, cdn) { _recalc_row(frm, cdt, cdn); },
    die_charge:    function(frm, cdt, cdn) { _recalc_row(frm, cdt, cdn); },
    plate_charges: function(frm, cdt, cdn) { _recalc_row(frm, cdt, cdn); },
    setup_charge:  function(frm, cdt, cdn) { _recalc_row(frm, cdt, cdn); },
});


// ── Core recalc function (calls server API) ───────────────────────────────────

function _recalc_row(frm, cdt, cdn) {
    var row = frappe.get_doc(cdt, cdn);
    if (!row || !row.quantity) return;

    var blank_area  = parseFloat(frm.doc.blank_area_sqft) || 0;
    if (!blank_area) return;

    // Use per-row board cost if set, else use estimate-level default
    var board_cost  = parseFloat(row.board_cost_msf) || parseFloat(frm.doc.board_cost_default_msf) || 180;

    frappe.call({
        method: "corrugated_estimating.corrugated_estimating.api.calculate_row",
        args: {
            quantity:                  row.quantity,
            blank_area_sqft:           blank_area,
            board_cost_msf:            board_cost,
            waste_pct:                 frm.doc.waste_pct              || 8,
            num_colors:                frm.doc.num_colors             || 0,
            print_addon_per_color_msf: frm.doc.print_addon_per_color_msf || 4,
            wax_treat:                 frm.doc.wax_water_resist ? 1 : 0,
            die_cut:                   frm.doc.die_cut_special ? 1 : 0,
            overhead_pct:              frm.doc.overhead_pct           || 15,
            target_margin_pct:         frm.doc.target_margin_pct      || 35,
            tooling_cost:              frm.doc.tooling_cost           || 0,
            setup_cost:                frm.doc.setup_cost             || 0,
            freight_mode:              frm.doc.freight_mode           || "LTL",
            freight_manual_per_unit:   frm.doc.freight_manual_per_unit || 0,
            board_grade:               frm.doc.board_grade            || "",
            markup_pct:                row.markup_pct                 || 30,
            plate_charges:             row.plate_charges              || 0,
            die_charge:                row.die_charge                 || 0,
            setup_charge:              row.setup_charge               || 0,
        },
        callback: function(r) {
            if (!r.message) return;
            var m = r.message;
            // Update all calc fields on the row
            var fields = [
                "material_cost", "converting_cost", "overhead_cost",
                "amort_fixed", "freight_cost", "total_cogs", "total_cost",
                "sell_price_m", "sell_price_unit", "extended_total",
            ];
            fields.forEach(function(f) {
                if (m[f] !== undefined) {
                    frappe.model.set_value(cdt, cdn, f, m[f]);
                }
            });
            frm.refresh_field("quantities");
        }
    });
}


// ── Sensitivity Analysis Dialog ───────────────────────────────────────────────

function _show_sensitivity_dialog(frm) {
    if (!frm.doc.blank_area_sqft) {
        frappe.msgprint(__("Please enter box dimensions to calculate blank area first."));
        return;
    }

    frappe.call({
        method: "corrugated_estimating.corrugated_estimating.api.get_sensitivity_matrix",
        args: { estimate_name: frm.doc.name },
        freeze: true,
        freeze_message: __("Calculating sensitivity matrix…"),
        callback: function(r) {
            if (!r.message) return;
            var data = r.message;
            var html = _build_sensitivity_table(data);

            frappe.msgprint({
                title: __("Sensitivity Analysis — Sell Price / Unit"),
                indicator: "blue",
                message: html,
                wide: true,
            });
        }
    });
}

function _build_sensitivity_table(data) {
    var board_costs = data.board_costs;
    var quantities  = data.quantities;
    var matrix      = data.matrix;

    // Find min/max for heat-map colouring
    var flat = [].concat.apply([], matrix);
    var mn = Math.min.apply(null, flat), mx = Math.max.apply(null, flat);

    var html = "<style>";
    html += ".sens-wrap { overflow-x: auto; max-width: 100%; }";
    html += ".sens-table { border-collapse: collapse; min-width: 100%; font-size: 12px; white-space: nowrap; }";
    html += ".sens-table th, .sens-table td { border: 1px solid #ddd; padding: 5px 8px; text-align: center; }";
    html += ".sens-table th { background: #2490EF; color: #fff; }";
    html += ".sens-table .rowhead { background: #f0f4f8; font-weight: bold; }";
    html += "</style>";
    html += "<p style='margin-bottom:8px;font-size:12px;color:#888;'>";
    html += "Rows = Board Cost ($/MSF) &nbsp;|&nbsp; Cols = Quantity &nbsp;|&nbsp; Values = Sell Price / Unit ($)</p>";
    html += "<div class='sens-wrap'><table class='sens-table'><thead><tr><th>$/MSF \\ Qty</th>";

    quantities.forEach(function(q) {
        html += "<th>" + _fmt_qty(q) + "</th>";
    });
    html += "</tr></thead><tbody>";

    matrix.forEach(function(row, i) {
        html += "<tr><td class='rowhead'>$" + board_costs[i] + "</td>";
        row.forEach(function(val) {
            var pct = mx > mn ? (val - mn) / (mx - mn) : 0.5;
            // Heat map: green (low) → yellow → red (high) — inverted for sell price (lower cost = better)
            var r = Math.round(255 * pct);
            var g = Math.round(255 * (1 - pct));
            var bg = "rgba(" + r + "," + g + ",80,0.25)";
            html += "<td style='background:" + bg + ";'>$" + val.toFixed(4) + "</td>";
        });
        html += "</tr>";
    });

    html += "</tbody></table></div>";
    return html;
}

function _fmt_qty(q) {
    if (q >= 1000) return (q / 1000) + "K";
    return q.toString();
}


// ── Print Cost Report ─────────────────────────────────────────────────────────

function _print_cost_report(frm) {
    // Build a full report and open it in a new window for printing
    var doc = frm.doc;
    var qty_rows = doc.quantities || [];

    var win = window.open("", "_blank");
    if (!win) { frappe.msgprint(__("Popup blocked. Please allow popups for this site.")); return; }

    var rows_html = "";
    qty_rows.forEach(function(row) {
        rows_html += "<tr>";
        rows_html += "<td>" + frappe.format(row.quantity, {fieldtype:"Int"}) + "</td>";
        rows_html += "<td>$" + _f(row.board_cost_msf) + "</td>";
        rows_html += "<td>$" + _f(row.material_cost) + "</td>";
        rows_html += "<td>$" + _f(row.converting_cost) + "</td>";
        rows_html += "<td>$" + _f(row.overhead_cost) + "</td>";
        rows_html += "<td>$" + _f(row.amort_fixed) + "</td>";
        rows_html += "<td>$" + _f(row.freight_cost) + "</td>";
        rows_html += "<td><strong>$" + _f(row.total_cogs) + "</strong></td>";
        rows_html += "<td><strong>$" + _f(row.sell_price_unit, 4) + "</strong></td>";
        rows_html += "<td><strong>$" + _f(row.extended_total) + "</strong></td>";
        rows_html += "</tr>";
    });

    var html = "<!DOCTYPE html><html><head>";
    html += "<title>Cost Report – " + (doc.estimate_no || "New") + "</title>";
    html += "<style>";
    html += "body{font-family:Arial,sans-serif;font-size:12px;padding:20px;color:#222;}";
    html += "h1{font-size:18px;margin:0 0 4px;}";
    html += ".header{display:flex;justify-content:space-between;border-bottom:2px solid #2490EF;padding-bottom:10px;margin-bottom:16px;}";
    html += ".section{margin-bottom:14px;}";
    html += ".section h3{font-size:13px;border-bottom:1px solid #ccc;margin-bottom:6px;padding-bottom:4px;color:#2490EF;}";
    html += ".grid{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;}";
    html += ".field{margin-bottom:4px;} .label{color:#888;font-size:10px;} .value{font-weight:bold;}";
    html += "table{width:100%;border-collapse:collapse;font-size:11px;}";
    html += "th{background:#2490EF;color:#fff;padding:5px 8px;text-align:left;}";
    html += "td{border-bottom:1px solid #eee;padding:5px 8px;}";
    html += "tr:nth-child(even){background:#f9f9f9;}";
    html += ".footer{margin-top:20px;font-size:10px;color:#aaa;text-align:center;}";
    html += "@media print{body{padding:0;} button{display:none;}}";
    html += "</style></head><body>";

    html += "<div class='header'>";
    html += "<div><h1>Corrugated Cost Report</h1>";
    html += "<div>" + (doc.estimate_no || "Draft") + " &nbsp;|&nbsp; ";
    html += frappe.datetime.str_to_user(doc.estimate_date) + "</div></div>";
    html += "<div style='text-align:right;'>";
    html += "<div><strong>" + (doc.customer || doc.crm_lead || "—") + "</strong></div>";
    html += "<div>Status: " + doc.status + "</div>";
    html += "<div>Sales Rep: " + (doc.sales_rep || "—") + "</div>";
    html += "</div></div>";

    html += "<div class='section'><h3>Box Specification</h3><div class='grid'>";
    html += _rf("Box Style",   doc.box_style);
    html += _rf("Wall Type",   doc.wall_type);
    html += _rf("Flute",       doc.flute_type);
    html += _rf("Board Grade", doc.board_grade);
    html += _rf("L × W × D",  (doc.length_inside||0) + '" × ' + (doc.width_inside||0) + '" × ' + (doc.depth_inside||0) + '"');
    html += _rf("Blank Size",  (doc.blank_length||0).toFixed(3) + '" × ' + (doc.blank_width||0).toFixed(3) + '"');
    html += _rf("Blank Area",  (doc.blank_area_sqft||0).toFixed(4) + " sq ft");
    html += _rf("Annual Qty",  doc.annual_quantity ? frappe.format(doc.annual_quantity,{fieldtype:"Int"}) : "—");
    html += "</div></div>";

    html += "<div class='section'><h3>Print &amp; Finishing</h3><div class='grid'>";
    html += _rf("# Colors",    doc.num_colors || 0);
    html += _rf("Print Method",doc.print_method || "—");
    html += _rf("Coating",     doc.coating || "None");
    html += _rf("Wax Treat",   doc.wax_water_resist ? "Yes" : "No");
    html += _rf("Die-Cut",     doc.die_cut_special ? "Yes" : "No");
    html += "</div></div>";

    html += "<div class='section'><h3>Cost Model Assumptions</h3><div class='grid'>";
    html += _rf("Board Cost Default", "$" + _f(doc.board_cost_default_msf) + "/MSF");
    html += _rf("Waste %",            (doc.waste_pct||8) + "%");
    html += _rf("Overhead %",         (doc.overhead_pct||15) + "%");
    html += _rf("Target Margin %",    (doc.target_margin_pct||35) + "%");
    html += _rf("Print Add-on",       "$" + _f(doc.print_addon_per_color_msf) + "/color/MSF");
    html += _rf("Tooling / Die",      "$" + _f(doc.tooling_cost));
    html += _rf("Setup Cost",         "$" + _f(doc.setup_cost));
    html += _rf("Freight Mode",       doc.freight_mode || "LTL");
    html += "</div></div>";

    html += "<div class='section'><h3>Quantity Breaks &amp; Pricing</h3>";
    html += "<table><thead><tr>";
    html += "<th>Qty</th><th>Board $/MSF</th><th>Material</th><th>Converting</th>";
    html += "<th>Overhead</th><th>Amort.Fixed</th><th>Freight</th>";
    html += "<th>Total COGS</th><th>Sell/Unit</th><th>Extended</th>";
    html += "</tr></thead><tbody>" + rows_html + "</tbody></table></div>";

    if (doc.customer_notes) {
        html += "<div class='section'><h3>Customer Notes</h3><p>" + doc.customer_notes + "</p></div>";
    }

    html += "<div class='footer'>Generated by Welchwyse Corrugated Estimating · " + new Date().toLocaleString() + "</div>";
    html += "<br><button onclick='window.print()' style='padding:8px 20px;background:#2490EF;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:13px;'>🖨 Print / Save PDF</button>";
    html += "</body></html>";

    win.document.write(html);
    win.document.close();
}

// ── Formatting helpers ────────────────────────────────────────────────────────

function _f(val, decimals) {
    decimals = decimals || 2;
    return parseFloat(val || 0).toFixed(decimals);
}

function _rf(label, value) {
    return "<div class='field'><div class='label'>" + label + "</div><div class='value'>" + (value || "—") + "</div></div>";
}

// ── Integration helpers ───────────────────────────────────────────────────────

function _convert_to_sales_order(frm) {
    // Build quantity row selector if multiple rows exist
    const rows = frm.doc.quantities || [];
    if (!rows.length) {
        frappe.msgprint(__("Please add at least one quantity break before converting."));
        return;
    }

    let promptFields = [];
    if (rows.length > 1) {
        promptFields.push({
            label: __("Select Quantity Break"),
            fieldname: "qty_idx",
            fieldtype: "Select",
            options: rows.map((r, i) => `${i}: ${frappe.format(r.quantity, {fieldtype:"Int"})} units @ ${frappe.format(r.sell_price_unit, {fieldtype:"Currency"})}/ea`).join("\n"),
            default: "0",
        });
    }

    const doConvert = (qty_idx) => {
        frappe.show_progress(__("Creating Sales Order…"), 0, 100);
        frappe.call({
            method: "corrugated_estimating.corrugated_estimating.integration.sales_order_bridge.estimate_to_sales_order",
            args: {
                estimate_name:    frm.doc.name,
                quantity_row_idx: qty_idx || 0,
            },
            callback(r) {
                frappe.hide_progress();
                const res = r.message || {};
                if (res.status === "success") {
                    frappe.show_alert({ message: res.message, indicator: "green" }, 8);
                    frm.reload_doc();
                } else {
                    frappe.msgprint({ title: __("Conversion Failed"), message: res.message || "Unknown error", indicator: "red" });
                }
            },
        });
    };

    if (rows.length > 1) {
        frappe.prompt(promptFields, (vals) => {
            const idx = parseInt((vals.qty_idx || "0").split(":")[0]);
            doConvert(idx);
        }, __("Convert to Sales Order"), __("Create SO"));
    } else {
        frappe.confirm(
            __("Create a Sales Order for {0} units at {1}/ea?",
               [frappe.format(rows[0].quantity, {fieldtype:"Int"}),
                frappe.format(rows[0].sell_price_unit, {fieldtype:"Currency"})]),
            () => doConvert(0)
        );
    }
}

// ── Capable Machines Dialog ──────────────────────────────────────────────────

function _show_capable_machines(frm) {
    if (!frm.doc.blank_length || !frm.doc.blank_width) {
        frappe.msgprint(__("Please enter box dimensions first."));
        return;
    }

    frappe.call({
        method: "corrugated_estimating.corrugated_estimating.api.get_capable_machines_for_estimate",
        args: { estimate_name: frm.doc.name },
        freeze: true,
        callback: function(r) {
            if (!r.message) return;
            var machines = r.message;

            var html = "<style>";
            html += ".mach-table { border-collapse: collapse; width: 100%; font-size: 12px; }";
            html += ".mach-table th, .mach-table td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; }";
            html += ".mach-table th { background: #2490EF; color: #fff; }";
            html += ".qualified { background: #e6ffe6; }";
            html += ".disqualified { background: #fff0f0; }";
            html += "</style>";
            html += "<table class='mach-table'><thead><tr>";
            html += "<th>Machine</th><th>Name</th><th>Dept</th><th>Speed/Hr</th><th>Rate $/MSF</th><th>Status</th>";
            html += "</tr></thead><tbody>";

            machines.forEach(function(m) {
                var cls = m.qualified ? "qualified" : "disqualified";
                var status = m.qualified ? "OK" : m.disqualify_reasons.join("; ");
                html += "<tr class='" + cls + "'>";
                html += "<td><strong>" + m.machine_id + "</strong></td>";
                html += "<td>" + m.machine_name + "</td>";
                html += "<td>" + m.department + "</td>";
                html += "<td>" + (m.speed_per_hour ? frappe.format(m.speed_per_hour, {fieldtype:"Int"}) : "-") + "</td>";
                html += "<td>$" + _f(m.rate_msf) + "</td>";
                html += "<td>" + status + "</td>";
                html += "</tr>";
            });

            html += "</tbody></table>";

            frappe.msgprint({
                title: __("Capable Machines — Blank {0}\" x {1}\"",
                          [_f(frm.doc.blank_length, 1), _f(frm.doc.blank_width, 1)]),
                indicator: "blue",
                message: html,
                wide: true,
            });
        }
    });
}


// ── Routing Summary Dialog ──────────────────────────────────────────────────

function _show_routing_summary(frm) {
    if (!frm.doc.routing_steps || !frm.doc.routing_steps.length) {
        frappe.msgprint(__("No routing computed yet. Click 'Compute Routing' first."));
        return;
    }

    frappe.call({
        method: "corrugated_estimating.corrugated_estimating.api.get_routing_summary",
        args: { estimate_name: frm.doc.name },
        freeze: true,
        callback: function(r) {
            if (!r.message) return;
            var data = r.message;

            var html = "<style>";
            html += ".route-table { border-collapse: collapse; width: 100%; font-size: 12px; margin-bottom: 12px; }";
            html += ".route-table th, .route-table td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; }";
            html += ".route-table th { background: #2490EF; color: #fff; }";
            html += ".summary-bar { display: flex; gap: 20px; margin-bottom: 12px; padding: 10px; background: #f0f4f8; border-radius: 4px; }";
            html += ".summary-item { text-align: center; } .summary-item .label { font-size: 10px; color: #888; } .summary-item .value { font-size: 16px; font-weight: bold; }";
            html += "</style>";

            // Summary bar
            html += "<div class='summary-bar'>";
            html += "<div class='summary-item'><div class='label'>Total Setup</div><div class='value'>" + _f(data.total_setup_minutes, 0) + " min</div></div>";
            html += "<div class='summary-item'><div class='label'>Total Run</div><div class='value'>" + _f(data.total_run_hours) + " hrs</div></div>";
            html += "<div class='summary-item'><div class='label'>Total Cost</div><div class='value'>$" + _f(data.total_machine_cost) + "</div></div>";
            html += "<div class='summary-item'><div class='label'>Bottleneck</div><div class='value'>" + (data.bottleneck_machine || "-") + "</div></div>";
            html += "</div>";

            // Steps table
            html += "<table class='route-table'><thead><tr>";
            html += "<th>Seq</th><th>Operation</th><th>Machine</th><th>Setup (min)</th><th>Run (hrs)</th><th>Total (hrs)</th><th>Cost ($)</th>";
            html += "</tr></thead><tbody>";

            (data.steps || []).forEach(function(s) {
                html += "<tr>";
                html += "<td>" + s.sequence + "</td>";
                html += "<td>" + s.operation + "</td>";
                html += "<td>" + (s.machine_name || s.machine || "-") + "</td>";
                html += "<td>" + _f(s.setup_min, 0) + "</td>";
                html += "<td>" + _f(s.run_hours) + "</td>";
                html += "<td>" + _f(s.total_hours) + "</td>";
                html += "<td>$" + _f(s.cost) + "</td>";
                html += "</tr>";
            });

            html += "</tbody></table>";

            // Die layout info
            if (frm.doc.die_layout_outs) {
                html += "<div style='margin-top:8px;padding:8px;background:#f5f5ff;border-radius:4px;font-size:12px;'>";
                html += "<strong>Die Layout:</strong> " + frm.doc.die_layout_outs + " outs";
                html += " | Waste: " + _f(frm.doc.die_layout_waste_pct, 1) + "%";
                html += " | Machine: " + (frm.doc.die_layout_machine || "-");
                html += " | Orientation: " + (frm.doc.die_layout_orientation || "-");
                html += "</div>";
            }

            frappe.msgprint({
                title: __("Production Routing Summary"),
                indicator: "blue",
                message: html,
                wide: true,
            });
        }
    });
}


function _check_board_stock(frm) {
    // Check if the board grade item is in stock via Lexington Inventory Monitor API
    frappe.call({
        method: "lexington_inventory.lexington_inventory.api.get_item_stock_info",
        args: { item_code: frm.doc.board_grade },
        callback(r) {
            if (!r.message || r.message.status !== "success") {
                frappe.msgprint(__("Could not retrieve stock info — ensure Lexington Inventory Monitor is installed and the board grade matches an Item code."));
                return;
            }
            const s = r.message;
            const color = s.actual_qty <= 0 ? "red" : s.actual_qty <= s.reorder_level ? "orange" : "green";
            const icon  = s.actual_qty <= 0 ? "🔴" : s.actual_qty <= s.reorder_level ? "🟠" : "🟢";
            frappe.msgprint({
                title: __("Board Stock — {0}", [frm.doc.board_grade]),
                message: `
                    <div style="text-align:center;font-size:18px;padding:12px">
                        ${icon} <b style="color:${color}">${s.actual_qty} ${s.uom || "units"}</b> on hand
                        <div style="font-size:12px;color:#888;margin-top:8px">Reorder level: ${s.reorder_level || "—"} | Open alerts: ${s.open_alerts}</div>
                    </div>
                `,
                indicator: s.actual_qty <= 0 ? "red" : s.actual_qty <= s.reorder_level ? "orange" : "green",
            });
        },
    });
}
