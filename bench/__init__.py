from bench.tasks.dungeon import Dungeon
from bench.tasks.inbox_triage import InboxTriage
from bench.tasks.incident_response import IncidentResponse
from bench.tasks.merge_gate import MergeGate
from bench.tasks.moderation import Moderation
from bench.tasks.procedures import Procedures
from bench.tasks.repo_nav import RepoNav
from bench.tasks.shop import Shop
from bench.tasks.support_desk import SupportDesk
from bench.tasks.wiki_race import WikiRace

TASKS = {t.name: t for t in [WikiRace, Dungeon, RepoNav, IncidentResponse, SupportDesk, Shop, Procedures,
                             InboxTriage, MergeGate, Moderation]}
