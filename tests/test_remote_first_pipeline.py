import copy

import discovery_lanes
import final_filter


ROLES = [
    "ai producer",
    "ai producing",
    "ai lead",
    "creative strategy",
    "creative lead",
    "creative director",
    "associate creative director",
    "ugc",
    "creative producer",
    "integrated creative",
    "brand strategist",
    "brand creative",
    "campaign strategist",
    "creative innovation",
    "creative technologist",
]


def _base_config():
    return {
        "locations": {
            "indeed": [{"location": "London, United Kingdom", "country": "GB"}],
            "google_jobs": [{"location": "London, United Kingdom", "country": "GB"}],
            "linkedin": [],
            "ziprecruiter": [],
        },
        "target_geography": {
            "locations": ["London", "Europe"],
            "exclude_us": True,
            "require_remote": True,
        },
        "location_filter": {"terms": ["london", "europe"]},
        "keywords": {"include": ROLES[:], "exclude": ["intern"]},
        "search_terms": {
            name: [] for name in (
                "linkedin", "indeed", "glassdoor", "google_jobs",
                "hiring_cafe", "ziprecruiter",
            )
        },
        "profile": {},
        "discovery_lanes": {"enabled": False},
    }


def test_focused_mode_keeps_exact_fifteen_role_queries():
    # Was eight roles through 2026-09-15; "Creative Producer" added same day
    # after live testing showed it wrongly rejected (a title Can's own CV
    # uses). Widened again 2026-09-16 to six more roles synced from Can's own
    # PROJECT-EXIT repo's target-role list — he explicitly asked to prioritize
    # speed-to-landed-role over narrow precision at this point in his search.
    cfg = discovery_lanes.expand_config(copy.deepcopy(_base_config()), [])
    expected = [f"{role} remote" for role in ROLES]
    assert cfg["target_geography"]["exclude_us"] is True
    assert cfg["target_geography"]["require_remote"] is True
    assert cfg["keywords"]["include"] == ROLES
    for source in ("linkedin", "indeed", "glassdoor", "google_jobs", "ziprecruiter"):
        assert [term.casefold() for term in cfg["search_terms"][source]] == expected
    assert "project manager remote" not in cfg["search_terms"]["linkedin"]
    assert "creative producer remote" in cfg["search_terms"]["linkedin"]


def test_delivery_gate_requires_remote_no_longer_requires_uk_europe_signal():
    # As of 2026-09-15, explicit UK/Europe geography proof is no longer
    # required — any genuinely remote role is eligible, US included. Only an
    # explicit exclusionary signal (onsite/hybrid, or an explicit US-only
    # restriction) rejects.
    assert final_filter.eligible_location({
        "location": "Remote - London, United Kingdom",
        "description": "AI producer role",
        "is_remote": True,
    })
    assert final_filter.eligible_location({
        "location": "Remote - Europe",
        "description": "UGC role",
        "is_remote": True,
    })
    assert final_filter.eligible_location({
        "location": "Remote - United States",
        "description": "AI producer role",
        "is_remote": True,
    })
    assert final_filter.eligible_location({
        "location": "Remote",
        "description": "Worldwide AI producer role",
        "is_remote": True,
    })
    assert not final_filter.eligible_location({
        "location": "Remote - US Only",
        "description": "AI producer role",
        "is_remote": True,
    })
    assert not final_filter.eligible_location({
        "location": "London, United Kingdom",
        "description": "On-site only",
        "is_remote": False,
    })
    # Bare "Hybrid"/"Onsite" in a structured location/work_arrangement field
    # rejects even without the word "only" (careerops_bridge.py bug, fixed
    # same day).
    assert not final_filter.eligible_location({
        "location": "London, United Kingdom (Hybrid)",
        "description": "Creative Director role",
        "is_remote": False,
    })


def test_domain_gate_examples():
    from telegram_notify import domain_blocked

    assert domain_blocked({
        "title": "Pharma Project Manager",
        "description": "Requires pharma supply chain experience.",
    })
    assert not domain_blocked({
        "title": "AI Producer",
        "description": "Remote AI concept production and creative ideation.",
    })
    # Regression: a CareerOps listing (title="Associate Creative Director,
    # Copy") at Avalere Health slipped through on 2026-09-14 because
    # domain_blocked() only scanned title+description text (often empty on
    # thin ATS listings) and never looked at the company name — even though
    # the company itself is a healthcare company.
    assert domain_blocked({
        "company": "avalerehealth",
        "title": "Associate Creative Director, Copy",
        "description": "",
    })
    assert domain_blocked({
        "company": "Avalere Health",
        "title": "Associate Creative Director, Copy",
        "description": "healthcare is not a barrier",
    })
    # Company-name check shouldn't false-positive on unrelated real names.
    assert not domain_blocked({
        "company": "Wealthsimple",
        "title": "Creative Director",
        "description": "",
    })
    assert not domain_blocked({
        "company": "Wieden+Kennedy",
        "title": "Creative Director",
        "description": "ad agency creative work",
    })
    # Regression: Humana's "Creative Director" (CareerOps/workday, empty
    # description) reached Telegram on 2026-09-15 — brand-name health
    # insurer with no generic health/pharma word in the name, so the
    # substring regex above never caught it. Curated blocklist added.
    assert domain_blocked({
        "company": "Humana",
        "title": "Creative Director",
        "description": "",
    })
    assert domain_blocked({
        "company": "Stryker",
        "title": "Brand Marketing Manager",
        "description": "",
    })
    # Blocklist is exact-match, not substring — shouldn't catch a
    # similar-looking but unrelated name.
    assert not domain_blocked({
        "company": "Human Made",
        "title": "Creative Director",
        "description": "",
    })


def test_on_camera_gig_gate_examples():
    from telegram_notify import on_camera_gig_blocked

    # Real casting-call "UGC" postings found live 2026-09-16 (mostly Upwork)
    # — on-camera-talent gigs, not the strategic/coordination UGC roles Can
    # wants.
    casting_call_titles = [
        "French-Speaking UGC Creators / Spokespersons Needed – 20-40 sec Videos",
        "Need someone to create 0:30-01:00min UGC video with himself/herself",
        "Paid test for 2 UGC creators over 50 (one man, one woman, US-based)",
        "TikTok / Reels UGC Creator for Language App — $50 + $450 Viral Bonus",
        "Malayalam-Speaking UGC Creators Wanted | $50 per Video",
        "Female UGC Creator / Spokesperson / Presenter / Actress (English)",
        "Remote UGC Content Creator (On-Camera)",
    ]
    for title in casting_call_titles:
        assert on_camera_gig_blocked({"title": title}), title

    # Real strategic/coordination UGC and creative roles must not be caught.
    legitimate_titles = [
        "UGC Coordinator",
        "Remote Performance UGC Pipeline Manager (Part-Time)",
        "US UGC Campaign Manager",
        "Hands-On Creative Lead — Video, Design, AI & Luxury Social Content",
        "Meta Ads AI Creative Director/Creative Execution",
        "UGC Creator (remote/part-time)",
    ]
    for title in legitimate_titles:
        assert not on_camera_gig_blocked({"title": title}), title


def test_gig_marketplace_gate_examples():
    from telegram_notify import gig_marketplace_blocked

    # Real junk found live 2026-09-17 auditing a week of Telegram deliveries:
    # Upwork freelance micro-gigs and recruiting/talent-pool platforms
    # posting under their own brand as if they were the employer. These
    # aren't real jobs Can can apply to — blocked regardless of how well the
    # title matches the approved role families.
    assert gig_marketplace_blocked({
        "company": "Upwork",
        "title": "Cavalier Dog Owner UGC Long Term!",
        "url": "https://www.upwork.com/freelance-jobs/apply/x",
    })
    assert gig_marketplace_blocked({
        "company": "Upwork",
        "title": "Set up a WhatsApp AI Lead-Qualification System (respond.io + Zapier)",
        "url": "https://www.upwork.com/freelance-jobs/apply/y",
    })
    assert gig_marketplace_blocked({
        "company": "Jobgether",
        "title": "Creative Lead – DTC & Performance Creative",
        "url": "https://www.linkedin.com/jobs/view/123",
    })
    assert gig_marketplace_blocked({
        "company": "HireLATAM",
        "title": "Remote Performance UGC Pipeline Manager (Part-Time)",
        "url": "https://recruiterflow.com/jobs/abc",
    })
    assert gig_marketplace_blocked({
        "company": "Jobs for Lebanon",
        "title": "Remote UGC Content Creator (On-Camera) Job at Jobs for Lebanon in New York",
        "url": "https://www.mediabistro.com/jobs/xyz",
    })
    # Real employers must not be caught, including on LinkedIn/Upwork-adjacent
    # domains that aren't actually the gig-marketplace domains themselves.
    assert not gig_marketplace_blocked({
        "company": "Stripe",
        "title": "Creative Director, Event Design",
        "url": "https://www.linkedin.com/jobs/view/456",
    })
    assert not gig_marketplace_blocked({
        "company": "Everyday Dose Inc.",
        "title": "Senior Creative Producer",
        "url": "https://boards.greenhouse.io/everydaydose/jobs/789",
    })


def test_off_mission_role_gate_examples():
    from telegram_notify import off_mission_role

    # Real off-mission titles found live 2026-09-16 in historical delivery
    # records — none of the eight (now nine) approved role families, but
    # slipped through because LinkedIn/Indeed/Glassdoor/Google Jobs are only
    # soft-scored (fit()), not hard title-gated like CareerOps/Remote Boards.
    off_mission_titles = [
        "Growth Marketing Manager - Paid Social (Berlin, Germany)",
        # word-order fix below must stay narrow: these must NOT slip through
        # just because they contain both "strategy" and "creative" somewhere.
        "Growth Strategy and Creative Ops Manager",
        "Digital Strategy Manager",
    ]
    for title in off_mission_titles:
        assert off_mission_role({"title": title}), title

    # On-mission titles, including real variants that must not be caught —
    # "Creative Strategist" (word-form of "creative strategy") broke this
    # gate the first time it was tested; "Creative Producer" was added
    # 2026-09-16 after being found wrongly excluded. "Creative Performance
    # Strategist" (one word inserted between "creative" and "strategist")
    # was found wrongly rejected the same day, while "Performance Creative
    # Strategist" (adjacent) passed — fixed to allow one word between them,
    # forward direction only.
    on_mission_titles = [
        "Founding Creative Director",
        "Senior Creative Strategist",
        "Performance Creative Lead, Europe",
        "UGC Coordinator",
        "Generative AI Producer (Creative)",
        "AI Creative Lead (Remote)",
        "Associate Creative Director - Women's Lifestyle",
        "Creative Producer:in",
        "Freelance Creative Producer FR/IT/ES",
        "Creative Performance Strategist - US",
        "Performance Creative Strategist",
        "Creative Content Strategist",
    ]
    for title in on_mission_titles:
        assert not off_mission_role({"title": title}), title


def test_remote_plausible_ignores_unrelated_hybrid_mentions():
    from telegram_notify import remote_plausible

    # Real false-reject found 2026-09-16: Darkroom's "Specialist, Creative
    # Strategy" said "This is a fully remote role" but was rejected because
    # unrelated company-culture boilerplate later mentioned "expected to work
    # hybrid" for people near their NY/Lisbon HQs, not this role.
    assert remote_plausible({
        "title": "Specialist, Creative Strategy",
        "location": "Portugal",
        "description": (
            "This is a fully remote role supporting a team in the EST time zone. "
            "Remote-First Culture: Many roles are fully remote. Employees based in "
            "or near our New York or Lisbon HQs are expected to work hybrid with "
            "weekly in-office time."
        ),
    })
    # A listing whose *own* role is hybrid must still be rejected, even when
    # the only signal is in free-text description (no structured field).
    assert not remote_plausible({
        "title": "Associate Creative Director (Art)",
        "location": "London, England, United Kingdom",
        "description": "Hybrid role - 2 days on site in London Wall Place.",
    })
    assert not remote_plausible({
        "title": "Creative Director",
        "location": "Remote",
        "description": "This on-site role requires 3 days a week in the office.",
    })


def test_off_mission_role_word_gap_creative_lead_director():
    from telegram_notify import off_mission_role

    # Same class of bug as "Creative Strategy" -> "Creative Strategist"
    # (2026-09-16), found the same day auditing LinkedIn's full 225-job
    # local pool: "Creative Performance Lead" and similar real titles were
    # wrongly rejected while their non-inserted forms passed, purely by
    # word placement.
    on_mission_titles = [
        "Creative Performance Lead",
        "Creative Marketing Lead",
        "3D Creative Art Director",
    ]
    for title in on_mission_titles:
        assert not off_mission_role({"title": title}), title

    # Must not over-widen — these have "creative"/"director" nearby but
    # aren't creative-leadership roles.
    off_mission_titles = [
        "Marketing Director",
        "Managing Director, Creative Solutions Sales",
    ]
    for title in off_mission_titles:
        assert off_mission_role({"title": title}), title


def test_off_mission_role_ai_lead_excludes_lead_generation():
    from telegram_notify import off_mission_role

    # Real false positive found 2026-09-17 auditing a week of Telegram
    # deliveries: the bare "ai lead" phrase matched unrelated Upwork gig
    # titles about lead-generation/lead-qualification tooling, not the
    # "AI Lead" leadership role Can means.
    off_mission_titles = [
        "Set up a WhatsApp AI Lead-Qualification System (respond.io + Zapier)",
        "AI Lead Generation Specialist",
        "AI Lead Gen Manager",
    ]
    for title in off_mission_titles:
        assert off_mission_role({"title": title}), title

    # Genuine "AI Lead" usage must still pass.
    on_mission_titles = ["AI Lead", "Senior AI Lead, Creative", "AI Lead (Remote)"]
    for title in on_mission_titles:
        assert not off_mission_role({"title": title}), title
