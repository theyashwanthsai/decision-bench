"""dungeon: a seeded text adventure. Blocked passages need the right tool.

Tests multi-step planning with an inventory: the model has to connect "stairs
descending into pitch darkness" with the oil lamp it saw two rooms back, fetch
it, and come back. The oracle plans optimally over the full state space.
"""
import random
from collections import deque

from bench.task import Task

ROOMS = ["Great Hall", "Kitchen", "Armory", "Library", "Chapel", "Cellar", "Garden", "Well Room",
         "Guard Post", "Gallery", "Pantry", "Study", "Crypt", "Tower Stair", "Courtyard", "Stable",
         "Forge", "Larder", "Scriptorium", "Bell Tower", "Dungeon Cell", "Servants' Quarters"]
# (how the blocked exit looks, the tool that clears it, what clearing it looks like)
OBSTACLES = [
    ("a heavy oak door with a brass lock", "brass key", "the lock clicks open"),
    ("a doorway nailed shut with thick planks", "crowbar", "the planks splinter away"),
    ("stairs descending into pitch darkness", "oil lamp", "the lamp lights the way down"),
    ("a deep shaft with no ladder", "coil of rope", "you tie off the rope and climb down"),
    ("a passage choked with thorny brambles", "machete", "you hack a path through"),
    ("an iron gate guarded by a snarling hound", "meat bone", "the hound takes the bone and lies down"),
    ("a tunnel flooded with icy water", "rubber waders", "you wade through safely"),
]
DECOYS = ["silver spoon", "torn painting", "pewter mug", "feather quill", "wool blanket", "chess piece", "old boot"]
DIRS = {"north": "south", "south": "north", "east": "west", "west": "east"}
GOAL = "crown"


class Dungeon(Task):
    name = "dungeon"
    instruction = "Find the crown hidden in the vault and take it. Some passages need the right tool to get through."

    def reset(self, seed):
        rng = random.Random(seed)
        names = rng.sample(ROOMS, len(ROOMS))
        k = rng.choice([3, 4])
        self.obstacles = rng.sample(OBSTACLES, k)
        self.exits, self.blocks, self.items = {}, {}, {}
        spine = [names.pop() for _ in range(k)] + ["Vault"]
        for i in range(k):                      # spine[i] -> spine[i+1] is blocked by obstacle i
            d = self._link(spine[i], spine[i + 1], rng)
            self.blocks[(spine[i], d)] = self.blocks[(spine[i + 1], DIRS[d])] = i
        reachable = [spine[0]]                  # rooms reachable before clearing obstacle i
        for i, (_, tool, _) in enumerate(self.obstacles):
            reachable.append(spine[i]) if spine[i] not in reachable else None
            room = self._side_room(names, reachable, rng) or rng.choice(reachable)
            if rng.random() < 0.4:              # sometimes one room deeper
                room = self._side_room(names, [room], rng) or room
            self.items[tool] = room
            reachable.append(room)
        for decoy in rng.sample(DECOYS, 3):
            room = self._side_room(names, reachable, rng) if rng.random() < 0.5 else None
            self.items[decoy] = room or rng.choice([r for r in self.exits if r != "Vault"])
        self.items[GOAL] = "Vault"
        self.state = (spine[0], frozenset(), frozenset())   # room, inventory, cleared obstacle ids
        self.dist = self._distances()
        self.max_steps = self.dist[self._key(self.state)] * 2 + 4
        self.last = ""

    def _link(self, a, b, rng):
        free = [d for d in DIRS if d not in self.exits.setdefault(a, {}) and DIRS[d] not in self.exits.setdefault(b, {})]
        d = rng.choice(free)
        self.exits[a][d], self.exits[b][DIRS[d]] = b, a
        return d

    def _side_room(self, names, anchors, rng):
        """Attach a new dead-end room to one of `anchors` that still has a free side."""
        anchors = [a for a in anchors if len(self.exits.get(a, {})) < 4]
        if not anchors or not names:
            return None
        room = names.pop()
        self._link(rng.choice(anchors), room, rng)
        return room

    # ------------------------------------------------------------- mechanics
    def _transitions(self, state):
        room, inv, cleared = state
        out = {}
        for d, nxt in self.exits[room].items():
            b = self.blocks.get((room, d))
            out[f"go:{d}"] = ((nxt, inv, cleared), f"you walk {d} into the {nxt}") if b is None or b in cleared \
                else (state, f"blocked: {self.obstacles[b][0]}")
        for item, where in sorted(self.items.items()):
            if where == room and item not in inv:
                out[f"take:{item}"] = ((room, inv | {item}, cleared), f"you take the {item}")
        for item in sorted(inv):
            hit = [b for d, b in self.blocks.items() if d[0] == room and b not in cleared and self.obstacles[b][1] == item]
            out[f"use:{item}"] = ((room, inv, cleared | {hit[0]}), self.obstacles[hit[0]][2]) if hit \
                else (state, "nothing happens")
        return out

    def _key(self, state):
        """Planning ignores decoys: carrying a spoon never changes what is reachable."""
        room, inv, cleared = state
        return room, frozenset(i for i in inv if i not in DECOYS), cleared

    def _distances(self):
        """Forward-explore every reachable state, then BFS backwards from the goal states."""
        seen, queue, back = {self._key(self.state)}, deque([self.state]), {}
        while queue:
            s = queue.popleft()
            for t, _ in self._transitions(s).values():
                kt = self._key(t)
                back.setdefault(kt, set()).add(self._key(s))
                if kt not in seen:
                    seen.add(kt)
                    queue.append(t)
        goals = [k for k in seen if GOAL in k[1]]
        dist, queue = {g: 0 for g in goals}, deque(goals)
        while queue:
            k = queue.popleft()
            for p in back.get(k, ()):
                if p not in dist:
                    dist[p] = dist[k] + 1
                    queue.append(p)
        return dist

    # ------------------------------------------------------------- Env API
    def observe(self):
        room, inv, cleared = self.state
        exits = {}
        for d, nxt in self.exits[room].items():
            b = self.blocks.get((room, d))
            exits[d] = f"open way to the {nxt}" if b is None or b in cleared else self.obstacles[b][0]
        return {"room": room, "exits": exits,
                "items_here": sorted(i for i, r in self.items.items() if r == room and i not in inv),
                "inventory": sorted(inv), "last_result": self.last}

    def place(self):
        return self.state[0]

    def memo(self):
        o = self.observe()
        exits = "; ".join(f"{d}: {v}" for d, v in o["exits"].items())
        items = ", ".join(o["items_here"]) or "none"
        return f"exits {exits}. items here: {items}"

    def actions(self):
        verbs = {"go": "walk {}", "take": "pick up the {}", "use": "use the {} here"}
        return {a: verbs[a.split(":")[0]].format(a.split(":", 1)[1]) for a in self._transitions(self.state)}

    def step(self, action):
        self.state, self.last = self._transitions(self.state)[action]
        return self.last

    @property
    def done(self):
        return GOAL in self.state[1]

    def reward(self):
        return 1.0 if self.done else 0.0

    def oracle(self):
        here = self.dist[self._key(self.state)]
        return {a for a, (t, _) in self._transitions(self.state).items() if self.dist.get(self._key(t)) == here - 1}
