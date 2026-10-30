"""shop: browse a seeded store and buy a product that meets every requirement.

Tests search with memory: category pages show only names and prices, so the
model has to open products to read their specs, remember which ones fit, and
come back to buy one. The cart holds one item; checkout ends the episode.
"""
import random

from bench.task import Task

# category: (attribute pools, product name parts)
CATALOG = {
    "Hiking Boots": ({"waterproof": [True, False], "level": ["beginner", "expert"], "weight": ["light", "heavy"]},
                     ["Trail", "Summit", "Ridge", "Canyon", "Alpine", "Scree"], "boots"),
    "Running Shoes": ({"surface": ["road", "trail"], "cushioning": ["high", "minimal"], "wide_fit": [True, False]},
                      ["Pace", "Stride", "Tempo", "Glide", "Sprint", "Drift"], "runners"),
    "Backpacks": ({"capacity_l": [20, 35, 50], "rain_cover": [True, False], "laptop_sleeve": [True, False]},
                  ["Nomad", "Atlas", "Ranger", "Voyager", "Pilot", "Rover"], "pack"),
    "Tents": ({"people": [1, 2, 4], "season": ["3-season", "4-season"], "freestanding": [True, False]},
              ["Shelter", "Haven", "Dome", "Arc", "Nest", "Bivy"], "tent"),
    "Jackets": ({"waterproof": [True, False], "insulated": [True, False], "packable": [True, False]},
                ["Storm", "Breeze", "Shell", "Puffer", "Gale", "Mist"], "jacket"),
}


def fmt(attrs):
    return ", ".join(f"{k.replace('_', ' ')}: {'yes' if v is True else 'no' if v is False else v}" for k, v in attrs.items())


class Shop(Task):
    name = "shop"

    def reset(self, seed):
        rng = random.Random(seed)
        self.products = {}          # pid -> {name, category, price, attrs}
        for cat, (pools, parts, noun) in CATALOG.items():
            for j, part in enumerate(rng.sample(parts, 5)):
                self.products[f"{cat}/{j}"] = {"name": f"{part} {noun}", "category": cat,
                                               "price": rng.randrange(40, 300, 5),
                                               "attrs": {k: rng.choice(v) for k, v in pools.items()}}
        self.target = rng.choice(sorted(CATALOG))
        pools = CATALOG[self.target][0]
        self.req = dict(rng.sample(sorted((k, rng.choice(v)) for k, v in pools.items()), 2))
        in_cat = [p for p in self.products if self.products[p]["category"] == self.target]
        good = rng.choice(in_cat)        # guarantee at least one match, and keep it affordable
        self.products[good]["attrs"].update(self.req)
        self.budget = max(self.products[good]["price"] + rng.choice([10, 30, 60]), 80)
        self.matches = {p for p in in_cat if self.ok(p)}
        self.page, self.history, self.cart, self.checked_out = "home", [], None, False
        self.instruction = (f"Buy {CATALOG[self.target][2]} with {fmt(self.req)}, costing at most ${self.budget}. "
                            "Open products to read their specs. Put exactly one matching item in the cart, then check out.")
        self.max_steps = 25

    def ok(self, pid):
        p = self.products[pid]
        return p["category"] == self.target and p["price"] <= self.budget and all(p["attrs"][k] == v for k, v in self.req.items())

    def observe(self):
        cart = self.products[self.cart]["name"] if self.cart else "empty"
        if self.page == "home":
            return {"page": "store home", "categories": sorted(CATALOG), "cart": cart}
        if self.page in CATALOG:
            return {"page": self.page, "products": {self.products[p]["name"]: f"${self.products[p]['price']}"
                                                    for p in self.in_category(self.page)}, "cart": cart}
        p = self.products[self.page]
        return {"page": p["name"], "category": p["category"], "price": f"${p['price']}", "specs": fmt(p["attrs"]),
                "cart": cart}

    def in_category(self, cat):
        return [p for p in self.products if self.products[p]["category"] == cat]

    def place(self):
        return self.page

    def memo(self):
        if self.page in self.products:
            p = self.products[self.page]
            return f"{p['name']}, ${p['price']}, {fmt(p['attrs'])}"
        return None

    def actions(self):
        acts = {}
        if self.page == "home":
            acts.update({f"open:{c}": f"open the {c} category" for c in CATALOG})
        elif self.page in CATALOG:
            acts.update({f"open:{p}": f"open {self.products[p]['name']} (${self.products[p]['price']})"
                         for p in self.in_category(self.page)})
        else:
            acts["add"] = f"put {self.products[self.page]['name']} in the cart (replaces the cart)"
        if self.page != "home":
            acts["back"] = "go back to the previous page"
        if self.cart:
            acts["checkout"] = f"check out with {self.products[self.cart]['name']}"
        return acts

    def step(self, action):
        if action.startswith("open:"):
            self.history.append(self.page)
            self.page = action[5:]
            return f"opened {self.observe()['page']}"
        if action == "back":
            self.page = self.history.pop() if self.history else "home"
            return "went back"
        if action == "add":
            self.cart = self.page
            return f"cart: {self.products[self.page]['name']}"
        self.checked_out = True
        return "order placed"

    @property
    def done(self):
        return self.checked_out

    def reward(self):
        return 1.0 if self.checked_out and self.ok(self.cart) else 0.0

    def oracle(self):
        if self.cart in self.matches:
            return {"checkout"}
        if self.page in self.matches:
            return {"add"}
        if self.page == self.target:
            return {f"open:{p}" for p in self.matches}
        if self.page == "home":
            return {f"open:{self.target}"}
        return {"back"}         # the store is two levels deep, so back always moves up toward home
