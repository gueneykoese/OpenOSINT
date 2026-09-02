"""football_agent — AI-assisted player-agency matching engine (pilot: UCL 2026/27).

The package is deliberately independent from the OSINT tooling that lives in
``openosint/``: it only shares the repository, the Python toolchain and the
FastAPI dependency.

Public entry points:

* :mod:`football_agent.loader`   — load the JSON dataset into typed models.
* :mod:`football_agent.matching` — deterministic, explainable scoring engine.
* :mod:`football_agent.api`      — FastAPI application (``uvicorn football_agent.api:app``).
* :mod:`football_agent.cli`      — ``python -m football_agent`` command line.
"""

__version__ = "0.1.0"
