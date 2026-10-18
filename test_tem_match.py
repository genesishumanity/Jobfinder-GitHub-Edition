from tem_match import tem_score


def test_reference_tem_role_is_gold():
    job = {
        "company": "tem",
        "title": "Brand & Creative Design Lead",
        "location": "United Kingdom — Remote",
        "description": """
        Senior hands-on creative role. Lead an AI-first practice using modern AI tools and workflows
        to accelerate concepting, iteration and production. Shape a creative system, visual identity
        and campaign storytelling. Startup and scale-up environment. Remote-first. Collaborate
        cross-functionally with Brand, Product and Growth to drive product adoption and business outcomes.
        """,
    }
    score, reasons = tem_score(job)
    assert score >= 72, (score, reasons)


def test_hybrid_dutch_role_is_rejected():
    job = {
        "title": "Dutch Speaking Google Ads Account Manager (Hybrid)",
        "location": "Barcelona",
        "description": "Hybrid only. Fluent Dutch C1 required. Three days in office.",
    }
    score, _ = tem_score(job)
    assert score == 0
