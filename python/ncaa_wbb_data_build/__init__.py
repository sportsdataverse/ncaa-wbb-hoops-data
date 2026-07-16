"""Python producer for the NCAA WBB release datasets.

Cloned from ``hoopR-dev/ncaa-mbb-hoops-data/python/ncaa_mbb_data_build`` as a
scaffold baseline, then retargeted for NCAA women's basketball. Reshapes the
sibling ``ncaa-wbb-hoops-raw`` per-game JSON into season-level parquet/csv +
manifest and publishes to the ``ncaa_wbb_*`` release tags.
"""

__all__ = ["config", "ingest", "io", "build", "publish", "reshapers"]
