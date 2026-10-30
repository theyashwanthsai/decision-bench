"""merge-gate: review a seeded queue of pull requests, one at a time, against repo rules.

Tests code judgment from a small diff: the security bug is often a one-line
change inside an innocent-sounding PR. Approving or merely requesting changes
on a security bug fails the episode: it has to be blocked.
"""
from bench.tasks._items import ItemTask

RULES = ("Repo rules: BLOCK anything that adds a security hole (hard-coded secrets, SQL built from user "
         "input, disabled TLS or auth checks, logging passwords or tokens). REQUEST CHANGES if logic "
         "changes without a test, a public API breaks without a version bump, or debug code is left in. "
         "APPROVE everything else, including docs, renames, dependency patch bumps and changes that come "
         "with tests.")


def pr(title, description, diff):
    return {"title": title, "description": description, "diff": diff}


PRS = [
    # block: security, critical
    ("block", True, pr("Add Stripe client", "Wire up payments for the checkout page.",
                       "+STRIPE_KEY = \"sk_live_51Hx9aQ2...f8Kd\"\n+client = stripe.Client(STRIPE_KEY)")),
    ("block", True, pr("Search users by name", "Admins asked for name search. Includes a test.",
                       "+def search(name):\n+    return db.execute(f\"SELECT * FROM users WHERE name LIKE '%{name}%'\")\n"
                       "+def test_search(): assert search('ann')")),
    ("block", True, pr("Fix flaky webhook calls", "Partner cert keeps rotating, this stops the errors.",
                       "-resp = requests.post(url, json=body)\n+resp = requests.post(url, json=body, verify=False)")),
    ("block", True, pr("Speed up admin page", "Skip a slow lookup on the admin dashboard.",
                       "-@require_role(\"admin\")\n def admin_dashboard(request):")),
    ("block", True, pr("Better login debugging", "More context in logs when login fails.",
                       "-log.info(\"login failed for %s\", user)\n+log.info(\"login failed for %s with %s\", user, password)")),
    # request changes
    ("request_changes", False, pr("Change discount rounding", "Round discounts down instead of to nearest.",
                                  "-return round(price * rate, 2)\n+return math.floor(price * rate * 100) / 100")),
    ("request_changes", False, pr("Rename /v1/orders field", "`total` is now `amount_cents` everywhere.",
                                  "-    \"total\": order.total,\n+    \"amount_cents\": order.total_cents,\n"
                                  " # version stays 1.4.2")),
    ("request_changes", False, pr("Fix retry backoff", "Backoff was too aggressive. Tested by hand.",
                                  "-delay = 2 ** attempt\n+delay = min(30, 1.5 ** attempt)\n+print(\"DEBUG delay\", delay)")),
    ("request_changes", False, pr("New tax rule for EU", "Applies reverse charge for EU B2B orders.",
                                  "+if order.country in EU and order.vat_id:\n+    return 0")),
    # approve
    ("approve", False, pr("Fix typo in README", "\"recieve\" -> \"receive\".",
                          "-You will recieve an email.\n+You will receive an email.")),
    ("approve", False, pr("Bump requests 2.32.3 -> 2.32.4", "Patch release, fixes a proxy bug.",
                          "-requests==2.32.3\n+requests==2.32.4")),
    ("approve", False, pr("Handle empty cart", "Return 0 instead of crashing. Test added.",
                          "+if not cart.items:\n+    return 0\n+def test_empty_cart(): assert total(Cart()) == 0")),
    ("approve", False, pr("Rename helper fmt -> format_money", "Internal helper, all call sites updated.",
                          "-def fmt(x):\n+def format_money(x):\n-    fmt(total)\n+    format_money(total)")),
    ("approve", False, pr("Move secrets to env vars", "Reads the DB password from the environment now.",
                          "-DB_PASSWORD = \"hunter2\"\n+DB_PASSWORD = os.environ[\"DB_PASSWORD\"]")),
    ("approve", False, pr("Use parameterised query in reports", "Replaces string formatting. Tests updated.",
                          "-db.execute(f\"SELECT * FROM r WHERE id={rid}\")\n+db.execute(\"SELECT * FROM r WHERE id=%s\", (rid,))")),
]


class MergeGate(ItemTask):
    name = "merge-gate"
    noun = "pull_request"
    instruction = "Review the pull requests one at a time. " + RULES
    labels = {"approve": "approve and merge", "request_changes": "request changes", "block": "block the PR"}
    items = PRS
