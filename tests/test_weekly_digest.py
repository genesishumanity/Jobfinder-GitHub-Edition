import json
from datetime import datetime, timedelta, timezone

import weekly_digest


def test_build_digest_empty_window(tmp_path, monkeypatch):
    # Point at fixture paths that don't exist -> should degrade gracefully to
    # the "0 roles" message, never raise.
    monkeypatch.setattr(weekly_digest, "NOTIFIED_PATH", str(tmp_path / "missing_notified.json"))
    monkeypatch.setattr(weekly_digest, "ALL_JOBS_PATH", str(tmp_path / "missing_all_jobs.json"))
    result = weekly_digest.build_digest(days=7)
    assert isinstance(result, str)
    assert "Haftalık JobFinder özeti" in result
    assert "hiç ilan gönderilmedi" in result


def test_build_digest_counts_and_groups_by_source(tmp_path, monkeypatch):
    notified_path = tmp_path / "telegram_notified.json"
    all_jobs_path = tmp_path / "all_jobs.json"

    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=1)).isoformat()
    old = (now - timedelta(days=30)).isoformat()

    notified_path.write_text(json.dumps({
        "records": {
            "acme|creative director|london": {"last_sent": recent},
            "beta|ai producer|remote": {"last_sent": recent},
            "stale|old role|nyc": {"last_sent": old},
        }
    }))
    all_jobs_path.write_text(json.dumps({
        "jobs": [
            {"company": "acme", "title": "Creative Director", "location": "London", "ats": "LinkedIn"},
            {"company": "beta", "title": "AI Producer", "location": "Remote", "ats": "GoogleJobs"},
        ]
    }))

    monkeypatch.setattr(weekly_digest, "NOTIFIED_PATH", str(notified_path))
    monkeypatch.setattr(weekly_digest, "ALL_JOBS_PATH", str(all_jobs_path))

    result = weekly_digest.build_digest(days=7)
    assert "Toplam 2 ilan gönderildi" in result
    assert "LinkedIn: 1" in result
    assert "Google Jobs: 1" in result
    assert "Creative Director" in result
    assert "old role" not in result  # outside the 7-day window
    # Sources with zero deliveries this window get flagged, e.g. Indeed here.
    assert "Indeed" in result
    assert "⚠️" in result


def test_source_label_mapping():
    assert weekly_digest._source_label("GoogleJobs") == "Google Jobs"
    assert weekly_digest._source_label("CareerOps/workday") == "CareerOps (Workday)"
    assert weekly_digest._source_label("CareerOps/lever") == "CareerOps (Lever)"
    assert weekly_digest._source_label("unknown") == "Diğer"
    assert weekly_digest._source_label(None) == "Diğer"
