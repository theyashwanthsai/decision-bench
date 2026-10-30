"""support-desk: resolve a seeded customer ticket by the support policy, in a safe order.

Tests gathering facts before acting: the right resolution depends on what the
order lookup shows (days since delivery, stock, value, fraud flag), so the model
has to get the order number, look the order up, and verify the customer before
any refund or replacement. Paying out to an unverified customer fails on the spot.
"""
import random

from bench.task import Task

POLICY = ("Support policy: verify the customer's identity before any refund or replacement. ESCALATE to a "
          "supervisor if the order is over $500 or the account is flagged for fraud. Damaged, wrong or lost "
          "items within 30 days of delivery: REPLACE if in stock, otherwise REFUND. Unwanted items within 30 "
          "days: REFUND. Past 30 days, or a parcel that is still on its way: REPLY explaining the policy or "
          "the delivery status. Look the order up before deciding.")
ISSUES = {
    "damaged": "My {item} arrived smashed, the box was crushed. What can you do?",
    "wrong": "I ordered a {item} but got something completely different.",
    "lost": "My {item} never showed up. Tracking hasn't moved in ages.",
    "unwanted": "I changed my mind about the {item}, can I send it back for my money?",
    "late": "Where is my {item}? I ordered it last week.",
}
ITEMS = ["coffee grinder", "desk lamp", "running jacket", "blender", "bluetooth speaker", "yoga mat", "backpack"]
RESOLUTIONS = {"refund": "issue a full refund", "replace": "ship a free replacement",
               "escalate": "escalate to a supervisor", "reply": "reply explaining the policy or delivery status"}


class SupportDesk(Task):
    name = "support-desk"
    instruction = "Resolve the customer's ticket. " + POLICY

    def reset(self, seed):
        rng = random.Random(seed)
        self.issue, item = rng.choice(sorted(ISSUES)), rng.choice(ITEMS)
        self.order_no = f"A{rng.randint(10000, 99999)}"
        flagged = rng.random() < 0.15
        value = rng.choice([24, 39, 59, 89, 129, 249]) if rng.random() < 0.85 else rng.choice([640, 899, 1250])
        days = rng.choice([3, 8, 15, 22, 27, 41, 55]) if self.issue != "late" else None
        stock = rng.random() < 0.6
        self.facts = {"order": self.order_no, "item": item, "value_usd": value, "account_flagged_for_fraud": flagged,
                      "in_stock": stock,
                      "delivery": "in transit, arriving in 2 days" if self.issue == "late" else
                                  ("lost in transit" if self.issue == "lost" else f"delivered {days} days ago")}
        if self.issue == "lost":
            days = 0
        if flagged or value > 500:
            self.answer = "escalate"
        elif self.issue == "late" or (days or 0) > 30:
            self.answer = "reply"
        elif self.issue == "unwanted":
            self.answer = "refund"
        else:
            self.answer = "replace" if stock else "refund"
        message = ISSUES[self.issue].format(item=item)
        self.has_number = rng.random() < 0.4
        if self.has_number:
            message += f" Order {self.order_no}."
        self.chat = [f"customer: {message}"]
        self.verified = self.looked_up = False
        self.resolved, self.failed = None, False
        self.max_steps = 10

    def observe(self):
        return {"conversation": list(self.chat), "identity_verified": self.verified,
                "order_record": self.facts if self.looked_up else "not looked up yet"}

    def actions(self):
        acts = {"ask_order": "ask the customer for their order number",
                "verify": "send a verification code to the email on file",
                "lookup": "look up the order in the order system"}
        acts.update(RESOLUTIONS)
        return acts

    def step(self, action):
        if action == "ask_order":
            self.has_number = True
            self.chat.append(f"customer: It's {self.order_no}.")
            return "customer gave the order number"
        if action == "verify":
            self.verified = True
            self.chat.append("customer: Got the code, it's 4417.")
            return "identity verified"
        if action == "lookup":
            if not self.has_number:
                return "no order number to look up"
            self.looked_up = True
            return "order record loaded"
        self.resolved = action
        if action in ("refund", "replace") and not self.verified:
            self.failed = True
            return "paid out to an unverified customer: account takeover risk"
        return f"ticket resolved: {RESOLUTIONS[action]}"

    @property
    def done(self):
        return self.resolved is not None

    def reward(self):
        return 1.0 if self.resolved == self.answer and self.looked_up and not self.failed else 0.0

    def oracle(self):
        need = set()
        if not self.has_number:
            need.add("ask_order")
        elif not self.looked_up:
            need.add("lookup")
        if self.answer in ("refund", "replace") and not self.verified:
            need.add("verify")
        return need or {self.answer}
