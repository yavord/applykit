"""Canonical vocabulary folding for the exact-match job fields."""

from app.discovery import EmploymentType, Seniority, WorkArrangement


def test_work_arrangement_spellings_fold():
    assert WorkArrangement.canonical("Remote") == "remote"
    assert WorkArrangement.canonical("FULLY REMOTE") == "remote"
    assert WorkArrangement.canonical("  work from home ") == "remote"
    assert WorkArrangement.canonical("Remote-OK") == "remote"
    assert WorkArrangement.canonical("100% remote") == "remote"
    assert WorkArrangement.canonical("Hybrid") == "hybrid"
    assert WorkArrangement.canonical("partially remote") == "hybrid"
    assert WorkArrangement.canonical("On-Site") == "onsite"
    assert WorkArrangement.canonical("in office") == "onsite"


def test_employment_type_spellings_fold():
    assert EmploymentType.canonical("Full-Time") == "full_time"
    assert EmploymentType.canonical("full_time") == "full_time"
    assert EmploymentType.canonical("FULL TIME") == "full_time"
    assert EmploymentType.canonical("Part Time") == "part_time"
    assert EmploymentType.canonical("Contractor") == "contract"
    assert EmploymentType.canonical("Freelance") == "freelance"
    assert EmploymentType.canonical("Temp") == "temporary"
    assert EmploymentType.canonical("Intern") == "internship"


def test_seniority_spellings_fold():
    assert Seniority.canonical("Sr.") == "senior"
    assert Seniority.canonical("Senior") == "senior"
    assert Seniority.canonical("Junior") == "entry"
    assert Seniority.canonical("Entry Level") == "entry"
    assert Seniority.canonical("Mid-Level") == "mid"
    assert Seniority.canonical("Principal") == "lead"
    assert Seniority.canonical("Staff") == "lead"
    assert Seniority.canonical("Director") == "lead"


def test_unknown_spelling_kept_verbatim():
    assert Seniority.canonical("Chief of Staff") == "Chief of Staff"
    assert EmploymentType.canonical("Freelance/Contract") == "Freelance/Contract"


def test_blank_values_become_none():
    for cls in (WorkArrangement, EmploymentType, Seniority):
        assert cls.canonical(None) is None
        assert cls.canonical("") is None
        assert cls.canonical("   ") is None


def test_every_member_round_trips():
    for cls in (WorkArrangement, EmploymentType, Seniority):
        for member in cls:
            assert cls.canonical(member.value) == member.value
