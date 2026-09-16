"""Regression tests for scoring_profile.json's poor_fit_terms and fit_terms.

The live delivery-time fit score (notify._fit, gating min_fit in
telegram_notify.py) reads this file directly, so these tests exercise the
real committed profile rather than a fixture, catching regex regressions in
the actual config.
"""
import notify


def test_medical_benefits_boilerplate_no_longer_penalized():
    # Real bug found 2026-09-16 auditing live Google Jobs output: three
    # genuine "Creative Director" listings scored exactly 0 because the old
    # poor_fit_terms pattern bare-matched "medical" anywhere in the text —
    # including standard US benefits-package language ("Medical, Dental and
    # Vision Insurance"), nothing to do with the healthcare industry.
    # domain_blocked() in telegram_notify.py already excludes genuine
    # healthcare-domain roles with proper compound-phrase matching; this
    # bare-word duplicate in the scoring profile was redundant and harmful.
    score = notify._fit(
        "Creative Director, Paid Social",
        "Great company. Medical, Dental and Vision Insurance start day one. "
        "Life and Disability Insurance, 401k match.",
    )
    assert score > 40, score


def test_junior_mentoring_mention_no_longer_penalized():
    # Real bug found the same day: "coach junior members toward the same"
    # (a senior role mentoring junior staff) bare-matched "junior" and took
    # a -28 penalty meant for actual junior-level postings.
    score = notify._fit(
        "Creative Director",
        "Establish best-practice design skills and coach junior members "
        "toward the same, fostering a culture of excellence.",
    )
    assert score > 40, score


def test_genuine_junior_and_graduate_postings_still_penalized():
    assert notify._fit("Junior Creative Director", "") < 40
    assert notify._fit(
        "Creative Graduate Scheme", "Join our graduate scheme this September."
    ) < 40
    assert notify._fit("Creative Director", "This is an entry-level role.") < 40


def test_genuine_us_residency_requirement_still_penalized():
    # Distinct from the medical/junior false positives above — this is a
    # real geography restriction and should still score low.
    score = notify._fit(
        "Creative Director",
        "100% remote within the United States. Must be a US resident.",
    )
    assert score < 40, score


def test_new_role_terms_score_as_signature_matches():
    # The six roles added 2026-09-16 (synced from Can's PROJECT-EXIT repo)
    # must be recognized by the scoring profile too, not just the hard
    # off_mission_role gate — otherwise they'd pass the gate but get capped
    # by generic_cap for not being a "signature" match.
    for title in (
        "Integrated Creative Lead",
        "Brand Strategist",
        "Senior Brand Creative",
        "Campaign Strategist",
        "Creative Innovation Director",
        "Creative Technologist",
    ):
        assert notify._fit(title, "Remote role.") >= 40, title


def test_creative_strategist_word_form_scores_well():
    # Same word-form gap fixed in discovery_lanes.ROLE_TERMS earlier the
    # same day — the scoring profile had its own separate copy of this bug.
    assert notify._fit("Senior Creative Strategist", "") >= 40
