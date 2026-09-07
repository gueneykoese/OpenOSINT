"""Live match intelligence for the head coach.

Pipeline: event feed → rolling MatchState (15-minute windows) → rule-based
insights (what is breaking, what is working, with evidence) → bench
recommendations (who on the bench fixes it, why).

The engine is feed-agnostic. ``simulator.py`` produces a deterministic, clearly
labelled *simulated* event stream from two club dossiers so the product can be
demonstrated; production connects a licensed live provider (Opta/Stats Perform,
StatsBomb, Second Spectrum tracking) through the same ``Event`` schema.
"""

from .analyzer import Insight, analyze  # noqa: F401
from .bench import recommend_substitutions  # noqa: F401
from .models import Event, MatchState  # noqa: F401
from .simulator import simulate_match  # noqa: F401
