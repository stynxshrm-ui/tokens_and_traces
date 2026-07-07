"""
kb_articles.py
Fake knowledge base articles for the support triage demo.
12 articles across 4 categories: billing, technical, account, general.
"""

KB_ARTICLES = [
    # ── BILLING ──────────────────────────────────────────────────────────────
    {
        "id": "KB001",
        "category": "billing",
        "title": "How to update your payment method",
        "content": (
            "To update your payment method, go to Account Settings > Billing > "
            "Payment Methods. Click 'Add New Payment Method' and enter your card details. "
            "Your new card will be charged on the next billing cycle. "
            "Old payment methods are not deleted automatically — you can remove them "
            "from the same page once your new method is confirmed."
        ),
    },
    {
        "id": "KB002",
        "category": "billing",
        "title": "Understanding your invoice",
        "content": (
            "Your monthly invoice includes your base subscription fee plus any usage "
            "overages. Overages are calculated at the end of each billing period based "
            "on your plan limits. You can view a line-by-line breakdown in "
            "Account Settings > Billing > Invoice History. Invoices are emailed to your "
            "billing contact address on the 1st of each month."
        ),
    },
    {
        "id": "KB003",
        "category": "billing",
        "title": "How to cancel your subscription",
        "content": (
            "To cancel your subscription, navigate to Account Settings > Billing > "
            "Subscription. Click 'Cancel Subscription' and follow the confirmation prompts. "
            "Your access continues until the end of your current billing period — you will "
            "not be charged again. Data is retained for 90 days after cancellation. "
            "Cancellations cannot be processed retroactively."
        ),
    },
    # ── TECHNICAL ────────────────────────────────────────────────────────────
    {
        "id": "KB004",
        "category": "technical",
        "title": "API rate limits and how to handle them",
        "content": (
            "Standard plans are limited to 1,000 API requests per minute. "
            "Exceeding this returns HTTP 429 Too Many Requests. "
            "The response includes a Retry-After header indicating when to retry. "
            "Implement exponential backoff with jitter to handle rate limits gracefully. "
            "Enterprise plans have custom rate limits — contact your account manager."
        ),
    },
    {
        "id": "KB005",
        "category": "technical",
        "title": "Troubleshooting webhook delivery failures",
        "content": (
            "Webhooks that fail 5 consecutive times are automatically disabled. "
            "To re-enable, go to Developer Settings > Webhooks and click 'Re-enable'. "
            "Your endpoint must return HTTP 200 within 10 seconds — otherwise the "
            "delivery is marked as failed and retried with exponential backoff. "
            "Check the delivery log for the exact response body and status code your "
            "endpoint returned."
        ),
    },
    {
        "id": "KB006",
        "category": "technical",
        "title": "SDK installation and authentication",
        "content": (
            "Install the SDK with: pip install acme-sdk. "
            "Authenticate by setting the ACME_API_KEY environment variable, or pass "
            "api_key= to the client constructor. "
            "Never hardcode your API key in source code or commit it to version control. "
            "If your key is exposed, revoke it immediately in Developer Settings > API Keys "
            "and generate a replacement."
        ),
    },
    {
        "id": "KB012",
        "category": "technical",
        "title": "Debugging 401 Unauthorized errors",
        "content": (
            "HTTP 401 means your API key is missing, expired, or invalid. "
            "Verify your key exists and is active in Developer Settings > API Keys. "
            "Keys are automatically revoked if detected in public repositories via our "
            "GitHub secret scanning integration. "
            "Generate a new key and rotate it into your environment variables. "
            "Do not reuse revoked keys."
        ),
    },
    # ── ACCOUNT ──────────────────────────────────────────────────────────────
    {
        "id": "KB007",
        "category": "account",
        "title": "How to reset your password",
        "content": (
            "Click 'Forgot Password' on the login page and enter your account email. "
            "A reset link will be sent within 2 minutes — the link is valid for 24 hours. "
            "If you don't receive the email, check your spam folder and verify the address "
            "matches your account. "
            "If your account uses SSO, password reset is managed by your identity provider."
        ),
    },
    {
        "id": "KB008",
        "category": "account",
        "title": "Adding team members to your organisation",
        "content": (
            "Go to Settings > Team > Invite Members and enter the email addresses of "
            "teammates you want to add. They will receive an invitation email valid for 72 hours. "
            "Available roles: Admin (full access), Developer (API and settings), "
            "Viewer (read-only dashboards). "
            "Seats are counted against your plan limit — check Settings > Team > Seat Usage "
            "before inviting."
        ),
    },
    {
        "id": "KB009",
        "category": "account",
        "title": "Transferring account ownership",
        "content": (
            "Only the current account owner can initiate a transfer. "
            "Go to Settings > Team > Ownership Transfer and select the new owner from your "
            "existing team members. The new owner must have a verified email address. "
            "The transfer takes effect immediately and cannot be undone without the new "
            "owner's cooperation."
        ),
    },
    # ── GENERAL ──────────────────────────────────────────────────────────────
    {
        "id": "KB010",
        "category": "general",
        "title": "How to contact support",
        "content": (
            "Support channels: live chat (available 09:00–18:00 EST, Mon–Fri), "
            "email at support@acme.io, or submit a ticket in your dashboard under Help > "
            "New Ticket. Standard response time is 24 hours. "
            "Priority support customers have a dedicated Slack channel and a 4-hour SLA. "
            "For billing emergencies outside business hours, use the emergency billing form "
            "in your dashboard."
        ),
    },
    {
        "id": "KB011",
        "category": "general",
        "title": "Data retention and export",
        "content": (
            "We retain your data for 90 days after account cancellation. "
            "To export before cancelling, go to Settings > Data > Export. "
            "Your data is prepared as a ZIP archive and emailed to your account address "
            "within 24 hours. "
            "Exports include: all project data, API logs (last 30 days), "
            "team member list, and billing history. "
            "We do not retain payment card details."
        ),
    },
]
