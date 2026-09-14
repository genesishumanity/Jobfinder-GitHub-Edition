"""Can-specific triage entrypoint.

Keeps the upstream triage engine intact while overriding stale role-family guidance
and excluding the retired HiringCafe source from scoring.
"""
import triage_agent as agent

agent.ROLE_FAMILIES = (
    "creative-strategy | creative-leadership | brand-strategy | integrated-campaign | "
    "ai-creative-workflows | performance-growth-creative | creative-production-ops | "
    "client-account-success | project-program-operations | implementation | "
    "fractional-contract | adjacent-commercial | other"
)

_original_build_static_prefix = agent.build_static_prefix
_original_load_jobs = agent.load_jobs


def build_static_prefix(profile: str, resume: str) -> str:
    prompt = _original_build_static_prefix(profile, resume)
    prompt = prompt.replace(
        "strong creative-strategy and AI-enabled creative background",
        "strong creative-strategy and AI-enabled creative background",
    )
    prompt += (
        "\n\n=== CAN-SPECIFIC TRIAGE STRATEGY ===\n"
        "- Remote eligibility is mandatory. Explicit US-only / location-locked roles should be skip.\n"
        "- Do not require an exact historical job title. Reward credible transferable skills and realistic rapid upskilling.\n"
        "- Primary targets: creative strategy/leadership, brand/integrated campaigns, AI-enabled creative workflows, "
        "performance/growth creative, and creative operations/production.\n"
        "- Also consider commercially useful adjacent roles in client/account success, project/program operations, "
        "implementation and marketing when the candidate has a realistic route to success.\n"
        "- Prefer strong English-working roles with worldwide, global, EMEA, Europe, UK or contractor-friendly remote access.\n"
        "- Penalize low-value execution-only roles (generic social posting, pure video editing, pure graphic production) "
        "unless the posting clearly includes strategy/ownership.\n"
        "- The decision question is: Is this a realistic route to a well-paid remote job for this candidate?"
    )
    return prompt


def load_jobs(from_files: bool) -> list[dict]:
    jobs = _original_load_jobs(from_files)
    return [j for j in jobs if str(j.get("ats", "")).lower() != "hiringcafe"]


agent.build_static_prefix = build_static_prefix
agent.load_jobs = load_jobs


if __name__ == "__main__":
    raise SystemExit(agent.main())
