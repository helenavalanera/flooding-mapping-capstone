"""Extraction of flood-related events from free text (bulletins, news, reports), with human review and a measured precision.

The model only *reads*: it turns a text into candidate events. A candidate is never a label until a person accepts it, it carries the
quote it came from, and the whole pipeline is measured against a hand-annotated sample (``precisao``). See docs/extracao.md.
"""
