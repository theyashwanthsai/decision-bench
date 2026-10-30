"""repo-nav: walk a fake codebase from a bug report to the file that causes it.

Tests localisation by meaning: the report describes a symptom, not a file, and
the obvious-looking file is often a decoy (reset emails failing is a queue
routing bug, not the reset handler). The model sees folder names with one-line
summaries and each file's header comment; submitting a file ends the episode.
"""
import random
from collections import deque

from bench.task import Task

# folder: (summary, {file: header comment})
TREE = {
    "": ("repository root", {"README.md": "project overview and setup", "pyproject.toml": "dependencies and tool config"}),
    "app": ("the web application", {"main.py": "creates the app and mounts every router", "settings.py": "loads config from env vars"}),
    "app/auth": ("login, sessions, password reset", {
        "login.py": "checks passwords and starts sessions",
        "sessions.py": "session cookies: creation, expiry, renewal",
        "reset.py": "password reset: creates a token and enqueues the reset email job",
        "tokens.py": "signs and verifies reset and invite tokens",
        "mfa.py": "one-time codes for two-factor login"}),
    "app/billing": ("prices, invoices, payments", {
        "pricing.py": "computes line prices, discounts and coupons",
        "tax.py": "VAT and sales tax per country",
        "invoices.py": "builds invoice PDFs and numbers",
        "payments.py": "charges cards through the payment provider",
        "currency.py": "converts and rounds amounts between currencies"}),
    "app/orders": ("cart, checkout, order history", {
        "cart.py": "add/remove items, cart totals",
        "checkout.py": "turns a cart into an order and calls payments",
        "history.py": "lists a user's past orders, newest first",
        "inventory.py": "reserves and releases stock"}),
    "app/api": ("public HTTP endpoints", {
        "routes.py": "URL table for the public API",
        "pagination.py": "cursor pagination helpers for list endpoints",
        "rate_limit.py": "per-key request limits",
        "serializers.py": "turns models into JSON responses"}),
    "app/search": ("product search", {
        "index.py": "builds the search index nightly",
        "query.py": "parses search text and ranks results",
        "synonyms.py": "synonym list used when matching words"}),
    "workers": ("background jobs", {"runner.py": "starts worker processes and listens on queues",
                                    "schedule.py": "cron-like schedule for recurring jobs"}),
    "workers/queues": ("job queue setup", {
        "routes.py": "maps each job type to the queue it is sent to",
        "retry.py": "retry and backoff policy for failed jobs",
        "dead_letter.py": "where jobs go after too many failures"}),
    "workers/jobs": ("job implementations", {
        "send_email.py": "renders a template and sends it via SMTP",
        "export.py": "builds CSV exports for admins",
        "cleanup.py": "deletes expired sessions and temp files",
        "reindex.py": "kicks off the nightly search index build"}),
    "notifications": ("email and push", {"smtp.py": "SMTP connection settings and send()",
                                         "push.py": "mobile push notifications"}),
    "notifications/templates": ("email templates", {
        "receipt.html": "order receipt email", "reset.html": "password reset email",
        "welcome.html": "welcome email after signup", "invoice.html": "monthly invoice email"}),
    "frontend": ("browser UI", {"app.js": "client-side router and bootstrapping"}),
    "frontend/pages": ("one file per screen", {
        "checkout.js": "checkout screen: address, card form, submit button",
        "orders.js": "order history screen",
        "search.js": "search box and results list",
        "settings.js": "account settings screen"}),
    "frontend/i18n": ("translations", {"en.json": "English strings", "de.json": "German strings",
                                       "format.js": "formats dates, numbers and currency per locale"}),
    "db": ("database layer", {"models.py": "table definitions", "connection.py": "connection pool and timeouts"}),
    "db/migrations": ("schema changes", {
        "0041_add_coupons.py": "adds the coupons table",
        "0042_orders_index.py": "adds an index on orders(user_id, created_at)",
        "0043_session_ttl.py": "changes default session lifetime column"}),
    "tests": ("test suite", {"test_auth.py": "auth tests", "test_billing.py": "billing tests",
                             "conftest.py": "shared fixtures"}),
    "infra": ("deployment config", {"docker-compose.yml": "local services", "nginx.conf": "reverse proxy and timeouts"}),
}
BUGS = [
    ("Password reset emails never arrive. Receipts and welcome emails arrive fine. The reset job shows as "
     "enqueued, but no worker ever picks it up.", "workers/queues/routes.py"),
    ("Customers with a 10% coupon are charged the full price. The coupon is shown as applied in the cart.",
     "app/billing/pricing.py"),
    ("German customers see prices like '1.234,5 €' with one decimal instead of two. English is fine.",
     "frontend/i18n/format.js"),
    ("The API's /orders list skips one order between every page when clients follow the next-page cursor.",
     "app/api/pagination.py"),
    ("Users are logged out after 5 minutes instead of 7 days. Started after last week's database migration.",
     "db/migrations/0043_session_ttl.py"),
    ("Searching 'sneakers' returns nothing, but 'shoes' finds sneakers. It used to work for both.",
     "app/search/synonyms.py"),
    ("Orders placed in JPY are charged 100x too much. Other currencies are fine.", "app/billing/currency.py"),
    ("Failed card payments retry forever and customers get charged multiple times.", "workers/queues/retry.py"),
    ("Order history shows the oldest orders first, though it is supposed to be newest first.",
     "app/orders/history.py"),
    ("Two-factor codes are always rejected for users in Asia, though users in Europe log in fine.",
     "app/auth/mfa.py"),
]


def parent(d):
    return d.rsplit("/", 1)[0] if "/" in d else ""


class RepoNav(Task):
    name = "repo-nav"

    def reset(self, seed):
        rng = random.Random(seed)
        self.report, self.target = rng.choice(BUGS)
        self.dir = rng.choice(["", "", "", "app", "workers", "frontend"])
        self.submitted = None
        self.instruction = (f"Bug report: {self.report} Navigate the repository and submit the one file "
                            "that most likely contains the bug.")
        self.dist = self._distances()
        self.max_steps = self.dist[self.dir] * 2 + 6

    def _children(self, d):
        return [c for c in TREE if c and parent(c) == d]

    def _distances(self):
        """Steps from each folder to submitting the target: BFS over open/up moves."""
        home = parent(self.target)
        dist, queue = {home: 1}, deque([home])
        while queue:
            d = queue.popleft()
            for n in self._children(d) + ([parent(d)] if d else []):
                if n not in dist:
                    dist[n] = dist[d] + 1
                    queue.append(n)
        return dist

    def _moves(self):
        moves = {f"open:{c}": c for c in self._children(self.dir)}
        if self.dir:
            moves["up"] = parent(self.dir)
        return moves

    def observe(self):
        return {"current_folder": "/" + self.dir, "folders": {c.split("/")[-1] + "/": TREE[c][0] for c in self._children(self.dir)},
                "files": TREE[self.dir][1]}

    def place(self):
        return "/" + self.dir

    def memo(self):
        return f"{TREE[self.dir][0]}; files: {', '.join(TREE[self.dir][1])}"

    def actions(self):
        acts = {f"open:{c}": f"open folder {c.split('/')[-1]}/ ({TREE[c][0]})" for c in self._children(self.dir)}
        if self.dir:
            acts["up"] = f"go up to /{parent(self.dir)}"
        for f, about in TREE[self.dir][1].items():
            acts[f"submit:{self.path(f)}"] = f"submit {f} as the cause ({about})"
        return acts

    def path(self, f):
        return f"{self.dir}/{f}" if self.dir else f

    def step(self, action):
        if action.startswith("submit:"):
            self.submitted = action[7:]
            return f"submitted {self.submitted}"
        self.dir = self._moves()[action]
        return f"now in /{self.dir}"

    @property
    def done(self):
        return self.submitted is not None

    def reward(self):
        return 1.0 if self.submitted == self.target else 0.0

    def oracle(self):
        if parent(self.target) == self.dir:
            return {f"submit:{self.target}"}
        best = self.dist[self.dir] - 1
        return {a for a, d in self._moves().items() if self.dist.get(d) == best}
