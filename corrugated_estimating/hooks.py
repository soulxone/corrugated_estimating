app_name = "corrugated_estimating"
app_title = "Corrugated Estimating"
app_publisher = "Welchwyse"
app_description = "Corrugated box estimating with full revision history, linked to CRM and Customer"
app_email = "admin@welchwyse.com"
app_license = "MIT"

# ── DocType JS overrides ───────────────────────────────────────────────────────
# Injects "Estimate History" tab into ERPNext Customer form
doctype_js = {
    "Customer": "public/js/customer_estimates.js",
}

# ── Fixtures ──────────────────────────────────────────────────────────────────
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [
            ["name", "in", [
                "Customer-estimate_history_section",
            ]]
        ]
    }
]
