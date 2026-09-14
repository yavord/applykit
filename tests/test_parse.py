"""Resume parser unit tests: structured extraction from raw section text."""

from app.resumes.parse import parse

MARKER = {"v": "", "uncertain": True}


def _content(kind: str, text: str) -> dict | list:
    return next(sec["content"] for sec in parse(text) if sec["kind"] == kind)


def test_wrapped_bullet_folds_into_previous_bullet():
    text = """EXPERIENCE
Lead ML Engineer | Acme Corp
2021 - Present
- Built Acme's internal platform APIs (Python), web apps (JavaScript), and databases (MySQL and
PostgreSQL)
- Cut p95 latency by 40%"""

    entry = _content("experience", text)[0]

    assert entry["bullets"] == [
        "Built Acme's internal platform APIs (Python), web apps (JavaScript), "
        "and databases (MySQL and PostgreSQL)",
        "Cut p95 latency by 40%",
    ]
    assert entry["summary"] == MARKER


def test_wrapped_education_achievement_folds_into_previous_achievement():
    text = """EDUCATION
State University, 2012 - 2016
B.S. Computer Science
GPA: 3.8
- Led robotics team
winning regional finals"""

    entry = _content("education", text)[0]

    assert entry["achievements"] == ["Led robotics team winning regional finals"]


def test_degree_keeps_major_after_comma():
    text = """EDUCATION
State University, 2012 - 2016
Master of Science, Computer Science
GPA: 3.8

Stanford University, 2018 - 2020
B.S. Mathematics, GPA: 3.9"""

    state_u, stanford = _content("education", text)

    assert state_u["degree"] == "Master of Science, Computer Science"
    assert stanford["degree"] == "B.S. Mathematics"
