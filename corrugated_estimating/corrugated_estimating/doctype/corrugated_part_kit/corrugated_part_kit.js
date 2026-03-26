frappe.ui.form.on("Corrugated Part Kit", {
    refresh: function (frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("View Die Layout"), function () {
                frappe.call({
                    method: "corrugated_estimating.corrugated_estimating.api.get_part_kit_layout",
                    args: { kit_name: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Calculating multi-part layout..."),
                    callback: function (r) {
                        if (r.message && r.message.layout_positions) {
                            _show_kit_layout_dialog(frm, r.message);
                        } else {
                            frappe.msgprint(r.message ? r.message.error : __("No layout possible."));
                        }
                    }
                });
            }, __("Layout"));

            // Open first Box Body part in Die Line Studio
            var body_part = (frm.doc.parts || []).find(function (p) {
                return p.part_type === "Box Body";
            });
            if (body_part) {
                frm.add_custom_button(__("Open in Studio"), function () {
                    var url = "/app/die-line-studio?style=" + encodeURIComponent(body_part.box_style || "RSC")
                        + "&L=" + (body_part.length || 0)
                        + "&W=" + (body_part.width || 0)
                        + "&D=" + (body_part.depth || 0);
                    window.location.href = url;
                }, __("Layout"));
            }
        }
    },
});


function _show_kit_layout_dialog(frm, layout) {
    var d = new frappe.ui.Dialog({
        title: __("Part Kit Die Layout: " + frm.doc.kit_name),
        size: "extra-large",
    });

    var html = '<div style="text-align:center;padding:10px;">';
    html += '<p><strong>' + layout.total_outs + ' parts</strong> nested on ';
    html += layout.sheet_length.toFixed(1) + '" x ' + layout.sheet_width.toFixed(1) + '" sheet';
    html += ' — Waste: <span style="color:' + (layout.waste_pct > 15 ? 'orange' : 'green') + ';">';
    html += layout.waste_pct.toFixed(1) + '%</span></p>';

    // Build simple SVG
    var sl = layout.sheet_length;
    var sw = layout.sheet_width;
    var scale = Math.min(800 / sl, 500 / sw);
    var svgW = sl * scale;
    var svgH = sw * scale;

    html += '<svg width="' + svgW + '" height="' + svgH + '" viewBox="0 0 ' + sl + ' ' + sw + '">';
    html += '<rect x="0" y="0" width="' + sl + '" height="' + sw + '" fill="#f5f5f5" stroke="#333" stroke-width="0.5"/>';

    var partColors = {
        "Box Body": "#2490EF", "Partition": "#28a745", "Pad": "#fd7e14",
        "Insert": "#6f42c1", "Divider": "#e83e8c", "Liner": "#20c997", "Sleeve": "#6610f2",
    };

    (layout.layout_positions || []).forEach(function (pos, i) {
        var color = partColors[pos.part_type] || "#999";
        html += '<rect x="' + pos.x + '" y="' + pos.y + '" width="' + pos.width + '" height="' + pos.height + '" ';
        html += 'fill="' + color + '" fill-opacity="0.3" stroke="' + color + '" stroke-width="0.4"/>';
        var fs = Math.max(1, Math.min(pos.width, pos.height) * 0.12);
        html += '<text x="' + (pos.x + pos.width / 2) + '" y="' + (pos.y + pos.height / 2) + '" text-anchor="middle" dominant-baseline="middle" font-size="' + fs + '" fill="#333">' + (pos.part_type || "") + '</text>';
    });

    html += '</svg></div>';

    d.$body.html(html);
    d.show();
}
