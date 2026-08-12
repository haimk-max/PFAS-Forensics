"""Well classification (monitoring vs production, approved 2026-08-12):
name-prefix convention primary, explicit source_type fallback; production
wells get a pumping-blurred best-tier within the declared capture radius."""

from src.attribution import classify_well
from src.flow_model import UniformFlowAssumption


def test_monitoring_prefixes():
    assert classify_well('נד תש"ן אלרואי 4') == "monitoring"
    assert classify_well("נת סולתם 3") == "monitoring"
    assert classify_well("מח דוגמה 1") == "monitoring"


def test_production_prefixes_including_dotted():
    assert classify_well("פ יגור קבוץ א") == "production"
    assert classify_well("מק יקנעם 2") == "production"
    assert classify_well("מק. מנשה 16 א") == "production"   # trailing dot


def test_source_type_fallback_and_unknown():
    assert classify_well("רגבים", "קידוח ניטור") == "monitoring"
    assert classify_well("רגבים", "קידוח הפקה") == "production"
    assert classify_well("רגבים", "קידוח") == "unknown"
    assert classify_well("יגור בית", "") == "unknown"


def test_lateral_slack_improves_tier():
    """A production well 700 m off-axis at L=668 m is tier 4 at the
    wellhead but tier 1-2 within a 500 m capture radius."""
    flow = UniformFlowAssumption(direction_deg=270)
    src = (203933.0, 711637.0)
    stn = (203265.0, 712356.0)   # L~668 m, W~719 m
    w0, t0 = flow.plausibility(stn, src, k=0.2)
    wb, tb = flow.plausibility(stn, src, k=0.2, lateral_slack_m=500.0)
    assert t0 == "4"
    assert tb in ("1", "2")
    assert wb > w0


def test_zero_slack_unchanged():
    flow = UniformFlowAssumption(direction_deg=270)
    src = (203933.0, 711637.0)
    stn = (203265.0, 712356.0)
    assert flow.plausibility(stn, src, k=0.2) == \
        flow.plausibility(stn, src, k=0.2, lateral_slack_m=0.0)
