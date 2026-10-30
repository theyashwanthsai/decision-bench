"""python -m bench --models typesafe/jev-1.14,oracle,random --tasks all --seeds 10"""
import argparse, json, re, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bench import TASKS
from decide import models
from decide.loop import model_policy, oracle_policy, random_policy, run_episode, summarize


def policy_for(spec):
    if spec == "oracle":
        return oracle_policy
    if spec == "random":
        return random_policy
    return model_policy(models.load(spec))


def main():
    ap = argparse.ArgumentParser(prog="bench")
    ap.add_argument("--models", required=True, help="comma-separated specs; 'oracle' and 'random' are baselines")
    ap.add_argument("--tasks", default="all")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default=None, help="results dir (default results/<timestamp>)")
    a = ap.parse_args()

    tasks = list(TASKS) if a.tasks == "all" else a.tasks.split(",")
    specs = a.models.split(",")
    policies = {s: policy_for(s) for s in specs}
    out = Path(a.out or f"results/{time.strftime('%Y%m%d-%H%M%S')}")
    jobs = [(s, t, seed) for s in specs for t in tasks for seed in range(a.seeds)]

    def job(j):
        s, t, seed = j
        return s, run_episode(TASKS[t](), policies[s], seed)

    episodes = {s: [] for s in specs}
    with ThreadPoolExecutor(a.workers) as pool:
        for i, (s, ep) in enumerate(pool.map(job, jobs), 1):
            episodes[s].append(ep)
            flag = "ERR " + ep["error"][:60] if ep["error"] else ("pass" if ep["passed"] else "fail")
            print(f"[{i}/{len(jobs)}] {s:40} {ep['task']:16} seed={ep['seed']:<3} {flag}", flush=True)

    board = []
    for s in specs:
        d = out / slug(s)
        d.mkdir(parents=True, exist_ok=True)
        for t in tasks:
            with open(d / f"{t}.jsonl", "w") as f:
                for ep in episodes[s]:
                    if ep["task"] == t:
                        f.write(json.dumps(ep) + "\n")
        row = {"model": s, **summarize(episodes[s]),
               "per_task": {t: summarize([e for e in episodes[s] if e["task"] == t])["reward"] for t in tasks}}
        (d / "summary.json").write_text(json.dumps(row, indent=1))
        board.append(row)
    board.sort(key=lambda r: -r["reward"])
    (out / "leaderboard.json").write_text(json.dumps(board, indent=1))
    (out / "LEADERBOARD.md").write_text(render(board, tasks))
    print("\n" + render(board, tasks) + f"\nresults in {out}/")


def slug(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)


def render(board, tasks):
    head = ["model", "reward", "pass", "step agree", "brier", "ece", "cost $", *tasks]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in board:
        cells = [r["model"], f"{r['reward']:.2f}", f"{r['pass_rate']:.2f}", f"{r['step_agreement']:.2f}",
                 f"{r['brier']:.3f}", "-" if r["ece"] is None else f"{r['ece']:.3f}", f"{r['cost']:.4f}",
                 *(f"{r['per_task'][t]:.2f}" for t in tasks)]
        if r["errors"]:
            cells[0] += f" ({r['errors']} err)"
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
