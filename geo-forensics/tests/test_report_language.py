"""Language-enforcement tests for the case report (methodology v1.0).

These lock in the reporting rules agreed in the 2026-08-12 reliability round:
composite scores are never shown as "XX% match", ratings come from the v1.0
Hebrew vocabulary, "monotonic" is only used when the data support it, the
evidence axes are "complementary" (not "independent"), product-level AFFF
attribution stays at family/technology level, and every report carries the
methodology version it was produced under.
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPORT = os.path.join(os.path.dirname(__file__), "..", "regions", "kishon",
                      "case_report_kishon.html")


@pytest.fixture(scope="module")
def prose():
    """Report text with <bdi> wrappers stripped (they split Hebrew tokens)."""
    if not os.path.isfile(REPORT):
        pytest.skip("case report not generated yet")
    with open(REPORT, encoding="utf-8") as f:
        html = f.read()
    # embedded figure JSON would produce false hits — keep only the body prose
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    return re.sub(r"</?bdi>", "", html)


def test_no_composite_percent_match(prose):
    """A composite support score is never presented as a percentage."""
    assert "% התאמה" not in prose
    assert "התאמה כימית משוקללת" not in prose
    assert "משוקלל-עוצמה" not in prose
    assert not re.search(r"התאמה[^<]{0,20}\d{1,3}\s*אחוז", prose)


def test_similarity_shown_on_zero_to_one_scale(prose):
    assert re.search(r"דמיון\s*0\.\d\d", prose), "0-1 similarity not found"


def test_support_components_present(prose):
    for label in ("דמיון בהרכב", "התאמה לפרופיל בליה", "איכות האות",
                  "רמת התמיכה הכימית"):
        assert label in prose, f"missing support component: {label}"


def test_ratings_use_v1_vocabulary(prose):
    assert "מועמד ליבה" not in prose
    assert "רקע מקומי" not in prose
    assert "אין תמיכה בנתונים הנוכחיים" not in prose


def test_axes_are_complementary_not_independent(prose):
    assert "בלתי-תלוי" not in prose
    assert "משלימים" in prose


def test_monotonic_only_with_supporting_data(prose):
    """The word may only appear if some series really is monotonic-strong."""
    if "מונוטוני" not in prose:
        return
    from generate_review_report import _prepare
    data = _prepare("kishon")
    strong = [c for c in data["candidates"]
              if (c["attenuation"].get("r_precursor") or 0) <= -0.8]
    assert strong, "'monotonic' used without a strong (<=-0.8) correlation"


def test_methodology_version_stamped(prose):
    from generate_case_report import METHODOLOGY_VERSION
    assert f"גרסה {METHODOLOGY_VERSION}" in prose
    assert "PFAS_INVESTIGATION_METHODOLOGY" in prose


def test_product_attribution_stays_at_family_level(prose):
    """AFFF is attributed to a family/technology, never identified as a
    commercial product."""
    if "Light Water" in prose:
        assert re.search(r"דוגמת[^<]{0,40}Light Water", prose), \
            "commercial product named without the 'for example' framing"
    assert "זוהה 3M" not in prose
