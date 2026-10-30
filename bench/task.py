"""A benchmark task = a steer.Env plus what only the benchmark needs."""
from steer import Env


class Task(Env):
    name = ""
    max_steps = 30          # env-step budget; tasks set it per episode in reset()

    def reset(self, seed):
        """Build the episode from `seed`. Must be deterministic."""
        raise NotImplementedError

    def reward(self):
        """Outcome checker: grade the final state only, 0..1. 1.0 is a pass."""
        raise NotImplementedError

    def oracle(self):
        """Set of actions an expert would take now: the oracle baseline and calibration reference."""
        raise NotImplementedError
