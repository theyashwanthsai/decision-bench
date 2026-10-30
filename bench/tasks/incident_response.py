"""incident-response: diagnose a seeded production incident with checks, fix it, close it.

Tests diagnosis: several causes share the same alert, so the model has to run the
checks that tell them apart, read the results, and pick the matching fix. Wrong
fixes waste time; harmful ones (restarting a database mid-corruption) fail the
episode. Closing before the fix lands also fails.
"""
import random

from bench.task import Task

CHECKS = {
    "logs": "read the application error logs",
    "deploys": "list recent deploys",
    "disk": "check disk usage on the hosts",
    "certs": "check TLS certificate expiry",
    "db": "check database health and replication",
    "cpu": "check CPU and memory on the hosts",
    "deps": "check the status pages of third-party providers",
    "dns": "check DNS resolution for our domains",
}
FIXES = {
    "rollback": "roll back the latest deploy",
    "restart_app": "restart the app servers",
    "clear_disk": "rotate and delete old log files",
    "renew_cert": "renew and install the TLS certificate",
    "restart_db": "restart the primary database",
    "failover_db": "fail over to the database replica",
    "scale_up": "add more app servers",
    "switch_provider": "switch payments to the backup provider",
    "fix_dns": "restore the DNS record from the last good config",
}
NORMAL = {
    "logs": "nothing unusual in the logs", "deploys": "no deploys in the last 3 days",
    "disk": "disks at 40-55%", "certs": "all certificates valid for 60+ days",
    "db": "primary and replica healthy, lag 0.2s", "cpu": "CPU 35%, memory 60%",
    "deps": "all providers report operational", "dns": "all records resolve correctly",
}
# cause: (alerts it can raise, {check: finding}, fix, harmful fixes)
CAUSES = {
    "bad_deploy": (["checkout errors at 40%", "API error rate at 25%"],
                   {"deploys": "v2.14.0 deployed 22 minutes ago, errors began 3 minutes later",
                    "logs": "TypeError: cart.total_cents is undefined (new in v2.14.0)"},
                   "rollback", []),
    "disk_full": (["checkout errors at 40%", "API error rate at 25%"],
                  {"disk": "/var on app hosts at 100%",
                   "logs": "OSError: [Errno 28] No space left on device"},
                  "clear_disk", ["rollback"]),
    "cert_expired": (["checkout errors at 40%", "mobile app cannot connect"],
                     {"certs": "api.acme.io certificate expired 40 minutes ago",
                      "logs": "TLS handshake failed: certificate has expired"},
                     "renew_cert", []),
    "db_corruption": (["API error rate at 25%", "checkout errors at 40%"],
                      {"db": "primary reports page checksum failures on the orders table; replica clean",
                       "logs": "ERROR: invalid page in block 88213 of relation orders"},
                      "failover_db", ["restart_db"]),
    "traffic_spike": (["API latency p99 at 9s", "checkout errors at 40%"],
                      {"cpu": "CPU 99% on every app host, request rate 6x normal",
                       "logs": "worker timeout: request queue full"},
                      "scale_up", ["restart_app"]),
    "provider_down": (["checkout errors at 40%", "payment failures at 60%"],
                      {"deps": "primary payment provider: major outage since 14:02",
                       "logs": "PaymentGatewayError: upstream 503 from provider"},
                      "switch_provider", ["rollback"]),
    "dns_broken": (["mobile app cannot connect", "API error rate at 25%"],
                   {"dns": "api.acme.io resolves to NXDOMAIN; record changed 30 minutes ago",
                    "logs": "nothing unusual in the logs: traffic dropped to near zero"},
                   "fix_dns", []),
    "memory_leak": (["API latency p99 at 9s", "API error rate at 25%"],
                    {"cpu": "memory at 97% and climbing on app hosts; up 18 days without restart",
                     "logs": "OutOfMemoryError in worker processes"},
                    "restart_app", ["scale_up"]),
}


class IncidentResponse(Task):
    name = "incident-response"

    def reset(self, seed):
        rng = random.Random(seed)
        self.cause = rng.choice(sorted(CAUSES))
        alerts, self.findings, self.fix, self.harmful = CAUSES[self.cause]
        self.alert = rng.choice(alerts)
        self.results, self.applied, self.fixed, self.failed, self.closed = {}, [], False, False, False
        self.instruction = (f"You are on call. Alert: {self.alert}. Find the cause with checks, apply the "
                            "fix that addresses it, then close the incident. A harmful action makes things worse.")
        self.max_steps = 12

    def observe(self):
        return {"alert": self.alert, "check_results": dict(self.results), "fixes_applied": list(self.applied),
                "status": "resolved, errors back to normal" if self.fixed else "ongoing"}

    def actions(self):
        acts = {f"check:{c}": d for c, d in CHECKS.items()}
        acts.update({f"fix:{f}": d for f, d in FIXES.items()})
        acts["close"] = "close the incident"
        return acts

    def step(self, action):
        kind, _, what = action.partition(":")
        if kind == "check":
            self.results[what] = self.findings.get(what, NORMAL[what])
            return self.results[what]
        if kind == "fix":
            self.applied.append(what)
            if what in self.harmful:
                self.failed = True
                return "that made it worse: outage widened"
            if what == self.fix:
                self.fixed = True
                return "errors dropping back to normal"
            return "no effect, errors continue"
        self.closed = True
        return "incident closed"

    @property
    def done(self):
        return self.closed or self.failed

    def reward(self):
        return 1.0 if self.closed and self.fixed and not self.failed else 0.0

    def oracle(self):
        if self.fixed:
            return {"close"}
        telling = {c for c in self.findings if c != "logs"}        # logs alone can be ambiguous
        if not telling & set(self.results):
            return {f"check:{c}" for c in self.findings if c not in self.results}
        return {f"fix:{self.fix}"}
