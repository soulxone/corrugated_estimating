app_name = "corrugated_estimating"
app_title = "Corrugated Estimating"
app_publisher = "Welchwyse"
app_description = "Corrugated box estimating with full revision history, linked to CRM and Customer"
app_email = "admin@welchwyse.com"
app_license = "MIT"

app_include_js = "/assets/corrugated_estimating/js/corrugated_estimating.bundle.js"

# ── After Install ────────────────────────────────────────────────────────────
after_install = "corrugated_estimating.corrugated_estimating.setup.after_install"

# ── DocType JS overrides ───────────────────────────────────────────────────────
# customer_estimates.js  → injects "Estimate History" tab into ERPNext Customer form
# Corrugated Estimate DocType JS is loaded automatically from doctype directory
doctype_js = {
    "Customer":     "public/js/customer_estimates.js",
    "Sales Order":  "public/js/sales_order_estimate.js",
    "Job Card":     "public/js/job_card_estimate.js",
}

# ── Fixtures ──────────────────────────────────────────────────────────────────
# Export Corrugated Estimating Settings so default values ship with the app.
# Run: bench --site <site> export-fixtures --app corrugated_estimating
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [
            ["name", "in", [
                "Customer-estimate_history_section",
                "Sales Order-corrugated_estimate_ref",
                "Job Card-corrugated_estimate_ref",
            ]]
        ]
    },
    # Export the singleton settings doc so installs get sensible defaults
    {
        "doctype": "Corrugated Estimating Settings",
        "filters": []
    },
    # Print format: full cost report PDF
    {
        "doctype": "Print Format",
        "filters": [["name", "in", ["Corrugated Cost Report"]]]
    },
    # ── Workspace: Corrugated Estimating desk page ────────────────────────────
    {
        "doctype": "Workspace",
        "filters": [["name", "in", ["Estimating", "Corrugated Estimating"]]]
    },
    # ── Machine Master Data ──────────────────────────────────────────────────
    {
        "doctype": "Corrugated Machine",
        "filters": []
    },
]
