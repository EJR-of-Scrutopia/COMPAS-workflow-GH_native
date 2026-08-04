from __future__ import annotations

import pytest

from ananke_fea.results import deflection_summary


def test_deflection_reports_a_span_ratio():
    summary = deflection_summary({"peak_magnitude": 0.01}, span=4.0)
    assert summary["span_over_deflection"] == pytest.approx(400.0)


def test_a_zero_deflection_does_not_divide_by_zero():
    summary = deflection_summary({"peak_magnitude": 0.0}, span=4.0)
    assert summary["span_over_deflection"] is None
