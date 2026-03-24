/* =============================================================================
   Estimating Training Guide — Interactive step-by-step guides for all box styles
   ============================================================================= */

frappe.pages["estimating-guide"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Estimating Training Guide",
        single_column: true,
    });

    page.main.html(`
        <div class="guide-container">
            <div class="guide-sidebar" id="guide-sidebar"></div>
            <div class="guide-content" id="guide-content">
                <div class="guide-welcome">
                    <h2>Corrugated Box Estimating Guide</h2>
                    <p>Select a box style from the left to view step-by-step estimating instructions, blank size formulas, machine routing, and CRM integration guides.</p>
                    <div class="quick-links">
                        <a href="/app/corrugated-estimate/new" class="btn btn-primary btn-sm">New Estimate</a>
                        <a href="/app/corrugated-machine" class="btn btn-default btn-sm">View Machines</a>
                        <a href="/app/corrugated-box-style" class="btn btn-default btn-sm">Box Styles</a>
                    </div>
                </div>
            </div>
        </div>
    `);

    // Build sidebar
    var sidebar = page.main.find("#guide-sidebar");
    var sidebarHtml = '<h4>Box Styles</h4>';
    Object.keys(GUIDE_DATA).forEach(function(key) {
        sidebarHtml += '<div class="guide-nav-item" data-style="' + key + '">';
        sidebarHtml += '<strong>' + key + '</strong><br>';
        sidebarHtml += '<span class="text-muted">' + GUIDE_DATA[key].title + '</span>';
        sidebarHtml += '</div>';
    });
    sidebarHtml += '<hr><h4>How-To</h4>';
    sidebarHtml += '<div class="guide-nav-item" data-style="CRM_LINK"><strong>Link CRM</strong><br><span class="text-muted">Leads & Contacts</span></div>';
    sidebarHtml += '<div class="guide-nav-item" data-style="SALES_ORDER"><strong>Sales Order</strong><br><span class="text-muted">Convert Estimate</span></div>';
    sidebar.html(sidebarHtml);

    // Click handler
    sidebar.on("click", ".guide-nav-item", function() {
        sidebar.find(".guide-nav-item").removeClass("active");
        $(this).addClass("active");
        var style = $(this).data("style");
        _renderGuide(page, style);
    });

    // Auto-select from URL params
    var params = frappe.utils.get_url_params();
    if (params.style) {
        var key = params.style.toUpperCase().replace("-","");
        if (GUIDE_DATA[key]) {
            sidebar.find('[data-style="' + key + '"]').click();
        }
    }
};

function _renderGuide(page, styleKey) {
    var content = page.main.find("#guide-content");

    if (styleKey === "CRM_LINK") {
        content.html(_renderCrmGuide());
        return;
    }
    if (styleKey === "SALES_ORDER") {
        content.html(_renderSalesOrderGuide());
        return;
    }

    var g = GUIDE_DATA[styleKey];
    if (!g) { content.html("<p>Style not found.</p>"); return; }

    var html = '<div class="guide-detail">';

    // Header
    html += '<div class="guide-header">';
    html += '<h2>' + g.title + '</h2>';
    html += '<span class="badge badge-info">' + g.fefco + '</span>';
    html += '</div>';

    // Description
    html += '<div class="guide-section"><h3>Description</h3>' + g.description + '</div>';

    // When to use
    html += '<div class="guide-section"><h3>When to Use</h3>' + g.when_to_use + '</div>';

    // Dimensions explained
    html += '<div class="guide-section"><h3>Understanding L x W x D</h3>' + g.dimensions + '</div>';

    // Blank formula with SVG
    html += '<div class="guide-section"><h3>Blank Size Formula</h3>';
    html += '<div class="formula-box">' + g.formula + '</div>';
    html += '<div class="blank-diagram">' + g.svg + '</div>';
    html += '</div>';

    // Step by step
    html += '<div class="guide-section"><h3>Step-by-Step: Create an Estimate</h3><ol class="steps-list">';
    g.steps.forEach(function(s) { html += '<li>' + s + '</li>'; });
    html += '</ol></div>';

    // Machine routing
    html += '<div class="guide-section"><h3>Machine Routing</h3>' + g.routing + '</div>';

    // Die layout (if applicable)
    if (g.die_layout) {
        html += '<div class="guide-section"><h3>Die Layout</h3>' + g.die_layout + '</div>';
    }

    html += '</div>';
    content.html(html);
}

function _renderCrmGuide() {
    return `<div class="guide-detail">
        <div class="guide-header"><h2>Linking CRM Leads & Contacts</h2></div>
        <div class="guide-section">
            <h3>Link a CRM Lead to an Estimate</h3>
            <ol class="steps-list">
                <li>Open or create a Corrugated Estimate</li>
                <li>In the header section, find the <strong>CRM Lead</strong> field</li>
                <li>Click the field and search for the lead by name or ID</li>
                <li>Select the lead - the link is now established</li>
                <li>Save the estimate</li>
            </ol>
            <p class="tip">You can also create estimates directly from a CRM Lead using the "New Estimate" button on the Lead form (requires Corrugated CRM app).</p>
        </div>
        <div class="guide-section">
            <h3>Link a CRM Deal</h3>
            <ol class="steps-list">
                <li>On the estimate form, find the <strong>CRM Deal</strong> field</li>
                <li>Search and select the deal</li>
                <li>This connects the estimate to the sales pipeline for tracking</li>
            </ol>
        </div>
        <div class="guide-section">
            <h3>Link a Customer</h3>
            <ol class="steps-list">
                <li>The <strong>Customer</strong> field links to ERPNext Customer records</li>
                <li>Once linked, the estimate shows in the Customer's Estimate History tab</li>
                <li>You can view all estimates for a customer from their Customer form</li>
            </ol>
        </div>
        <div class="guide-section">
            <h3>Contact / Email</h3>
            <p>Use the <strong>Contact / Email</strong> field to store the primary contact for this estimate. This is a free-text field for quick reference.</p>
        </div>
    </div>`;
}

function _renderSalesOrderGuide() {
    return `<div class="guide-detail">
        <div class="guide-header"><h2>Converting an Estimate to a Sales Order</h2></div>
        <div class="guide-section">
            <h3>Prerequisites</h3>
            <ul>
                <li>The estimate must have at least one quantity break row with pricing</li>
                <li>The estimate status should not be "Rejected"</li>
                <li>No existing Sales Order should be linked yet</li>
            </ul>
        </div>
        <div class="guide-section">
            <h3>Steps</h3>
            <ol class="steps-list">
                <li>Open the estimate you want to convert</li>
                <li>Click the <strong>Integrate</strong> dropdown in the top-right toolbar</li>
                <li>Select <strong>Convert to Sales Order</strong></li>
                <li>If the estimate has multiple quantity breaks, you'll be asked to select which one to use</li>
                <li>Confirm the conversion - a new Sales Order will be created with the selected quantity and pricing</li>
                <li>The estimate's <strong>Sales Order</strong> field will auto-populate with the new SO number</li>
                <li>A "View Sales Order" button will appear under the Integrate menu</li>
            </ol>
        </div>
        <div class="guide-section">
            <h3>After Conversion</h3>
            <p>The Sales Order is linked back to the estimate via the <strong>corrugated_estimate_ref</strong> custom field. You can navigate between them freely. The estimate status can be changed to "Accepted" to reflect the won deal.</p>
        </div>
    </div>`;
}


// ══════════════════════════════════════════════════════════════════════════════
// GUIDE DATA — Content for each box style
// ══════════════════════════════════════════════════════════════════════════════

var GUIDE_DATA = {
    "RSC": {
        title: "Regular Slotted Container",
        fefco: "FEFCO 0201",
        description: "<p>The RSC is the most common corrugated box. All four flaps are the same length, and the outer flaps meet at the center of the box when folded. It's manufactured from a single piece of corrugated board with a glued manufacturer's joint.</p>",
        when_to_use: "<p>Use RSC for general-purpose shipping, storage, and retail. It's the most economical box style and runs efficiently on FFG (Flexo Folder Gluer) machines. Best for items that don't require tight tolerances or special protection.</p>",
        dimensions: "<p><strong>L (Length)</strong> = longest dimension of the box opening<br><strong>W (Width)</strong> = shorter dimension of the box opening<br><strong>D (Depth)</strong> = height of the box (top to bottom)</p><p>All dimensions are <strong>inside measurements in inches</strong>.</p>",
        formula: "<code>Blank Length = 2 x (L + W) + 1.25\" (joint)</code><br><code>Blank Width = 2 x D + 4 x caliper</code><br><p class='text-muted'>Caliper = flute thickness (C-flute = 0.146\")</p>",
        svg: _svgRSC(),
        steps: [
            "Navigate to <strong>Corrugated Estimating > New Estimate</strong>",
            "Set <strong>Box Style = RSC</strong>",
            "Select <strong>Wall Type</strong> (Single Wall, Double Wall, or Triple Wall)",
            "Select <strong>Flute Type</strong> (C, B, or E flute)",
            "Enter <strong>Length Inside</strong>, <strong>Width Inside</strong>, and <strong>Depth Inside</strong> in inches",
            "The <strong>Calculated Blank Size</strong> section auto-fills with blank dimensions and area",
            "Set <strong># Colors</strong> and <strong>Print Method</strong> if needed",
            "Review <strong>Cost Model</strong> defaults (waste %, overhead %, margin %)",
            "Add one or more <strong>Quantity Break</strong> rows with the desired quantities",
            "The system calculates Material, Converting, Overhead, Freight, COGS, and Sell Price for each row",
            "Save the estimate - routing and CAD file generate automatically"
        ],
        routing: "<p>RSC boxes route to <strong>Flexo Folder Gluers (FFG)</strong> which handle print, score, fold, and glue in a single inline pass:</p><ul><li><strong>Machine 146</strong> (37\" Lang FFG) — for blanks up to 42\" x 92\", 250/min</li><li><strong>Machine 148</strong> (47\" Apstar FFG) — for blanks up to 59\" x 110\", 240/min</li></ul><p>If the blank is too narrow for FFGs (< 25\" width), it routes to Machine 110 (Slitter/Scorer) + Machine 150 (J&L Specialty Folder).</p>",
        die_layout: null,
    },

    "FOL": {
        title: "Full Overlap",
        fefco: "FEFCO 0203",
        description: "<p>The FOL is similar to an RSC but the outer flaps overlap completely when closed, providing extra stacking strength and cushioning. The inner flaps remain standard length (D/2).</p>",
        when_to_use: "<p>Use FOL when the box needs extra top/bottom strength for heavy items or stacking. Common for produce shipping, heavy industrial parts, and palletized goods that bear significant top loads.</p>",
        dimensions: "<p>Same as RSC: <strong>L</strong> (opening length), <strong>W</strong> (opening width), <strong>D</strong> (height). The overlap doesn't change the blank formula — it's the same blank as RSC but the die cuts the flaps differently.</p>",
        formula: "<code>Blank Length = 2 x (L + W) + 1.25\" (same as RSC)</code><br><code>Blank Width = 2 x D + 4 x caliper (same as RSC)</code>",
        svg: _svgFOL(),
        steps: [
            "Navigate to <strong>New Estimate</strong>",
            "Set <strong>Box Style = FOL</strong>",
            "Enter dimensions L x W x D in inches",
            "The blank calculates identically to RSC",
            "Check <strong>Die-Cut / Special Processing</strong> if custom flap cuts are needed",
            "Add quantity rows and save"
        ],
        routing: "<p>Routes the same as RSC — inline FFG (Machine 146 or 148). The flap overlap is handled by the die tooling, not a different machine.</p>",
        die_layout: null,
    },

    "HSC": {
        title: "Half Slotted Container",
        fefco: "FEFCO 0202",
        description: "<p>The HSC has flaps on only one end (typically the bottom). The other end is open, making it ideal for sliding items in from the top or for use as a lid/sleeve over another box.</p>",
        when_to_use: "<p>Use HSC for telescope-style packaging (lid + bottom), open-top bins, or when items need to be loaded from the top. Often paired with another HSC to create a two-piece telescope box.</p>",
        dimensions: "<p><strong>L</strong> and <strong>W</strong> are the opening dimensions. <strong>D</strong> is the height (depth of the open container). The blank is shorter than RSC because it only has flaps on one end.</p>",
        formula: "<code>Blank Length = 2 x (L + W) + 1.25\"</code><br><code>Blank Width = D + D/2 + 2 x caliper</code><br><p class='text-muted'>Only 1.5x depth (body + one set of flaps)</p>",
        svg: _svgHSC(),
        steps: [
            "Set <strong>Box Style = HSC</strong>",
            "Enter L x W x D (D = depth of the open container)",
            "Note the blank width is smaller than RSC (only bottom flaps)",
            "No die-cut needed for standard HSC",
            "Add quantities and save"
        ],
        routing: "<p>HSC blanks are often narrower than FFG minimums. Routing typically goes to:<ul><li><strong>Machine 126</strong> (Flexo Press) for printing</li><li><strong>Machine 110</strong> (Slitter/Scorer) for scoring</li></ul><p>No fold/glue step needed if used as a sleeve.</p>",
        die_layout: null,
    },

    "TRAY": {
        title: "Tray",
        fefco: "Various",
        description: "<p>Trays are open-top containers formed from a cross-shaped blank. The side walls fold up and corner ears tuck in to create a rigid tray. Common as display trays, food trays, and assembly trays.</p>",
        when_to_use: "<p>Use TRAY for shallow open-top containers, display packaging, food service trays, and auto-bottom retail displays. Requires die cutting due to the cross-shaped blank.</p>",
        dimensions: "<p><strong>L</strong> = tray length (inside), <strong>W</strong> = tray width (inside), <strong>D</strong> = wall height. Typically D is small relative to L and W.</p>",
        formula: "<code>Blank Length = L + 2D + 2 x 1.25\"</code><br><code>Blank Width = W + 2D + 2 x caliper</code><br><p class='text-muted'>Cross-shaped pattern with corner ears</p>",
        svg: _svgTRAY(),
        steps: [
            "Set <strong>Box Style = TRAY</strong>",
            "Enter L x W x D (D = wall height, usually 2-6 inches)",
            "Check <strong>Die-Cut / Special Processing</strong> (required for trays)",
            "The system routes to Machine 130 (Rotary Die Cutter) + Machine 150 (J&L Specialty Folder)",
            "Die layout auto-calculates outs and waste percentage",
            "Set tooling cost (die tooling typically $300-$600 for trays)",
            "Add quantities and save"
        ],
        routing: "<p>Trays require die cutting and specialty folding:</p><ul><li><strong>Machine 130</strong> (2-Color Ward RDC) — die cut + print, 200/min</li><li><strong>Machine 150</strong> (J&L 130\" SFG) — specialty tray fold</li></ul>",
        die_layout: "<p>The die layout shows how many tray blanks nest onto the die cutter sheet. For trays, the cross-shaped blank can waste more material at corners. Check the <strong>Die Layout Waste %</strong> — target under 30% for good utilization. The system tests both 0-degree and 90-degree rotation to find the best nesting.</p>",
    },

    "BLISS": {
        title: "Bliss Box",
        fefco: "N/A",
        description: "<p>The Bliss box (also called wrap-around) has end panels that fold over to close the box, rather than traditional flaps. No manufacturer's joint in the traditional sense — the body wraps around the product.</p>",
        when_to_use: "<p>Use BLISS for heavy-duty applications, produce, and items needing full-panel end closures. The wrap-around design provides excellent stacking strength. Common in agriculture and industrial packaging.</p>",
        dimensions: "<p><strong>L</strong> = box length (along the wrap direction), <strong>W</strong> = box width, <strong>D</strong> = box depth. The blank wraps around so L and D form the panel sequence.</p>",
        formula: "<code>Blank Length = 2 x (L + D) + 1.25\"</code><br><code>Blank Width = W + D + 2 x caliper</code><br><p class='text-muted'>Wrap-around panels: End-Body-End-Body-Joint</p>",
        svg: _svgBLISS(),
        steps: [
            "Set <strong>Box Style = BLISS</strong>",
            "Enter L x W x D",
            "Note: BLISS blanks are typically large — check machine capacity",
            "No fold/glue step (wrap-around assembly)",
            "Routes to Machine 126 (Print) + Machine 118 (SBS Auto Box) or Machine 110 (Scorer)"
        ],
        routing: "<p>Bliss boxes only need printing and scoring (no fold/glue):</p><ul><li><strong>Machine 126</strong> (100\" Flexo Press) — printing, handles large blanks up to 100\" x 199\"</li><li><strong>Machine 110</strong> (Slitter/Scorer) or <strong>Machine 118</strong> (SBS Auto Box) — scoring/slitting</li></ul>",
        die_layout: null,
    },

    "DIE-CUT": {
        title: "Die Cut Custom",
        fefco: "Various",
        description: "<p>Die-cut boxes are custom shapes cut with a steel-rule die. They can be mailers, pizza boxes, display boxes, or any non-standard shape that can't be made on a standard FFG.</p>",
        when_to_use: "<p>Use DIE-CUT for specialty packaging: mailers, retail displays, food containers, e-commerce mailers, or any shape requiring custom cuts, perforations, or non-standard fold patterns.</p>",
        dimensions: "<p><strong>L</strong> = length of the product area, <strong>W</strong> = width, <strong>D</strong> = depth/height. The actual blank shape depends on the custom die design.</p>",
        formula: "<code>Blank Length = L + 2D + 1.25\"</code><br><code>Blank Width = W + 2D</code><br><p class='text-muted'>Approximate — actual depends on die design</p>",
        svg: _svgDIECUT(),
        steps: [
            "Set <strong>Box Style = DIE-CUT</strong>",
            "Enter approximate L x W x D for the blank size estimate",
            "Check <strong>Die-Cut / Special Processing</strong>",
            "Set <strong>Tooling / Die Cost</strong> ($300-$1,500+ depending on complexity)",
            "Upload a <strong>CAD File</strong> or <strong>Print Artwork</strong> if available",
            "The system routes to Machine 130 (Rotary) or Machine 135 (Flatbed) die cutter",
            "Die layout calculates outs and waste for the die cutter sheet"
        ],
        routing: "<p>Die-cut styles route to die cutting machines:</p><ul><li><strong>Machine 130</strong> (2-Color Ward RDC) — rotary die cutter, 200/min, up to 75\" x 110\", preferred for speed</li><li><strong>Machine 135</strong> (Haire Flatbed DC) — flatbed die cutter, 50/hr, up to 60\" x 80\", for complex shapes</li></ul><p>Fold/glue goes to Machine 150 (J&L Specialty Folder).</p>",
        die_layout: "<p>Die layout is critical for die-cut boxes. The nesting optimizer tries both blank orientations (0-degree and 90-degree) on each machine to maximize outs and minimize waste. Machine 130 with its 64\" cutting surface typically yields more outs than Machine 135.</p>",
    },

    "SFF": {
        title: "Snap/Lock Bottom",
        fefco: "FEFCO 0210",
        description: "<p>The SFF (Snap-Fold/Lock Bottom) has a standard RSC-style top with interlocking lock tabs on the bottom. When erected, the bottom locks into place automatically without tape or glue.</p>",
        when_to_use: "<p>Use SFF for retail packaging, e-commerce, and applications where fast assembly is needed. The auto-lock bottom speeds up packing operations. Requires die cutting for the lock tab geometry.</p>",
        dimensions: "<p>Same as RSC: <strong>L</strong> (length), <strong>W</strong> (width), <strong>D</strong> (depth). The blank formula is identical to RSC, but the bottom flaps have lock tab cutouts.</p>",
        formula: "<code>Blank Length = 2 x (L + W) + 1.25\" (same as RSC)</code><br><code>Blank Width = 2 x D + 4 x caliper (same as RSC)</code><br><p class='text-muted'>Lock tabs are cut into the bottom flap zone</p>",
        svg: _svgSFF(),
        steps: [
            "Set <strong>Box Style = SFF</strong>",
            "Enter L x W x D in inches",
            "Check <strong>Die-Cut / Special Processing</strong> (required for lock tabs)",
            "Set die tooling cost (typically $400-$800 for lock bottom dies)",
            "Routes to Machine 130 (Die Cut) + Machine 150 (Specialty Fold)",
            "Add quantities and save"
        ],
        routing: "<p>SFF requires die cutting for the lock tabs and specialty folding:</p><ul><li><strong>Machine 130</strong> (2-Color Ward RDC) — die cut + print</li><li><strong>Machine 150</strong> (J&L 130\" SFG) — snap/lock bottom fold</li></ul>",
        die_layout: "<p>Similar to RSC blank size but the die has lock tab geometry. The nesting calculator treats it as a rectangular blank. Check waste percentage and compare Machine 130 vs 135 for best utilization.</p>",
    },
};


// ══════════════════════════════════════════════════════════════════════════════
// SVG BLANK DIAGRAMS
// ══════════════════════════════════════════════════════════════════════════════

function _svgRSC() {
    return `<svg viewBox="0 0 360 200" style="max-width:600px;width:100%;">
        <defs><style>.cut{fill:none;stroke:#c00;stroke-width:1.5}.score{fill:none;stroke:#2490EF;stroke-width:1;stroke-dasharray:5,3}.panel{fill:#2490EF;fill-opacity:0.1}.flap{fill:#28a745;fill-opacity:0.1}.joint{fill:#c00;fill-opacity:0.1}.lbl{font:10px sans-serif;fill:#333;text-anchor:middle}.dim{font:9px sans-serif;fill:#666;text-anchor:middle}</style></defs>
        <!-- Panels -->
        <rect x="15" y="55" width="20" height="80" class="joint"/><text x="25" y="100" class="lbl">J</text>
        <rect x="35" y="55" width="70" height="80" class="panel"/><text x="70" y="100" class="lbl">W</text>
        <rect x="105" y="55" width="90" height="80" class="panel"/><text x="150" y="100" class="lbl">L</text>
        <rect x="195" y="55" width="70" height="80" class="panel"/><text x="230" y="100" class="lbl">W</text>
        <rect x="265" y="55" width="90" height="80" class="panel"/><text x="310" y="100" class="lbl">L</text>
        <!-- Bottom flaps -->
        <rect x="35" y="135" width="70" height="40" class="flap"/><rect x="105" y="135" width="90" height="40" class="flap"/>
        <rect x="195" y="135" width="70" height="40" class="flap"/><rect x="265" y="135" width="90" height="40" class="flap"/>
        <text x="190" y="160" class="dim">Bottom Flaps (D/2)</text>
        <!-- Top flaps -->
        <rect x="35" y="15" width="70" height="40" class="flap"/><rect x="105" y="15" width="90" height="40" class="flap"/>
        <rect x="195" y="15" width="70" height="40" class="flap"/><rect x="265" y="15" width="90" height="40" class="flap"/>
        <text x="190" y="38" class="dim">Top Flaps (D/2)</text>
        <!-- Cut lines -->
        <rect x="15" y="15" width="340" height="160" class="cut"/>
        <!-- Score lines -->
        <line x1="35" y1="55" x2="35" y2="135" class="score"/><line x1="105" y1="55" x2="105" y2="135" class="score"/>
        <line x1="195" y1="55" x2="195" y2="135" class="score"/><line x1="265" y1="55" x2="265" y2="135" class="score"/>
        <line x1="15" y1="55" x2="355" y2="55" class="score"/><line x1="15" y1="135" x2="355" y2="135" class="score"/>
        <!-- Slot cuts -->
        <line x1="105" y1="15" x2="105" y2="55" class="cut"/><line x1="195" y1="15" x2="195" y2="55" class="cut"/>
        <line x1="265" y1="15" x2="265" y2="55" class="cut"/><line x1="105" y1="135" x2="105" y2="175" class="cut"/>
        <line x1="195" y1="135" x2="195" y2="175" class="cut"/><line x1="265" y1="135" x2="265" y2="175" class="cut"/>
        <!-- Dimension labels -->
        <text x="190" y="192" class="dim">Blank Length = 2(L+W) + 1.25"</text>
        <text x="8" y="100" class="dim" transform="rotate(-90,8,100)">Blank Width = 2D + 4cal</text>
    </svg>`;
}

function _svgFOL() {
    return `<svg viewBox="0 0 360 200" style="max-width:600px;width:100%;">
        <defs><style>.cut{fill:none;stroke:#c00;stroke-width:1.5}.score{fill:none;stroke:#2490EF;stroke-width:1;stroke-dasharray:5,3}.panel{fill:#2490EF;fill-opacity:0.1}.flap{fill:#28a745;fill-opacity:0.1}.overlap{fill:#fd7e14;fill-opacity:0.15}.lbl{font:10px sans-serif;fill:#333;text-anchor:middle}.dim{font:9px sans-serif;fill:#666;text-anchor:middle}</style></defs>
        <rect x="15" y="55" width="20" height="80" style="fill:#c00;fill-opacity:0.1"/><text x="25" y="100" class="lbl">J</text>
        <rect x="35" y="55" width="70" height="80" class="panel"/><text x="70" y="100" class="lbl">W</text>
        <rect x="105" y="55" width="90" height="80" class="panel"/><text x="150" y="100" class="lbl">L</text>
        <rect x="195" y="55" width="70" height="80" class="panel"/><text x="230" y="100" class="lbl">W</text>
        <rect x="265" y="55" width="90" height="80" class="panel"/><text x="310" y="100" class="lbl">L</text>
        <!-- FULL OVERLAP flaps (outer flaps extend further) -->
        <rect x="105" y="15" width="90" height="40" class="overlap"/><rect x="265" y="15" width="90" height="40" class="overlap"/>
        <rect x="35" y="15" width="70" height="40" class="flap"/><rect x="195" y="15" width="70" height="40" class="flap"/>
        <text x="190" y="38" class="dim">Top: outer flaps FULL OVERLAP</text>
        <rect x="105" y="135" width="90" height="40" class="overlap"/><rect x="265" y="135" width="90" height="40" class="overlap"/>
        <rect x="35" y="135" width="70" height="40" class="flap"/><rect x="195" y="135" width="70" height="40" class="flap"/>
        <text x="190" y="160" class="dim">Bottom: outer flaps FULL OVERLAP</text>
        <rect x="15" y="15" width="340" height="160" class="cut"/>
        <line x1="35" y1="55" x2="35" y2="135" class="score"/><line x1="105" y1="55" x2="105" y2="135" class="score"/>
        <line x1="195" y1="55" x2="195" y2="135" class="score"/><line x1="265" y1="55" x2="265" y2="135" class="score"/>
        <line x1="15" y1="55" x2="355" y2="55" class="score"/><line x1="15" y1="135" x2="355" y2="135" class="score"/>
        <text x="190" y="192" class="dim">Same blank as RSC - die cuts flaps for overlap</text>
    </svg>`;
}

function _svgHSC() {
    return `<svg viewBox="0 0 360 160" style="max-width:600px;width:100%;">
        <defs><style>.cut{fill:none;stroke:#c00;stroke-width:1.5}.score{fill:none;stroke:#2490EF;stroke-width:1;stroke-dasharray:5,3}.panel{fill:#2490EF;fill-opacity:0.1}.flap{fill:#28a745;fill-opacity:0.1}.lbl{font:10px sans-serif;fill:#333;text-anchor:middle}.dim{font:9px sans-serif;fill:#666;text-anchor:middle}</style></defs>
        <rect x="15" y="15" width="20" height="80" style="fill:#c00;fill-opacity:0.1"/><text x="25" y="60" class="lbl">J</text>
        <rect x="35" y="15" width="70" height="80" class="panel"/><text x="70" y="60" class="lbl">W</text>
        <rect x="105" y="15" width="90" height="80" class="panel"/><text x="150" y="60" class="lbl">L</text>
        <rect x="195" y="15" width="70" height="80" class="panel"/><text x="230" y="60" class="lbl">W</text>
        <rect x="265" y="15" width="90" height="80" class="panel"/><text x="310" y="60" class="lbl">L</text>
        <rect x="35" y="95" width="70" height="40" class="flap"/><rect x="105" y="95" width="90" height="40" class="flap"/>
        <rect x="195" y="95" width="70" height="40" class="flap"/><rect x="265" y="95" width="90" height="40" class="flap"/>
        <text x="190" y="120" class="dim">Bottom Flaps (D/2)</text>
        <text x="190" y="10" class="dim" style="fill:#c00;font-weight:bold">OPEN TOP - No top flaps</text>
        <rect x="15" y="15" width="340" height="120" class="cut"/>
        <line x1="35" y1="15" x2="35" y2="95" class="score"/><line x1="105" y1="15" x2="105" y2="95" class="score"/>
        <line x1="195" y1="15" x2="195" y2="95" class="score"/><line x1="265" y1="15" x2="265" y2="95" class="score"/>
        <line x1="15" y1="95" x2="355" y2="95" class="score"/>
        <line x1="105" y1="95" x2="105" y2="135" class="cut"/><line x1="195" y1="95" x2="195" y2="135" class="cut"/><line x1="265" y1="95" x2="265" y2="135" class="cut"/>
        <text x="190" y="150" class="dim">Blank Width = D + D/2 + 2cal (shorter than RSC)</text>
    </svg>`;
}

function _svgTRAY() {
    return `<svg viewBox="0 0 300 260" style="max-width:500px;width:100%;">
        <defs><style>.cut{fill:none;stroke:#c00;stroke-width:1.5}.score{fill:none;stroke:#2490EF;stroke-width:1;stroke-dasharray:5,3}.panel{fill:#2490EF;fill-opacity:0.15}.wall{fill:#28a745;fill-opacity:0.1}.ear{fill:#fd7e14;fill-opacity:0.15}.lbl{font:10px sans-serif;fill:#333;text-anchor:middle}.dim{font:9px sans-serif;fill:#666;text-anchor:middle}</style></defs>
        <!-- Center panel -->
        <rect x="80" y="80" width="140" height="100" class="panel"/><text x="150" y="135" class="lbl">BASE (L x W)</text>
        <!-- Side walls -->
        <rect x="10" y="80" width="70" height="100" class="wall"/><text x="45" y="135" class="lbl">D</text>
        <rect x="220" y="80" width="70" height="100" class="wall"/><text x="255" y="135" class="lbl">D</text>
        <rect x="80" y="10" width="140" height="70" class="wall"/><text x="150" y="50" class="lbl">D</text>
        <rect x="80" y="180" width="140" height="70" class="wall"/><text x="150" y="220" class="lbl">D</text>
        <!-- Corner ears -->
        <rect x="10" y="10" width="70" height="70" class="ear"/><line x1="10" y1="10" x2="80" y2="80" class="score"/>
        <rect x="220" y="10" width="70" height="70" class="ear"/><line x1="290" y1="10" x2="220" y2="80" class="score"/>
        <rect x="10" y="180" width="70" height="70" class="ear"/><line x1="10" y1="250" x2="80" y2="180" class="score"/>
        <rect x="220" y="180" width="70" height="70" class="ear"/><line x1="290" y1="250" x2="220" y2="180" class="score"/>
        <!-- Cut outline -->
        <rect x="10" y="10" width="280" height="240" class="cut"/>
        <!-- Scores -->
        <line x1="80" y1="10" x2="80" y2="250" class="score"/><line x1="220" y1="10" x2="220" y2="250" class="score"/>
        <line x1="10" y1="80" x2="290" y2="80" class="score"/><line x1="10" y1="180" x2="290" y2="180" class="score"/>
        <text x="150" y="258" class="dim">Cross-shaped blank: L+2D+2(1.25") x W+2D+2cal</text>
    </svg>`;
}

function _svgBLISS() {
    return `<svg viewBox="0 0 380 140" style="max-width:600px;width:100%;">
        <defs><style>.cut{fill:none;stroke:#c00;stroke-width:1.5}.score{fill:none;stroke:#2490EF;stroke-width:1;stroke-dasharray:5,3}.panel{fill:#2490EF;fill-opacity:0.1}.end{fill:#6f42c1;fill-opacity:0.12}.lbl{font:10px sans-serif;fill:#333;text-anchor:middle}.dim{font:9px sans-serif;fill:#666;text-anchor:middle}</style></defs>
        <rect x="15" y="15" width="50" height="100" class="end"/><text x="40" y="70" class="lbl">END D</text>
        <rect x="65" y="15" width="100" height="100" class="panel"/><text x="115" y="70" class="lbl">BODY L</text>
        <rect x="165" y="15" width="50" height="100" class="end"/><text x="190" y="70" class="lbl">END D</text>
        <rect x="215" y="15" width="100" height="100" class="panel"/><text x="265" y="70" class="lbl">BODY L</text>
        <rect x="315" y="15" width="20" height="100" style="fill:#c00;fill-opacity:0.1"/><text x="325" y="70" class="lbl">J</text>
        <rect x="15" y="15" width="320" height="100" class="cut"/>
        <line x1="65" y1="15" x2="65" y2="115" class="score"/><line x1="165" y1="15" x2="165" y2="115" class="score"/>
        <line x1="215" y1="15" x2="215" y2="115" class="score"/><line x1="315" y1="15" x2="315" y2="115" class="score"/>
        <line x1="15" y1="65" x2="335" y2="65" class="score"/>
        <text x="175" y="130" class="dim">Blank = 2(L+D)+1.25" x W+D+2cal | No flaps (wrap-around)</text>
    </svg>`;
}

function _svgDIECUT() {
    return `<svg viewBox="0 0 300 200" style="max-width:500px;width:100%;">
        <defs><style>.cut{fill:none;stroke:#c00;stroke-width:1.5}.score{fill:none;stroke:#2490EF;stroke-width:1;stroke-dasharray:5,3}.panel{fill:#e83e8c;fill-opacity:0.08}.lbl{font:10px sans-serif;fill:#333;text-anchor:middle}.dim{font:9px sans-serif;fill:#666;text-anchor:middle}</style></defs>
        <rect x="15" y="15" width="270" height="150" class="panel"/>
        <rect x="15" y="15" width="270" height="150" class="cut"/>
        <line x1="55" y1="15" x2="55" y2="165" class="score"/><line x1="225" y1="15" x2="225" y2="165" class="score"/>
        <line x1="15" y1="55" x2="285" y2="55" class="score"/><line x1="15" y1="125" x2="285" y2="125" class="score"/>
        <text x="150" y="95" class="lbl" style="font-size:14px">CUSTOM DIE SHAPE</text>
        <text x="150" y="112" class="dim">Actual cut pattern varies by design</text>
        <text x="140" y="70" class="dim">L x W center area</text>
        <text x="35" y="95" class="dim" transform="rotate(-90,35,95)">D</text>
        <text x="255" y="95" class="dim" transform="rotate(-90,255,95)">D</text>
        <text x="150" y="185" class="dim">Blank = L+2D+1.25" x W+2D</text>
    </svg>`;
}

function _svgSFF() {
    return `<svg viewBox="0 0 360 200" style="max-width:600px;width:100%;">
        <defs><style>.cut{fill:none;stroke:#c00;stroke-width:1.5}.score{fill:none;stroke:#2490EF;stroke-width:1;stroke-dasharray:5,3}.panel{fill:#2490EF;fill-opacity:0.1}.flap{fill:#28a745;fill-opacity:0.1}.lock{fill:#fd7e14;fill-opacity:0.2}.lbl{font:10px sans-serif;fill:#333;text-anchor:middle}.dim{font:9px sans-serif;fill:#666;text-anchor:middle}</style></defs>
        <rect x="15" y="55" width="20" height="80" style="fill:#c00;fill-opacity:0.1"/><text x="25" y="100" class="lbl">J</text>
        <rect x="35" y="55" width="70" height="80" class="panel"/><text x="70" y="100" class="lbl">W</text>
        <rect x="105" y="55" width="90" height="80" class="panel"/><text x="150" y="100" class="lbl">L</text>
        <rect x="195" y="55" width="70" height="80" class="panel"/><text x="230" y="100" class="lbl">W</text>
        <rect x="265" y="55" width="90" height="80" class="panel"/><text x="310" y="100" class="lbl">L</text>
        <!-- Top flaps (standard) -->
        <rect x="35" y="15" width="70" height="40" class="flap"/><rect x="105" y="15" width="90" height="40" class="flap"/>
        <rect x="195" y="15" width="70" height="40" class="flap"/><rect x="265" y="15" width="90" height="40" class="flap"/>
        <text x="190" y="38" class="dim">Standard Top Flaps (D/2)</text>
        <!-- Lock bottom flaps -->
        <rect x="35" y="135" width="70" height="40" class="lock"/><rect x="105" y="135" width="90" height="40" class="lock"/>
        <rect x="195" y="135" width="70" height="40" class="lock"/><rect x="265" y="135" width="90" height="40" class="lock"/>
        <!-- Lock tab indicators -->
        <rect x="140" y="155" width="20" height="15" style="fill:#c00;fill-opacity:0.3"/><rect x="300" y="155" width="20" height="15" style="fill:#c00;fill-opacity:0.3"/>
        <text x="190" y="160" class="dim" style="fill:#c00;font-weight:bold">LOCK TABS (auto-erect bottom)</text>
        <rect x="15" y="15" width="340" height="160" class="cut"/>
        <line x1="35" y1="55" x2="35" y2="135" class="score"/><line x1="105" y1="55" x2="105" y2="135" class="score"/>
        <line x1="195" y1="55" x2="195" y2="135" class="score"/><line x1="265" y1="55" x2="265" y2="135" class="score"/>
        <line x1="15" y1="55" x2="355" y2="55" class="score"/><line x1="15" y1="135" x2="355" y2="135" class="score"/>
        <text x="190" y="192" class="dim">Same blank as RSC + lock tab die cuts on bottom</text>
    </svg>`;
}
