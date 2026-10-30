"""Play one seeded episode with a steer Agent or a baseline, and score episodes."""
import random

from steer import Agent

HARNESSES = {
    "default": dict(),                                                   # steer's defaults
    "notes": dict(notes=True),
    "bare": dict(notes=False, shortcuts=False, gate=None, novelty=None),
}


def episode(task_cls, seed, player):
    """`player` is a steer Agent, 'oracle' or 'random'."""
    task = task_cls()
    task.reset(seed)
    if isinstance(player, Agent):
        run = player.run(task, max_steps=task.max_steps, probe=lambda env: sorted(env.oracle()))
        name = f"{player.name} [{harness_name(player)}]"
    else:
        run = baseline(task, player, random.Random(seed))
        name = player
    reward = task.reward()
    return {"task": task.name, "player": name, "seed": seed, "reward": reward, "passed": reward >= 1.0,
            **{k: run[k] for k in ("steps", "calls", "cost", "input_tokens", "seconds", "error", "decisions")}}


def harness_name(agent):
    c = agent.config()
    return next((n for n, h in HARNESSES.items() if c == Agent(agent.model, **h).config()), "custom")


def baseline(task, kind, rng):
    decisions, steps = [], 0
    while not task.done and steps < task.max_steps:
        acts, good = list(task.actions()), sorted(task.oracle())
        pick = rng.choice(good if kind == "oracle" else acts)
        probs = {a: (1 / len(good) if a in good else 0.0) for a in acts} if kind == "oracle" else {a: 1 / len(acts) for a in acts}
        result = task.step(pick)
        steps += 1
        decisions.append({"choice": pick, "confidence": probs[pick], "probabilities": probs,
                          "first_step": {a: a for a in acts}, "executed": [[pick, result]],
                          "escalated": False, "probe": good})
    return {"steps": steps, "calls": 0, "cost": 0.0, "input_tokens": 0, "seconds": 0, "error": None,
            "decisions": decisions}


def summarize(episodes):
    ok = [e for e in episodes if not e["error"]]
    ds = [d for e in ok for d in e["decisions"]]
    n, nd = len(ok) or 1, len(ds) or 1
    for d in ds:     # a shortcut counts as its first primitive step
        d["agree"] = d["first_step"][d["choice"]] in d["probe"]
        d["p_good"] = sum(p for o, p in d["probabilities"].items() if d["first_step"].get(o) in d["probe"])
    passes = sum(e["passed"] for e in ok)
    cost = sum(e["cost"] for e in ok)
    return {
        "episodes": len(ok), "errors": len(episodes) - len(ok),
        "reward": round(sum(e["reward"] for e in ok) / n, 4),
        "pass_rate": round(passes / n, 4),
        "step_agreement": round(sum(d["agree"] for d in ds) / nd, 4),
        "brier": round(sum((1 - d["p_good"]) ** 2 for d in ds) / nd, 4),   # vs the expert's actions; 0 is perfect
        "ece": ece(ds),
        "escalated": round(sum(d["escalated"] for d in ds) / nd, 4),
        "cost": round(cost, 6), "calls": sum(e["calls"] for e in ok),
        "cost_per_pass": round(cost / passes, 6) if passes else None,
    }


def ece(ds, bins=10):
    """Expected calibration error: stated confidence vs agreement with the expert."""
    pts = [(d["confidence"], d["agree"]) for d in ds if d["confidence"] is not None]
    if not pts:
        return None
    total = 0.0
    for b in range(bins):
        bucket = [(c, a) for c, a in pts if b / bins <= c < (b + 1) / bins or (b == bins - 1 and c == 1.0)]
        if bucket:
            total += abs(sum(c for c, _ in bucket) - sum(a for _, a in bucket))
    return round(total / len(pts), 4)
