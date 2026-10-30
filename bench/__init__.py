from bench.tasks.dungeon import Dungeon
from bench.tasks.inbox_triage import InboxTriage
from bench.tasks.merge_gate import MergeGate
from bench.tasks.moderation import Moderation
from bench.tasks.wiki_race import WikiRace

TASKS = {t.name: t for t in [WikiRace, Dungeon, InboxTriage, MergeGate, Moderation]}
