frappe.ui.form.on("Corrugated Tooling", {
    refresh: function (frm) {
        // Show linked estimate button
        if (frm.doc.corrugated_estimate) {
            frm.add_custom_button(__("View Estimate"), function () {
                frappe.set_route("Form", "Corrugated Estimate", frm.doc.corrugated_estimate);
            });
        }

        // Status color indicator
        var colors = {
            Active: "green",
            "Needs Repair": "orange",
            Retired: "blue",
            Disposed: "red",
        };
        frm.page.set_indicator(frm.doc.status, colors[frm.doc.status] || "grey");

        // Wear warning
        if (frm.doc.num_impressions && frm.doc.max_impressions) {
            var pct = (frm.doc.num_impressions / frm.doc.max_impressions) * 100;
            if (pct >= 90) {
                frm.dashboard.set_headline(
                    __("Warning: {0}% of max impressions reached — consider replacement", [pct.toFixed(0)]),
                    "red"
                );
            } else if (pct >= 70) {
                frm.dashboard.set_headline(
                    __("{0}% of max impressions used", [pct.toFixed(0)]),
                    "orange"
                );
            }
        }
    },

    corrugated_estimate: function (frm) {
        if (frm.doc.corrugated_estimate) {
            frappe.call({
                method: "corrugated_estimating.corrugated_estimating.api.get_estimate_spec",
                args: { estimate_name: frm.doc.corrugated_estimate },
                callback: function (r) {
                    if (r.message) {
                        var d = r.message;
                        frm.set_value("box_style", d.box_style);
                        frm.set_value("length_inside", d.length_inside);
                        frm.set_value("width_inside", d.width_inside);
                        frm.set_value("depth_inside", d.depth_inside);
                        frm.set_value("flute_type", d.flute_type);
                        frm.set_value("board_grade", d.board_grade);
                        frm.set_value("num_colors", d.num_colors);
                        if (!frm.doc.tooling_name) {
                            frm.set_value("tooling_name",
                                (d.box_style || "Box") + " " +
                                (d.length_inside || 0) + "x" + (d.width_inside || 0) + "x" + (d.depth_inside || 0) +
                                " " + (frm.doc.tooling_type || "Die")
                            );
                        }
                    }
                },
            });
        }
    },
});
