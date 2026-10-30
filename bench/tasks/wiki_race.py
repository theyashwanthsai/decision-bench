"""wiki-race: follow links through a fixed concept graph from a start page to a target.

Tests planning by meaning: the model sees only the current page's links and has
to judge which one is semantically closer to the target.
"""
import random
from collections import deque

from bench.task import Task

# title: (one-line summary, [outgoing links])
PAGES = {
    "Sun": ("The star at the centre of the Solar System.", ["Solar System", "Nuclear Fusion", "Light", "Photosynthesis", "Solar Power"]),
    "Solar System": ("The Sun and the bodies that orbit it.", ["Sun", "Earth", "Mars", "Jupiter", "Gravity"]),
    "Earth": ("The third planet from the Sun, home to all known life.", ["Solar System", "Moon", "Atmosphere", "Ocean", "Life"]),
    "Moon": ("Earth's only natural satellite.", ["Earth", "Tides", "Apollo Program", "Gravity"]),
    "Mars": ("The red planet, fourth from the Sun.", ["Solar System", "Planetary Rover", "Water"]),
    "Jupiter": ("The largest planet in the Solar System.", ["Solar System", "Gravity", "Galileo Galilei"]),
    "Gravity": ("The force by which masses attract one another.", ["Isaac Newton", "Albert Einstein", "Tides", "Solar System"]),
    "Tides": ("The rise and fall of sea levels caused by the Moon and Sun.", ["Moon", "Ocean", "Gravity"]),
    "Isaac Newton": ("English physicist who formulated the laws of motion.", ["Gravity", "Calculus", "Optics"]),
    "Calculus": ("Mathematics of continuous change.", ["Isaac Newton", "Physics"]),
    "Physics": ("The natural science of matter, energy and motion.", ["Calculus", "Albert Einstein", "Light", "Electricity"]),
    "Albert Einstein": ("Physicist who developed the theory of relativity.", ["Relativity", "Gravity", "Nuclear Energy", "Physics"]),
    "Relativity": ("Einstein's theories of space, time and gravity.", ["Albert Einstein", "GPS", "Light"]),
    "GPS": ("Satellite-based navigation system.", ["Relativity", "Satellite", "Smartphone"]),
    "Satellite": ("An object placed in orbit around a planet.", ["GPS", "Rocket", "Weather Forecasting", "Internet"]),
    "Rocket": ("A vehicle propelled by expelling exhaust.", ["Satellite", "Apollo Program", "Combustion"]),
    "Apollo Program": ("NASA programme that landed humans on the Moon.", ["Moon", "Rocket", "Cold War", "Computer"]),
    "Cold War": ("Geopolitical rivalry between the US and the USSR.", ["Apollo Program", "Internet", "Nuclear Energy"]),
    "Internet": ("Global network of interconnected computers.", ["Computer", "Cold War", "Smartphone", "World Wide Web"]),
    "World Wide Web": ("System of linked hypertext pages on the Internet.", ["Internet", "Search Engine", "Wikipedia"]),
    "Search Engine": ("Software that finds information on the Web.", ["World Wide Web", "Artificial Intelligence"]),
    "Wikipedia": ("A free online encyclopedia.", ["World Wide Web", "Encyclopedia"]),
    "Encyclopedia": ("A reference work summarising knowledge.", ["Wikipedia", "Printing Press", "Library"]),
    "Library": ("A collection of books and media for borrowing.", ["Encyclopedia", "Printing Press"]),
    "Printing Press": ("Machine for mass-producing printed text.", ["Encyclopedia", "Paper", "Renaissance"]),
    "Paper": ("Thin material made from wood pulp.", ["Printing Press", "Tree"]),
    "Tree": ("A tall perennial woody plant.", ["Paper", "Forest", "Photosynthesis"]),
    "Forest": ("A large area dominated by trees.", ["Tree", "Rainforest", "Wildfire"]),
    "Rainforest": ("Dense forest with very high rainfall.", ["Forest", "Amazon River", "Biodiversity"]),
    "Biodiversity": ("The variety of life in an area.", ["Rainforest", "Life", "Climate Change"]),
    "Amazon River": ("The largest river in South America.", ["Rainforest", "River"]),
    "River": ("A natural flowing watercourse.", ["Amazon River", "Water", "Hydroelectric Power", "Ocean"]),
    "Ocean": ("The body of salt water covering most of Earth.", ["Earth", "Tides", "River", "Water"]),
    "Water": ("H2O, essential for all known life.", ["River", "Ocean", "Hydrogen", "Life"]),
    "Life": ("Matter that grows, reproduces and responds.", ["Earth", "Water", "Carbon", "Biodiversity"]),
    "Hydrogen": ("The lightest and most abundant chemical element.", ["Water", "Nuclear Fusion", "Periodic Table"]),
    "Nuclear Fusion": ("Light nuclei combining to release energy.", ["Sun", "Hydrogen", "Nuclear Energy"]),
    "Nuclear Energy": ("Energy released from atomic nuclei.", ["Nuclear Fusion", "Electricity", "Uranium"]),
    "Uranium": ("A heavy radioactive element used as nuclear fuel.", ["Nuclear Energy", "Periodic Table"]),
    "Periodic Table": ("Tabular arrangement of the chemical elements.", ["Hydrogen", "Carbon", "Oxygen", "Silicon", "Uranium"]),
    "Carbon": ("The element at the basis of organic chemistry.", ["Periodic Table", "Life", "Coal", "Climate Change"]),
    "Coal": ("A black rock burned as fuel.", ["Carbon", "Steam Engine", "Fossil Fuel"]),
    "Steam Engine": ("Engine that does work using steam.", ["Coal", "Industrial Revolution", "Railway"]),
    "Industrial Revolution": ("Shift to machine manufacturing, 1760-1840.", ["Steam Engine", "Railway", "Climate Change"]),
    "Railway": ("Track on which trains run.", ["Steam Engine", "Industrial Revolution"]),
    "Fossil Fuel": ("Fuel formed from ancient organisms.", ["Coal", "Combustion", "Climate Change"]),
    "Combustion": ("Burning: rapid reaction with oxygen.", ["Oxygen", "Rocket", "Wildfire", "Fossil Fuel"]),
    "Wildfire": ("An uncontrolled fire in vegetation.", ["Forest", "Combustion"]),
    "Oxygen": ("The element most living things need to breathe.", ["Atmosphere", "Photosynthesis", "Combustion", "Periodic Table"]),
    "Atmosphere": ("The layer of gases around Earth.", ["Earth", "Oxygen", "Climate Change", "Weather Forecasting"]),
    "Weather Forecasting": ("Predicting the state of the atmosphere.", ["Atmosphere", "Satellite", "Computer"]),
    "Climate Change": ("Long-term shifts in global temperatures.", ["Carbon", "Atmosphere", "Fossil Fuel", "Solar Power"]),
    "Photosynthesis": ("How plants turn light into chemical energy.", ["Sun", "Tree", "Oxygen", "Light"]),
    "Light": ("Electromagnetic radiation visible to the eye.", ["Sun", "Optics", "Relativity", "Physics"]),
    "Optics": ("The study of light and its behaviour.", ["Light", "Isaac Newton", "Telescope", "Glass"]),
    "Glass": ("A hard transparent material made from sand.", ["Optics", "Silicon"]),
    "Telescope": ("An instrument for seeing distant objects.", ["Optics", "Galileo Galilei", "Jupiter"]),
    "Galileo Galilei": ("Astronomer who pioneered the telescope.", ["Telescope", "Jupiter", "Renaissance"]),
    "Renaissance": ("European cultural rebirth, 14th-17th century.", ["Galileo Galilei", "Printing Press", "Leonardo da Vinci"]),
    "Leonardo da Vinci": ("Renaissance painter and inventor.", ["Renaissance", "Mona Lisa", "Anatomy"]),
    "Mona Lisa": ("Portrait painted by Leonardo da Vinci.", ["Leonardo da Vinci", "Louvre"]),
    "Louvre": ("Art museum in Paris.", ["Mona Lisa", "Paris"]),
    "Paris": ("The capital of France.", ["Louvre", "Eiffel Tower"]),
    "Eiffel Tower": ("Wrought-iron tower in Paris.", ["Paris", "Steel"]),
    "Steel": ("An alloy of iron and carbon.", ["Eiffel Tower", "Carbon", "Railway"]),
    "Anatomy": ("The study of the structure of organisms.", ["Leonardo da Vinci", "Brain"]),
    "Brain": ("The organ at the centre of the nervous system.", ["Anatomy", "Neural Network"]),
    "Neural Network": ("Computing system loosely inspired by the brain.", ["Brain", "Artificial Intelligence"]),
    "Artificial Intelligence": ("Machines performing tasks that need intelligence.", ["Neural Network", "Alan Turing", "Computer"]),
    "Alan Turing": ("Founder of theoretical computer science.", ["Artificial Intelligence", "Computer", "Cryptography"]),
    "Cryptography": ("Techniques for secure communication.", ["Alan Turing", "Internet"]),
    "Computer": ("A machine that runs programs.", ["Alan Turing", "Semiconductor", "Internet", "Electricity"]),
    "Semiconductor": ("Material whose conductivity can be controlled.", ["Silicon", "Computer", "Solar Power"]),
    "Silicon": ("The element chips are built on.", ["Semiconductor", "Glass", "Periodic Table"]),
    "Smartphone": ("A handheld mobile computer.", ["Computer", "Internet", "GPS"]),
    "Electricity": ("Phenomena from the flow of charge.", ["Physics", "Computer", "Solar Power", "Hydroelectric Power", "Lightning"]),
    "Lightning": ("An electrical discharge during a storm.", ["Electricity", "Atmosphere"]),
    "Solar Power": ("Electricity generated from sunlight.", ["Sun", "Semiconductor", "Electricity", "Climate Change"]),
    "Hydroelectric Power": ("Electricity from flowing water.", ["River", "Electricity"]),
    "Planetary Rover": ("A vehicle that explores another planet's surface.", ["Mars", "Computer", "Rocket"]),
}


def distances_to(target):
    """BFS on reversed edges: hops from every page to `target`."""
    rev = {p: [] for p in PAGES}
    for p, (_, links) in PAGES.items():
        for q in links:
            rev[q].append(p)
    dist, queue = {target: 0}, deque([target])
    while queue:
        p = queue.popleft()
        for q in rev[p]:
            if q not in dist:
                dist[q] = dist[p] + 1
                queue.append(q)
    return dist


class WikiRace(Task):
    name = "wiki-race"

    def reset(self, seed):
        rng = random.Random(seed)
        while True:
            self.target = rng.choice(sorted(PAGES))
            self.dist = distances_to(self.target)
            far = sorted(p for p, d in self.dist.items() if 4 <= d <= 6)
            if far:
                break
        self.page = rng.choice(far)
        self.optimal = self.dist[self.page]
        self.budget = self.max_steps = self.optimal * 2
        self.moves = 0
        self.instruction = (f"Reach the page '{self.target}' by following links, starting from "
                            f"'{self.page}'. You may only follow links on the current page.")

    def observe(self):
        summary, _ = PAGES[self.page]
        return {"current_page": self.page, "summary": summary, "target_page": self.target,
                "moves_left": self.budget - self.moves}

    def place(self):
        return self.page

    def memo(self):
        return f"{PAGES[self.page][0]} Links to: {', '.join(PAGES[self.page][1])}"

    def actions(self):
        return {f"go:{q}": f"Follow the link to '{q}' ({PAGES[q][0]})" for q in PAGES[self.page][1]}

    def step(self, action):
        self.page = action.removeprefix("go:")
        self.moves += 1
        return "reached the target" if self.page == self.target else f"now on '{self.page}'"

    @property
    def done(self):
        return self.page == self.target or self.moves >= self.budget

    def reward(self):
        return 1.0 if self.page == self.target else 0.0

    def oracle(self):
        best = self.dist.get(self.page, 99) - 1
        return {f"go:{q}" for q in PAGES[self.page][1] if self.dist.get(q) == best}
