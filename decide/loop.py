"""The harness loop: turn every agent step into one typed `choice` question.

    observe -> {action: choice over legal actions} -> model -> execute argmax -> repeat

The model never writes text. It returns a distribution over the legal actions,
the harness executes the top one, and the env's checker grades the end state.
"""
import os, random, time

HISTORY = int(os.environ.get("DB_HISTORY", 8))
# Decision models judge the input in front of them; they do not reason over a log.
# So the harness remembers for them: an action already taken from this same
# situation (same legal-action set) is annotated with how often and what happened.
ANNOTATE = os.environ.get("DB_ANNOTATE", "1") == "1"
ASK = "Pick the single best next action toward the task goal."


def model_policy(model):
    def act(state, question, env, rng):
        answers, usage = model.decide(state, question)
        a = answers.get("action") or {}
        return a.get("value"), a.get("probabilities") or {}, a.get("confidence"), usage
    act.name = model.name
    return act


def oracle_policy(state, question, env, rng):
    good = sorted(env.oracle())
    probs = {k: (1 / len(good) if k in good else 0.0) for k in question["action"]["criteria"]}
    return rng.choice(good), probs, 1.0, None
oracle_policy.name = "oracle"


def random_policy(state, question, env, rng):
    acts = list(question["action"]["criteria"])
    probs = {k: 1 / len(acts) for k in acts}
    return rng.choice(acts), probs, 1 / len(acts), None
random_policy.name = "random"


def run_episode(env, policy, seed):
    """Play one seeded episode. Returns a trace dict; never raises on model errors."""
    rng = random.Random(seed)
    env.reset(seed)
    history, steps, tried = [], [], {}
    cost = tokens = 0
    t0 = time.time()
    error = None
    while not env.done and len(steps) < env.max_steps:
        acts = env.actions()
        good = sorted(env.oracle())
        where = tuple(sorted(acts))
        shown = {a: annotate(d, tried.get((where, a))) for a, d in acts.items()} if ANNOTATE else acts
        state = {"observation": env.observe(), "recent_actions": history[-HISTORY:]}
        question = {"action": {"type": "choice", "instructions": f"Task: {env.instruction}\n\n{ASK}", "criteria": shown}}
        try:
            choice, probs, conf, usage = policy(state, question, env, rng)
        except Exception as e:
            error = str(e)[:300]
            break
        if choice not in acts:
            error = f"illegal action {choice!r}"
            break
        if usage:
            cost += usage["cost"]
            tokens += usage["input_tokens"]
        feedback = env.step(choice)
        n, _ = tried.get((where, choice), (0, None))
        tried[(where, choice)] = (n + 1, feedback)
        history.append(f"{choice} -> {feedback}")
        steps.append({
            "n_actions": len(acts), "choice": choice, "confidence": conf, "good": good,
            "agree": choice in good, "p_good": round(sum(probs.get(g, 0.0) for g in good), 4),
            "probabilities": probs, "feedback": feedback, "ms": usage["ms"] if usage else 0,
        })
    reward = env.reward()
    return {
        "task": env.name, "policy": policy.name, "seed": seed, "reward": round(reward, 4),
        "passed": reward >= 1.0, "steps": len(steps), "hit_step_limit": not env.done and error is None,
        "cost": cost, "input_tokens": tokens, "seconds": round(time.time() - t0, 1),
        "error": error, "trace": steps,
    }


def annotate(desc, seen):
    if not seen:
        return desc
    n, feedback = seen
    return f"{desc} [already tried {n}x from here; result: {feedback}]"


def summarize(episodes):
    """Aggregate episodes (any mix of tasks) into the leaderboard metrics."""
    ok = [e for e in episodes if not e["error"]]
    steps = [s for e in ok for s in e["trace"]]
    n = len(ok) or 1
    passes = sum(e["passed"] for e in ok)
    out = {
        "episodes": len(ok), "errors": len(episodes) - len(ok),
        "reward": round(sum(e["reward"] for e in ok) / n, 4),
        "pass_rate": round(passes / n, 4),
        "step_agreement": round(sum(s["agree"] for s in steps) / (len(steps) or 1), 4),
        # Brier on the oracle set: (1 - P(any expert action))^2, 0 is perfect.
        "brier": round(sum((1 - s["p_good"]) ** 2 for s in steps) / (len(steps) or 1), 4),
        "ece": ece(steps),
        "cost": round(sum(e["cost"] for e in ok), 6),
        "calls": len(steps),
    }
    out["cost_per_pass"] = round(out["cost"] / passes, 6) if passes else None
    return out


def ece(steps, bins=10):
    """Expected calibration error of the model's stated confidence vs oracle agreement."""
    pts = [(s["confidence"], s["agree"]) for s in steps if s["confidence"] is not None]
    if not pts:
        return None
    total = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        bucket = [(c, a) for c, a in pts if lo <= c < hi or (b == bins - 1 and c == 1.0)]
        if bucket:
            total += len(bucket) * abs(sum(c for c, _ in bucket) / len(bucket) - sum(a for _, a in bucket) / len(bucket))
    return round(total / len(pts), 4)
