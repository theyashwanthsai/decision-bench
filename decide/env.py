"""The contract a task implements. Deterministic given the seed."""


class Env:
    name = ""
    instruction = ""        # the goal, shown to the model on every step
    max_steps = 30

    def reset(self, seed):
        """Build the episode from `seed`. Must be deterministic."""
        raise NotImplementedError

    def observe(self):
        """What the model sees now: str or a JSON-able dict."""
        raise NotImplementedError

    def actions(self):
        """Legal actions now: {action_id: description}. 2..24 entries."""
        raise NotImplementedError

    def step(self, action):
        """Apply `action`; return a short feedback string."""
        raise NotImplementedError

    @property
    def done(self):
        raise NotImplementedError

    def reward(self):
        """Outcome checker: grade the final state only, 0..1. 1.0 is a pass."""
        raise NotImplementedError

    def oracle(self):
        """Set of actions an expert would take now. Used for the oracle baseline and calibration."""
        raise NotImplementedError
