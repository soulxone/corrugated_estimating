/* =============================================================================
   Die Layout Viewer – Interactive SVG nesting visualization
   =============================================================================
   Shows how blanks are nested onto a die cut sheet, with:
   - Trim zone (hatched border)
   - Gripper edge (dark strip at leading edge)
   - Blank rectangles OR detailed dielines (Pacdora-style colored lines)
   - Waste areas (highlighted)
   - Info panel: outs, waste %, utilization, sheet dims
   - Legend: line type colors (Cut/Score/Fold/Glue)
   - Toggle: Simple view (rectangles) vs Detailed view (dielines)
   ============================================================================= */

frappe.pages["die-layout-viewer"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Die Cut Layout Viewer",
        single_column: true,
    });

    // Track current state
    page._viewMode = "detailed"; // "simple" or "detailed"
    page._currentLayout = null;
    page._currentDielineData = null;
    page._layerVisibility = { CUT: true, SCORE: true, FOLD: true, GLUE: true };

    page.main.html(`
        <div class="die-layout-container">
            <div class="die-layout-controls">
                <div class="control-row">
                    <div class="control-group">
                        <label>Estimate</label>
                        <div id="estimate-field"></div>
                    </div>
                    <div class="control-group">
                        <label>Machine</label>
                        <div id="machine-field"></div>
                    </div>
                    <div class="control-group">
                        <label>Sheet Length (in)</label>
                        <div id="sheet-length-field"></div>
                    </div>
                    <div class="control-group">
                        <label>Sheet Width (in)</label>
                        <div id="sheet-width-field"></div>
                    </div>
                    <div class="control-group control-buttons">
                        <button class="btn btn-primary btn-sm" id="calc-layout-btn">Calculate Layout</button>
                        <button class="btn btn-default btn-sm" id="toggle-view-btn" title="Toggle Simple/Detailed view">Detailed</button>
                        <button class="btn btn-default btn-sm" id="export-svg-btn">Export PNG</button>
                        <button class="btn btn-default btn-sm" id="export-dxf-btn" title="Generate die board DXF file">Export DXF</button>
                    </div>
                </div>
            </div>
            <div class="die-layout-body">
                <div class="svg-container" id="svg-container">
                    <div class="placeholder-text">Select an estimate and click "Calculate Layout" to view the die nesting.</div>
                </div>
                <div class="info-panel" id="info-panel">
                    <h4>Layout Info</h4>
                    <div id="info-content">No layout computed yet.</div>
                    <div id="legend-container"></div>
                    <div id="layer-toggles"></div>
                </div>
            </div>
        </div>
    `);

    // ── Build controls ────────────────────────────────────────────────────
    var estimateField = frappe.ui.form.make_control({
        parent: page.main.find("#estimate-field"),
        df: { fieldtype: "Link", fieldname: "estimate", options: "Corrugated Estimate", placeholder: "Select Estimate" },
        render_input: true,
    });

    var machineField = frappe.ui.form.make_control({
        parent: page.main.find("#machine-field"),
        df: { fieldtype: "Link", fieldname: "machine", options: "Corrugated Machine",
              placeholder: "Auto or select", get_query: function() { return { filters: { can_die_cut: 1, enabled: 1 } }; } },
        render_input: true,
    });

    var sheetLengthField = frappe.ui.form.make_control({
        parent: page.main.find("#sheet-length-field"),
        df: { fieldtype: "Float", fieldname: "sheet_length", placeholder: "Auto" },
        render_input: true,
    });

    var sheetWidthField = frappe.ui.form.make_control({
        parent: page.main.find("#sheet-width-field"),
        df: { fieldtype: "Float", fieldname: "sheet_width", placeholder: "Auto" },
        render_input: true,
    });

    // ── Auto-populate from URL params ─────────────────────────────────────
    var routeParams = new URLSearchParams(window.location.search);
    if (routeParams.get("estimate")) {
        estimateField.set_value(routeParams.get("estimate"));
    }

    // ── Toggle View Mode ─────────────────────────────────────────────────
    page.main.find("#toggle-view-btn").on("click", function () {
        page._viewMode = page._viewMode === "simple" ? "detailed" : "simple";
        $(this).text(page._viewMode === "simple" ? "Simple" : "Detailed");
        $(this).toggleClass("btn-primary", page._viewMode === "detailed");
        $(this).toggleClass("btn-default", page._viewMode === "simple");
        // Re-render if we have data
        if (page._currentLayout) {
            _renderLayout(page, page._currentLayout, page._currentDielineData);
        }
    });

    // ── Calculate button ──────────────────────────────────────────────────
    page.main.find("#calc-layout-btn").on("click", function () {
        var est = estimateField.get_value();
        if (!est) {
            frappe.msgprint(__("Please select an estimate."));
            return;
        }

        // Fetch layout + dieline data in parallel
        var layoutPromise = frappe.xcall(
            "corrugated_estimating.corrugated_estimating.api.get_die_layout",
            {
                estimate_name: est,
                machine_id: machineField.get_value() || null,
                sheet_length: sheetLengthField.get_value() || null,
                sheet_width: sheetWidthField.get_value() || null,
            }
        );

        var dielinePromise = frappe.xcall(
            "corrugated_estimating.corrugated_estimating.api.get_dieline_svg",
            { estimate_name: est }
        );

        frappe.dom.freeze(__("Calculating die layout..."));

        Promise.all([layoutPromise, dielinePromise]).then(function (results) {
            frappe.dom.unfreeze();
            var data = results[0];
            var dielineData = results[1];

            page._currentDielineData = dielineData;

            if (Array.isArray(data)) {
                if (data.length === 0) {
                    page.main.find("#svg-container").html(
                        '<div class="placeholder-text">No die cut machines can fit this blank size.</div>'
                    );
                    page.main.find("#info-content").html("No layout possible.");
                    return;
                }
                page._currentLayout = data[0];
                _renderLayout(page, data[0], dielineData);
                _renderComparisonInfo(page, data);
            } else if (data.error) {
                page.main.find("#svg-container").html(
                    '<div class="placeholder-text" style="color:red;">' + data.error + '</div>'
                );
            } else {
                page._currentLayout = data;
                _renderLayout(page, data, dielineData);
                _renderSingleInfo(page, data);
            }

            // Render legend and layer toggles
            _renderLegend(page);
            _renderLayerToggles(page);
        }).catch(function (err) {
            frappe.dom.unfreeze();
            frappe.msgprint(__("Error calculating layout: ") + (err.message || err));
        });
    });

    // ── Export PNG ─────────────────────────────────────────────────────────
    page.main.find("#export-svg-btn").on("click", function () {
        var svgEl = page.main.find("#svg-container svg")[0];
        if (!svgEl) {
            frappe.msgprint(__("No layout to export."));
            return;
        }
        _exportSvgToPng(svgEl);
    });

    // ── Export DXF Die Board ──────────────────────────────────────────────
    page.main.find("#export-dxf-btn").on("click", function () {
        var est = estimateField.get_value();
        if (!est) {
            frappe.msgprint(__("Please select an estimate first."));
            return;
        }

        frappe.call({
            method: "corrugated_estimating.corrugated_estimating.api.generate_die_board_dxf",
            args: {
                estimate_name: est,
                machine_id: machineField.get_value() || null,
            },
            freeze: true,
            freeze_message: __("Generating die board DXF..."),
            callback: function (r) {
                if (r.message && r.message.status === "success") {
                    window.open(r.message.file_url, "_blank");
                    frappe.show_alert({message: __("Die board DXF generated!"), indicator: "green"});
                } else {
                    frappe.msgprint(r.message ? r.message.message : __("Failed to generate DXF."));
                }
            }
        });
    });

    // Auto-calculate if estimate was passed via URL
    setTimeout(function () {
        if (routeParams.get("estimate")) {
            page.main.find("#calc-layout-btn").click();
        }
    }, 500);
};


// ── SVG Rendering ───────────────────────────────────────────────────────────

function _renderLayout(page, layout, dielineData) {
    var container = page.main.find("#svg-container");
    container.empty();

    if (!layout || !layout.layout_positions || layout.layout_positions.length === 0) {
        container.html('<div class="placeholder-text">No blanks fit in this layout.</div>');
        return;
    }

    // Scale: fit SVG to container width
    var containerWidth = Math.min(container.width() || 900, 900);
    var scale = containerWidth / layout.sheet_length;
    var svgW = layout.sheet_length * scale;
    var svgH = layout.sheet_width * scale;

    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + svgW + '" height="' + svgH + '" viewBox="0 0 ' + layout.sheet_length + ' ' + layout.sheet_width + '">';

    // Defs for patterns
    svg += '<defs>';
    svg += '<pattern id="trim-hatch" patternUnits="userSpaceOnUse" width="4" height="4">';
    svg += '<path d="M-1,1 l2,-2 M0,4 l4,-4 M3,5 l2,-2" stroke="#cc0000" stroke-width="0.3" opacity="0.4"/>';
    svg += '</pattern>';
    svg += '</defs>';

    // Sheet boundary
    svg += '<rect x="0" y="0" width="' + layout.sheet_length + '" height="' + layout.sheet_width + '" fill="#f5f5f5" stroke="#333" stroke-width="0.5"/>';

    // Trim zone
    var trim = layout.trim_allowance;
    svg += '<rect x="0" y="0" width="' + layout.sheet_length + '" height="' + trim + '" fill="url(#trim-hatch)"/>';
    svg += '<rect x="0" y="' + (layout.sheet_width - trim) + '" width="' + layout.sheet_length + '" height="' + trim + '" fill="url(#trim-hatch)"/>';
    svg += '<rect x="0" y="0" width="' + trim + '" height="' + layout.sheet_width + '" fill="url(#trim-hatch)"/>';
    svg += '<rect x="' + (layout.sheet_length - trim) + '" y="0" width="' + trim + '" height="' + layout.sheet_width + '" fill="url(#trim-hatch)"/>';

    // Gripper edge
    var gripper = layout.gripper_edge;
    if (gripper > 0) {
        svg += '<rect x="' + trim + '" y="0" width="' + gripper + '" height="' + layout.sheet_width + '" fill="rgba(100,100,100,0.15)" stroke="#666" stroke-width="0.2"/>';
        var fontSize = Math.max(1.5, layout.sheet_width * 0.02);
        svg += '<text x="' + (trim + gripper / 2) + '" y="' + (layout.sheet_width / 2) + '" text-anchor="middle" font-size="' + fontSize + '" fill="#666" transform="rotate(-90,' + (trim + gripper / 2) + ',' + (layout.sheet_width / 2) + ')">GRIPPER</text>';
    }

    // Render blanks
    var useDetailed = page._viewMode === "detailed" && dielineData && dielineData.elements;
    var colors = ["#2490EF", "#28a745", "#6f42c1", "#fd7e14", "#e83e8c", "#20c997"];
    var partTypeColors = {
        "Box Body": "#2490EF",
        "Partition": "#28a745",
        "Pad": "#fd7e14",
        "Insert": "#6f42c1",
        "Divider": "#e83e8c",
        "Liner": "#20c997",
        "Sleeve": "#6610f2",
    };

    layout.layout_positions.forEach(function (pos, i) {
        var color = pos.part_type ? (partTypeColors[pos.part_type] || colors[i % colors.length]) : colors[i % colors.length];

        if (useDetailed) {
            // Detailed view: render dieline inside each blank position
            svg += _renderDielineInBlank(pos, dielineData, page._layerVisibility, i);
        } else {
            // Simple view: colored rectangles
            svg += '<rect x="' + pos.x + '" y="' + pos.y + '" width="' + pos.width + '" height="' + pos.height + '" ';
            svg += 'fill="' + color + '" fill-opacity="0.25" stroke="' + color + '" stroke-width="0.5"/>';
        }

        // Dimension text inside blank
        var txtSize = Math.max(1.2, Math.min(pos.width, pos.height) * 0.1);
        var cx = pos.x + pos.width / 2;
        var cy = pos.y + pos.height / 2;

        if (!useDetailed) {
            svg += '<text x="' + cx + '" y="' + cy + '" text-anchor="middle" dominant-baseline="middle" font-size="' + txtSize + '" fill="#333">';
            svg += pos.width.toFixed(1) + '" x ' + pos.height.toFixed(1) + '"';
            svg += '</text>';
        }

        // Out number
        svg += '<text x="' + (pos.x + 0.5) + '" y="' + (pos.y + txtSize + 0.5) + '" font-size="' + (txtSize * 0.7) + '" fill="' + color + '" font-weight="bold">#' + (i + 1) + '</text>';
    });

    // Sheet dimension callouts
    var dimFont = Math.max(2, layout.sheet_width * 0.03);
    svg += '<text x="' + (layout.sheet_length / 2) + '" y="' + (layout.sheet_width - trim / 3) + '" text-anchor="middle" font-size="' + dimFont + '" fill="#c00">' + layout.sheet_length.toFixed(1) + '"</text>';
    svg += '<text x="' + (layout.sheet_length - trim / 3) + '" y="' + (layout.sheet_width / 2) + '" text-anchor="middle" font-size="' + dimFont + '" fill="#c00" transform="rotate(-90,' + (layout.sheet_length - trim / 3) + ',' + (layout.sheet_width / 2) + ')">' + layout.sheet_width.toFixed(1) + '"</text>';

    svg += '</svg>';
    container.html(svg);
}


// ── Render Dieline Elements Inside a Blank Position ─────────────────────────

function _renderDielineInBlank(pos, dielineData, layerVis, index) {
    var svg = '';
    var bl = dielineData.blank_length || pos.width;
    var bw = dielineData.blank_width || pos.height;

    // Scale dieline to fit the blank position
    var scaleX = pos.width / bl;
    var scaleY = pos.height / bw;

    // Group with transform to position and scale
    svg += '<g transform="translate(' + pos.x + ',' + pos.y + ') scale(' + scaleX.toFixed(4) + ',' + scaleY.toFixed(4) + ')">';

    // Light background for the blank
    svg += '<rect x="0" y="0" width="' + bl + '" height="' + bw + '" fill="#fff" fill-opacity="0.9" stroke="#999" stroke-width="' + (0.3 / scaleX) + '"/>';

    // Render each element
    (dielineData.elements || []).forEach(function (el) {
        if (!layerVis[el.line_type] && el.type !== "label") return;

        var style = dielineData.line_styles[el.line_type] || dielineData.line_styles["CUT"];
        var sw = (style.stroke_width || 0.4) / Math.min(scaleX, scaleY);
        var strokeAttr = 'stroke="' + style.stroke + '" stroke-width="' + sw.toFixed(2) + '" fill="none"';
        if (style.dash) {
            // Scale dash pattern inversely
            var dashScale = 1 / Math.min(scaleX, scaleY);
            var scaledDash = style.dash.split(",").map(function (d) {
                return (parseFloat(d) * dashScale).toFixed(1);
            }).join(",");
            strokeAttr += ' stroke-dasharray="' + scaledDash + '"';
        }

        switch (el.type) {
            case "line":
                svg += '<line x1="' + el.x1 + '" y1="' + el.y1 + '" x2="' + el.x2 + '" y2="' + el.y2 + '" ' + strokeAttr + '/>';
                break;

            case "rect":
                svg += '<rect x="' + el.x + '" y="' + el.y + '" width="' + el.width + '" height="' + el.height + '" ' + strokeAttr + '/>';
                break;

            case "polyline":
                var pts = el.points.map(function (p) { return p[0] + "," + p[1]; }).join(" ");
                if (el.closed) {
                    svg += '<polygon points="' + pts + '" ' + strokeAttr + '/>';
                } else {
                    svg += '<polyline points="' + pts + '" ' + strokeAttr + '/>';
                }
                break;

            case "circle":
                svg += '<circle cx="' + el.cx + '" cy="' + el.cy + '" r="' + el.r + '" ' + strokeAttr + '/>';
                break;

            case "ellipse":
                svg += '<ellipse cx="' + el.cx + '" cy="' + el.cy + '" rx="' + el.rx + '" ry="' + el.ry + '" ' + strokeAttr + '/>';
                break;

            case "label":
                var labelSize = (el.size || 0.2) * 5;
                svg += '<text x="' + el.x + '" y="' + el.y + '" text-anchor="middle" dominant-baseline="middle" font-size="' + labelSize + '" fill="#555" font-family="sans-serif">' + el.text + '</text>';
                break;
        }
    });

    svg += '</g>';
    return svg;
}


// ── Legend ────────────────────────────────────────────────────────────────────

function _renderLegend(page) {
    var legend = '<hr style="margin:10px 0 8px;"><h5>Dieline Legend</h5>';
    legend += '<div class="dieline-legend">';

    var items = [
        { type: "CUT",   color: "#0066CC", label: "Cut Line",   dash: "" },
        { type: "SCORE", color: "#CC0000", label: "Score Line", dash: "6,4" },
        { type: "FOLD",  color: "#009933", label: "Fold Line",  dash: "2,4" },
        { type: "GLUE",  color: "#FF6600", label: "Glue Tab",   dash: "8,4,2,4" },
    ];

    items.forEach(function (item) {
        legend += '<div class="legend-item">';
        legend += '<svg width="30" height="12"><line x1="0" y1="6" x2="30" y2="6" stroke="' + item.color + '" stroke-width="2"';
        if (item.dash) legend += ' stroke-dasharray="' + item.dash + '"';
        legend += '/></svg>';
        legend += '<span class="legend-label">' + item.label + '</span>';
        legend += '</div>';
    });

    legend += '</div>';
    page.main.find("#legend-container").html(legend);
}


// ── Layer Toggles ────────────────────────────────────────────────────────────

function _renderLayerToggles(page) {
    var html = '<h5 style="margin-top:8px;">Layers</h5><div class="layer-toggles">';

    var layers = [
        { key: "CUT", label: "Cut", color: "#0066CC" },
        { key: "SCORE", label: "Score", color: "#CC0000" },
        { key: "FOLD", label: "Fold", color: "#009933" },
        { key: "GLUE", label: "Glue", color: "#FF6600" },
    ];

    layers.forEach(function (layer) {
        var checked = page._layerVisibility[layer.key] ? "checked" : "";
        html += '<label class="layer-toggle" style="border-left: 3px solid ' + layer.color + ';">';
        html += '<input type="checkbox" data-layer="' + layer.key + '" ' + checked + '> ';
        html += layer.label;
        html += '</label>';
    });

    html += '</div>';
    page.main.find("#layer-toggles").html(html);

    // Bind toggle events
    page.main.find("#layer-toggles input").on("change", function () {
        var layerKey = $(this).data("layer");
        page._layerVisibility[layerKey] = $(this).is(":checked");
        if (page._currentLayout) {
            _renderLayout(page, page._currentLayout, page._currentDielineData);
        }
    });
}


// ── Info Panel Rendering ────────────────────────────────────────────────────

function _renderSingleInfo(page, layout) {
    var html = '<table class="info-table">';
    html += _infoRow("Machine", layout.machine_name || layout.machine_id || "Manual");
    html += _infoRow("Total Outs", '<strong>' + layout.total_outs + '</strong>');
    html += _infoRow("Layout", layout.outs_across + " across x " + layout.outs_down + " down");
    html += _infoRow("Orientation", layout.blank_orientation || "0deg");
    html += _infoRow("Blank Size", layout.blank_length.toFixed(2) + '" x ' + layout.blank_width.toFixed(2) + '"');
    html += _infoRow("Sheet Size", layout.sheet_length.toFixed(1) + '" x ' + layout.sheet_width.toFixed(1) + '"');
    html += _infoRow("Usable Area", layout.usable_length.toFixed(1) + '" x ' + layout.usable_width.toFixed(1) + '"');
    html += _infoRow("Trim", layout.trim_allowance + '" per side');
    html += _infoRow("Gripper", layout.gripper_edge + '"');
    html += _infoRow("Gutter", layout.gutter + '"');
    html += _infoRow("Waste %", '<span style="color:' + (layout.waste_pct > 25 ? 'red' : layout.waste_pct > 15 ? 'orange' : 'green') + ';font-weight:bold;">' + layout.waste_pct.toFixed(1) + '%</span>');
    html += _infoRow("Utilization", '<span style="font-weight:bold;">' + layout.utilization_pct.toFixed(1) + '%</span>');
    html += _infoRow("Blank Area", layout.total_blank_area_sqft.toFixed(2) + ' sq ft');
    html += _infoRow("Sheet Area", layout.sheet_area_sqft.toFixed(2) + ' sq ft');
    html += '</table>';

    page.main.find("#info-content").html(html);
}


function _renderComparisonInfo(page, layouts) {
    var html = '<p style="font-size:11px;color:#888;margin-bottom:8px;">Showing best layout. All machines:</p>';
    html += '<table class="info-table">';
    html += '<tr><th>Machine</th><th>Outs</th><th>Waste</th><th>Layout</th></tr>';

    layouts.forEach(function (l, i) {
        var cls = i === 0 ? ' style="background:#e6ffe6;font-weight:bold;"' : '';
        html += '<tr' + cls + '>';
        html += '<td>' + (l.machine_name || l.machine_id) + '</td>';
        html += '<td>' + l.total_outs + '</td>';
        html += '<td>' + l.waste_pct.toFixed(1) + '%</td>';
        html += '<td>' + l.outs_across + 'x' + l.outs_down + '</td>';
        html += '</tr>';
    });

    html += '</table>';

    html += '<hr style="margin:8px 0;">';
    html += '<h5>Best Layout Details</h5>';
    var best = layouts[0];
    html += '<table class="info-table">';
    html += _infoRow("Machine", best.machine_name || best.machine_id);
    html += _infoRow("Outs", best.total_outs + ' (' + best.outs_across + ' x ' + best.outs_down + ')');
    html += _infoRow("Orientation", best.blank_orientation);
    html += _infoRow("Sheet", best.sheet_length.toFixed(1) + '" x ' + best.sheet_width.toFixed(1) + '"');
    html += _infoRow("Waste", best.waste_pct.toFixed(1) + '%');
    html += _infoRow("Utilization", best.utilization_pct.toFixed(1) + '%');
    html += '</table>';

    page.main.find("#info-content").html(html);
}


function _infoRow(label, value) {
    return '<tr><td class="info-label">' + label + '</td><td class="info-value">' + value + '</td></tr>';
}


// ── Export SVG to PNG ────────────────────────────────────────────────────────

function _exportSvgToPng(svgElement) {
    var serializer = new XMLSerializer();
    var svgStr = serializer.serializeToString(svgElement);
    var canvas = document.createElement("canvas");
    var svgW = svgElement.width.baseVal.value;
    var svgH = svgElement.height.baseVal.value;

    // 2x resolution for print
    canvas.width = svgW * 2;
    canvas.height = svgH * 2;
    var ctx = canvas.getContext("2d");
    ctx.scale(2, 2);

    var img = new Image();
    var blob = new Blob([svgStr], { type: "image/svg+xml;charset=utf-8" });
    var url = URL.createObjectURL(blob);

    img.onload = function () {
        ctx.fillStyle = "#fff";
        ctx.fillRect(0, 0, svgW, svgH);
        ctx.drawImage(img, 0, 0, svgW, svgH);
        URL.revokeObjectURL(url);

        var link = document.createElement("a");
        link.download = "die-layout-" + new Date().toISOString().slice(0, 10) + ".png";
        link.href = canvas.toDataURL("image/png");
        link.click();
    };

    img.src = url;
}
