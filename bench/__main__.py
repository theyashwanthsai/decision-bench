"""python -m bench --models typesafe/jev-1.14 --harness default,bare --baselines --tasks all --seeds 10"""
import argparse, json, re, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from steer import Agent

from bench import TASKS
from bench.run import HARNESSES, episode, summarize


def main():
    ap = argparse.ArgumentParser(prog="bench")
    ap.add_argument("--models", default="", help="comma-separated steer model specs")
    ap.add_argument("--harness", default="default", help=f"comma-separated: {', '.join(HARNESSES)}")
    ap.add_argument("--baselines", action="store_true", help="also run oracle and random")
    ap.add_argument("--tasks", default="all")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default=None, help="results dir (default results/<timestamp>)")
    a = ap.parse_args()

    tasks = list(TASKS) if a.tasks == "all" else a.tasks.split(",")
    players = [Agent(m, **HARNESSES[h]) for m in filter(None, a.models.split(",")) for h in a.harness.split(",")]
    players += ["oracle", "random"] if a.baselines else []
    out = Path(a.out or f"results/{time.strftime('%Y%m%d-%H%M%S')}")
    jobs = [(p, t, seed) for p in players for t in tasks for seed in range(a.seeds)]

    episodes = {}
    with ThreadPoolExecutor(a.workers) as pool:
        for i, ep in enumerate(pool.map(lambda j: episode(TASKS[j[1]], j[2], j[0]), jobs), 1):
            episodes.setdefault(ep["player"], []).append(ep)
            flag = "ERR " + ep["error"][:60] if ep["error"] else ("pass" if ep["passed"] else "fail")
            print(f"[{i}/{len(jobs)}] {ep['player']:44} {ep['task']:12} seed={ep['seed']:<3} {flag}", flush=True)

    board = []
    for player, eps in episodes.items():
        d = out / slug(player)
        d.mkdir(parents=True, exist_ok=True)
        for t in tasks:
            with open(d / f"{t}.jsonl", "w") as f:
                f.writelines(json.dumps(e) + "\n" for e in eps if e["task"] == t)
        row = {"player": player, **summarize(eps),
               "per_task": {t: summarize([e for e in eps if e["task"] == t])["reward"] for t in tasks}}
        (d / "summary.json").write_text(json.dumps(row, indent=1))
        board.append(row)
    board.sort(key=lambda r: -r["reward"])
    (out / "leaderboard.json").write_text(json.dumps(board, indent=1))
    (out / "LEADERBOARD.md").write_text(render(board, tasks))
    print("\n" + render(board, tasks) + f"\nresults in {out}/")


def slug(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")


def render(board, tasks):
    head = ["player", "reward", "pass", "step agree", "brier", "ece", "cost $", *tasks]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in board:
        cells = [r["player"], f"{r['reward']:.2f}", f"{r['pass_rate']:.2f}", f"{r['step_agreement']:.2f}",
                 f"{r['brier']:.3f}", "-" if r["ece"] is None else f"{r['ece']:.3f}", f"{r['cost']:.4f}",
                 *(f"{r['per_task'][t]:.2f}" for t in tasks)]
        if r["errors"]:
            cells[0] += f" ({r['errors']} err)"
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
