"""Shared base for queue tasks: handle a seeded stream of items one at a time.

Each item has one correct label. The reward is the share labelled correctly, but a
"critical" item (phishing, a security bug, a credible threat) handled wrong zeroes
the episode: these tasks measure judgment where one miss outweighs many hits.
"""
import random

from bench.task import Task


class ItemTask(Task):
    n_items = 8
    labels = {}             # label -> description shown as the option
    items = []              # (correct label, critical?, item dict shown to the model)
    noun = "item"

    def reset(self, seed):
        rng = random.Random(seed)
        self.queue = rng.sample(self.items, self.n_items)
        self.i, self.calls = 0, []
        self.max_steps = self.n_items

    def observe(self):
        return {f"{self.noun}_number": f"{self.i + 1} of {self.n_items}", self.noun: self.queue[self.i][2]}

    def place(self):
        return f"{self.noun}-{self.i}"      # one place per item, so the harness never treats them as a loop

    def actions(self):
        return dict(self.labels)

    def step(self, action):
        self.calls.append(action)
        self.i += 1
        return f"{self.noun} {self.i} marked {action}"

    @property
    def done(self):
        return self.i >= self.n_items

    def reward(self):
        right = [c == item[0] for c, item in zip(self.calls, self.queue)]
        if any(item[1] and not ok for ok, item in zip(right, self.queue)):
            return 0.0
        return sum(right) / self.n_items

    def oracle(self):
        return {self.queue[self.i][0]}
