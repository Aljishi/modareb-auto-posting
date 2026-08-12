RASED Patch v10.1

READY-TO-REPLACE / CREATE FILES

CREATE:
- scripts/sector_master.py

REPLACE:
- scripts/market_intelligence.py
- scripts/run_signal_pipeline.py
- scripts/sector_rotation.py
- .github/workflows/post.yml

NO CHANGE REQUIRED:
- scripts/generate_market_brief.py (main already has Investor Daily Brief v2.0)
- scripts/weekly_report.py (main already has Investor Weekly Review v2.0)
- scripts/signal_quality_gate.py (v10 already exists)

Main fixes:
1) prevents MIN_SIGNAL_SCORE='81.0' integer parsing crash
2) actually runs signal_quality_gate.py from the signal pipeline
3) corrects/normalizes sector mapping, including 4011 Lazurde
4) updates sector rotation before the daily investor brief
5) removes redundant standalone regime detection in auto-post
