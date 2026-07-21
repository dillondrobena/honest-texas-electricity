"""Honest Texas Electricity — Milestone 1 (Oncor trust engine).

Pipeline:  ingest -> validate -> filter -> cost -> recommend -> emit JSON

The heart of the product is the *filter*: a small set of explicit, documented
rules that reproduce the volunteer curator's honest-plan judgment. See filter.py.
"""

__version__ = "0.1.0"
