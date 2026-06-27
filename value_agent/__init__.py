"""
UK Football Value-Bet Agent.

Entirely standalone — no dependency on the pitchside web app.

Quick start
-----------
    pip install -r value_agent/requirements.txt
    export ODDS_API_KEY=<your_key>
    export ANTHROPIC_API_KEY=<your_key>

    # First run: seed your bankroll
    python -m value_agent.run deposit 200

    # Weekly: run the scan
    python -m value_agent.run scan

See value_agent/run.py --help for all sub-commands.
"""
