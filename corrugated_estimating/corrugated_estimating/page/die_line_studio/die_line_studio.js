/* =============================================================================
   Die Line Studio — Interactive Dieline Editor
   =============================================================================
   Pacdora-style interactive editor for designing corrugated box dielines.
   - Left panel: dimension inputs, box style, material
   - Center: live SVG dieline preview with measurements
   - Right: feature toggles, measurements readout, save/export
   ============================================================================= */

frappe.pages["die-line-studio"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Die Line Studio",
        single_column: true,
    });

    page._dielineData = null;

    page.main.html(`
        <div class="studio-container">
            <div class="studio-left">
                <h4>Box Design</h4>
                <div class="control-group"><label>Box Style</label><div id="st-style"></div></div>
                <div class="control-group"><label>Length (in)</label><div id="st-length"></div></div>
                <div class="control-group"><label>Width (in)</label><div id="st-width"></div></div>
                <div class="control-group"><label>Depth (in)</label><div id="st-depth"></div></div>
                <div class="studio-section-title">Material</div>
                <div class="control-group"><label>Flute Type</label><div id="st-flute"></div></div>
                <div class="control-group"><label>Wall Type</label><div id="st-wall"></div></div>
                <div class="studio-section-title">Joint</div>
                <div class="control-group"><label>Joint Width (in)</label><div id="st-joint"></div></div>
            </div>
            <div class="studio-canvas" id="st-canvas">
                <div class="studio-placeholder">Enter dimensions to preview the dieline.</div>
            </div>
            <div class="studio-right">
                <h4>Features</h4>
                <label class="studio-toggle"><input type="checkbox" id="st-handholes"> Hand Holes</label>
                <label class="studio-toggle"><input type="checkbox" id="st-gluetab"> Glue Tab</label>
                <label class="studio-toggle"><input type="checkbox" id="st-ventholes"> Vent Holes</label>
                <label class="studio-toggle"><input type="checkbox" id="st-dims" checked> Show Dimensions</label>
                <div class="studio-section-title">Measurements</div>
                <div class="studio-readout" id="st-readout">
                    <table>
                        <tr><td class="ro-label">Blank L</td><td class="ro-value" id="ro-bl">—</td></tr>
                        <tr><td class="ro-label">Blank W</td><td class="ro-value" id="ro-bw">—</td></tr>
                        <tr><td class="ro-label">Area (sqft)</td><td class="ro-value" id="ro-area">—</td></tr>
                        <tr><td class="ro-label">Style</td><td class="ro-value" id="ro-style">—</td></tr>
                        <tr><td class="ro-label">FEFCO</td><td class="ro-value" id="ro-fefco">—</td></tr>
                    </table>
                </div>
                <div class="studio-section-title">Save & Export</div>
                <div class="studio-export-group">
                    <button class="btn btn-primary btn-sm" id="st-save-est">Save as Estimate</button>
                    <button class="btn btn-default btn-sm" id="st-link-est">Link to Estimate</button>
                    <button class="btn btn-default btn-sm" id="st-export-png">Export PNG</button>
                    <button class="btn btn-default btn-sm" id="st-export-dxf">Export DXF</button>
                </div>
            </div>
        </div>
    `);

    // ── Build Controls ──────────────────────────────────────────────────
    var styleField = frappe.ui.form.make_control({
        parent: page.main.find("#st-style"),
        df: { fieldtype: "Link", fieldname: "box_style",
              options: "Corrugated Box Style",
              default: "RSC" },
        render_input: true,
    });
    styleField.set_value("RSC");

    var lengthField = frappe.ui.form.make_control({
        parent: page.main.find("#st-length"),
        df: { fieldtype: "Float", fieldname: "length", placeholder: "e.g. 16", default: 16 },
        render_input: true,
    });

    var widthField = frappe.ui.form.make_control({
        parent: page.main.find("#st-width"),
        df: { fieldtype: "Float", fieldname: "width", placeholder: "e.g. 12", default: 12 },
        render_input: true,
    });

    var depthField = frappe.ui.form.make_control({
        parent: page.main.find("#st-depth"),
        df: { fieldtype: "Float", fieldname: "depth", placeholder: "e.g. 10", default: 10 },
        render_input: true,
    });

    var fluteField = frappe.ui.form.make_control({
        parent: page.main.find("#st-flute"),
        df: { fieldtype: "Link", fieldname: "flute_type", options: "Corrugated Flute", placeholder: "C-Flute" },
        render_input: true,
    });

    var wallField = frappe.ui.form.make_control({
        parent: page.main.find("#st-wall"),
        df: { fieldtype: "Select", fieldname: "wall_type",
              options: "Single Wall\nDouble Wall\nTriple Wall", default: "Single Wall" },
        render_input: true,
    });

    var jointField = frappe.ui.form.make_control({
        parent: page.main.find("#st-joint"),
        df: { fieldtype: "Float", fieldname: "joint_width", default: 1.25 },
        render_input: true,
    });
    jointField.set_value(1.25);

    // ── Live Preview on Change ──────────────────────────────────────────
    var debounceTimer = null;
    function schedulePreview() {
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function () { _updatePreview(page); }, 300);
    }

    // Bind change events
    [styleField, lengthField, widthField, depthField, fluteField, wallField, jointField].forEach(function (f) {
        f.$input && f.$input.on("change", schedulePreview);
    });
    page.main.find("#st-handholes, #st-gluetab, #st-ventholes, #st-dims").on("change", schedulePreview);

    // Store field refs on page for access in functions
    page._fields = {
        style: styleField, length: lengthField, width: widthField,
        depth: depthField, flute: fluteField, wall: wallField, joint: jointField,
    };

    // ── URL Params ──────────────────────────────────────────────────────
    var params = new URLSearchParams(window.location.search);
    if (params.get("estimate")) {
        _loadFromEstimate(page, params.get("estimate"));
    } else {
        if (params.get("style")) styleField.set_value(params.get("style"));
        if (params.get("L")) lengthField.set_value(parseFloat(params.get("L")));
        if (params.get("W")) widthField.set_value(parseFloat(params.get("W")));
        if (params.get("D")) depthField.set_value(parseFloat(params.get("D")));
        setTimeout(schedulePreview, 500);
    }

    // ── Save as Estimate ────────────────────────────────────────────────
    page.main.find("#st-save-est").on("click", function () {
        var vals = _getFieldValues(page);
        if (!vals.length || !vals.width || !vals.depth) {
            frappe.msgprint(__("Enter L, W, D dimensions first."));
            return;
        }
        frappe.call({
            method: "corrugated_estimating.corrugated_estimating.api.create_estimate_from_studio",
            args: vals,
            callback: function (r) {
                if (r.message && r.message.name) {
                    frappe.set_route("corrugated-estimate", r.message.name);
                    frappe.show_alert({message: __("Estimate created: " + r.message.name), indicator: "green"});
                }
            }
        });
    });

    // ── Link to Estimate ────────────────────────────────────────────────
    page.main.find("#st-link-est").on("click", function () {
        frappe.prompt({
            fieldtype: "Link", options: "Corrugated Estimate",
            label: "Select Estimate", fieldname: "estimate", reqd: 1,
        }, function (values) {
            var vals = _getFieldValues(page);
            frappe.call({
                method: "frappe.client.set_value",
                args: {
                    doctype: "Corrugated Estimate",
                    name: values.estimate,
                    fieldname: {
                        box_style: vals.box_style,
                        length_inside: vals.length,
                        width_inside: vals.width,
                        depth_inside: vals.depth,
                    }
                },
                callback: function () {
                    frappe.show_alert({message: __("Estimate updated"), indicator: "green"});
                }
            });
        }, __("Link to Estimate"));
    });

    // ── Export PNG ───────────────────────────────────────────────────────
    page.main.find("#st-export-png").on("click", function () {
        var svgEl = page.main.find("#st-canvas svg")[0];
        if (!svgEl) { frappe.msgprint(__("No dieline to export.")); return; }
        _studioExportPng(svgEl);
    });

    // ── Export DXF ───────────────────────────────────────────────────────
    page.main.find("#st-export-dxf").on("click", function () {
        frappe.msgprint(__("Save as Estimate first, then use Generate CAD from the estimate form."));
    });
};


// ── Update Preview ──────────────────────────────────────────────────────────

function _updatePreview(page) {
    var vals = _getFieldValues(page);
    if (!vals.length || !vals.width || !vals.depth) {
        page.main.find("#st-canvas").html('<div class="studio-placeholder">Enter dimensions to preview.</div>');
        return;
    }

    frappe.xcall(
        "corrugated_estimating.corrugated_estimating.api.get_dieline_svg",
        {
            box_style: vals.box_style,
            length: vals.length,
            width: vals.width,
            depth: vals.depth,
            flute_type: vals.flute_type || null,
            hand_holes: vals.hand_holes,
            glue_tab: vals.glue_tab,
            vent_holes: vals.vent_holes,
            show_dimensions: vals.show_dimensions,
        }
    ).then(function (data) {
        if (data && data.error) {
            page.main.find("#st-canvas").html('<div class="studio-placeholder" style="color:red;">' + data.error + '</div>');
            return;
        }
        page._dielineData = data;
        _renderStudioPreview(page, data);
        _updateReadout(page, data);
    });
}


function _renderStudioPreview(page, data) {
    var container = page.main.find("#st-canvas");
    container.empty();

    if (!data || !data.elements) return;

    var bl = data.blank_length;
    var bw = data.blank_width;
    var pad = 3;  // padding for dimension annotations
    var vw = bl + 2 * pad;
    var vh = bw + 2 * pad;

    // Scale to container
    var containerW = container.width() || 700;
    var containerH = container.height() || 500;
    var scale = Math.min(containerW / vw, containerH / vh);
    var svgW = vw * scale;
    var svgH = vh * scale;

    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + svgW + '" height="' + svgH + '" viewBox="' + (-pad) + ' ' + (-pad) + ' ' + vw + ' ' + vh + '">';

    // White background for the blank
    svg += '<rect x="0" y="0" width="' + bl + '" height="' + bw + '" fill="#fff" stroke="#ccc" stroke-width="0.1"/>';

    // Render elements
    (data.elements || []).forEach(function (el) {
        var style = data.line_styles[el.line_type] || data.line_styles["CUT"];
        var sw = style.stroke_width || 0.3;
        var strokeAttr = 'stroke="' + style.stroke + '" stroke-width="' + sw + '" fill="none"';
        if (style.dash) {
            strokeAttr += ' stroke-dasharray="' + style.dash + '"';
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
                svg += (el.closed ? '<polygon' : '<polyline') + ' points="' + pts + '" ' + strokeAttr + '/>';
                break;
            case "circle":
                svg += '<circle cx="' + el.cx + '" cy="' + el.cy + '" r="' + el.r + '" ' + strokeAttr + '/>';
                break;
            case "ellipse":
                svg += '<ellipse cx="' + el.cx + '" cy="' + el.cy + '" rx="' + el.rx + '" ry="' + el.ry + '" ' + strokeAttr + '/>';
                break;
            case "label":
                var ls = (el.size || 0.2) * 5;
                svg += '<text x="' + el.x + '" y="' + el.y + '" text-anchor="middle" dominant-baseline="middle" font-size="' + ls + '" fill="#555" font-family="sans-serif">' + el.text + '</text>';
                break;
            case "dimension":
                var isH = Math.abs(el.y2 - el.y1) < 0.01;
                var off = el.offset || 0.8;
                var tk = 0.2;
                if (isH) {
                    var dy = el.side === "outside" ? off : -off;
                    svg += '<line x1="' + el.x1 + '" y1="' + (el.y1+dy) + '" x2="' + el.x2 + '" y2="' + (el.y2+dy) + '" stroke="#666" stroke-width="0.1" fill="none"/>';
                    svg += '<line x1="' + el.x1 + '" y1="' + (el.y1+dy-tk) + '" x2="' + el.x1 + '" y2="' + (el.y1+dy+tk) + '" stroke="#666" stroke-width="0.1"/>';
                    svg += '<line x1="' + el.x2 + '" y1="' + (el.y2+dy-tk) + '" x2="' + el.x2 + '" y2="' + (el.y2+dy+tk) + '" stroke="#666" stroke-width="0.1"/>';
                    svg += '<text x="' + ((el.x1+el.x2)/2) + '" y="' + (el.y1+dy-0.15) + '" text-anchor="middle" font-size="0.8" fill="#666" font-family="sans-serif">' + el.text + '</text>';
                } else {
                    var dx = el.side === "outside" ? -off : off;
                    svg += '<line x1="' + (el.x1+dx) + '" y1="' + el.y1 + '" x2="' + (el.x2+dx) + '" y2="' + el.y2 + '" stroke="#666" stroke-width="0.1" fill="none"/>';
                    svg += '<line x1="' + (el.x1+dx-tk) + '" y1="' + el.y1 + '" x2="' + (el.x1+dx+tk) + '" y2="' + el.y1 + '" stroke="#666" stroke-width="0.1"/>';
                    svg += '<line x1="' + (el.x2+dx-tk) + '" y1="' + el.y2 + '" x2="' + (el.x2+dx+tk) + '" y2="' + el.y2 + '" stroke="#666" stroke-width="0.1"/>';
                    svg += '<text x="' + (el.x1+dx-0.2) + '" y="' + ((el.y1+el.y2)/2) + '" text-anchor="middle" font-size="0.8" fill="#666" font-family="sans-serif" transform="rotate(-90,' + (el.x1+dx-0.2) + ',' + ((el.y1+el.y2)/2) + ')">' + el.text + '</text>';
                }
                break;
            case "arc":
                var aR = el.r, a1 = el.start_angle * Math.PI / 180, a2 = el.end_angle * Math.PI / 180;
                var ax1 = el.cx + aR * Math.cos(a1), ay1 = el.cy + aR * Math.sin(a1);
                var ax2 = el.cx + aR * Math.cos(a2), ay2 = el.cy + aR * Math.sin(a2);
                var la = (el.end_angle - el.start_angle) > 180 ? 1 : 0;
                svg += '<path d="M' + ax1.toFixed(3) + ',' + ay1.toFixed(3) + ' A' + aR + ',' + aR + ' 0 ' + la + ' 1 ' + ax2.toFixed(3) + ',' + ay2.toFixed(3) + '" ' + strokeAttr + '/>';
                break;
            case "path":
                svg += '<path d="' + el.d + '" ' + strokeAttr + '/>';
                break;
        }
    });

    svg += '</svg>';
    container.html(svg);
}


function _updateReadout(page, data) {
    var bl = data.blank_length || 0;
    var bw = data.blank_width || 0;
    page.main.find("#ro-bl").text(bl.toFixed(2) + '"');
    page.main.find("#ro-bw").text(bw.toFixed(2) + '"');
    page.main.find("#ro-area").text(((bl * bw) / 144).toFixed(3));
    page.main.find("#ro-style").text(data.style || "—");
    page.main.find("#ro-fefco").text(data.fefco || "—");
}


function _getFieldValues(page) {
    var f = page._fields;
    return {
        box_style: f.style.get_value() || "RSC",
        length: parseFloat(f.length.get_value()) || 0,
        width: parseFloat(f.width.get_value()) || 0,
        depth: parseFloat(f.depth.get_value()) || 0,
        flute_type: f.flute.get_value() || null,
        wall_type: f.wall.get_value() || "Single Wall",
        joint_width: parseFloat(f.joint.get_value()) || 1.25,
        hand_holes: page.main.find("#st-handholes").is(":checked"),
        glue_tab: page.main.find("#st-gluetab").is(":checked"),
        vent_holes: page.main.find("#st-ventholes").is(":checked"),
        show_dimensions: page.main.find("#st-dims").is(":checked"),
    };
}


function _loadFromEstimate(page, estimateName) {
    frappe.xcall("frappe.client.get", {
        doctype: "Corrugated Estimate",
        name: estimateName,
    }).then(function (doc) {
        if (!doc) return;
        var f = page._fields;
        if (doc.box_style) f.style.set_value(doc.box_style);
        if (doc.length_inside) f.length.set_value(doc.length_inside);
        if (doc.width_inside) f.width.set_value(doc.width_inside);
        if (doc.depth_inside) f.depth.set_value(doc.depth_inside);
        if (doc.flute_type) f.flute.set_value(doc.flute_type);
        if (doc.wall_type) f.wall.set_value(doc.wall_type);
        setTimeout(function () { _updatePreview(page); }, 500);
    });
}


function _studioExportPng(svgEl) {
    var serializer = new XMLSerializer();
    var svgStr = serializer.serializeToString(svgEl);
    var canvas = document.createElement("canvas");
    var svgW = svgEl.width.baseVal.value;
    var svgH = svgEl.height.baseVal.value;
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
        link.download = "dieline-" + new Date().toISOString().slice(0, 10) + ".png";
        link.href = canvas.toDataURL("image/png");
        link.click();
    };
    img.src = url;
}
