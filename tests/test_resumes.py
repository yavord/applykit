"""ResumeRepo behavior: naming, active invariant, sections, revision."""

import pytest
from sqlalchemy import select

from app.data.models import Resume, Section, SectionKind
from app.data.repositories import ResumeRepo


@pytest.fixture
def repo():
    return ResumeRepo()


def test_create_and_list_ordered_by_name(repo):
    repo.create("beta")
    repo.create("alpha")

    assert [r.name for r in repo.list()] == ["alpha", "beta"]


def test_duplicate_name_raises(repo):
    repo.create("Main")

    with pytest.raises(ValueError):
        repo.create("Main")


def test_empty_name_rejected(repo):
    with pytest.raises(ValueError):
        repo.create("   ")


def test_exactly_one_active_row(repo, session):
    a = repo.create("a")
    b = repo.create("b")

    repo.set_active(a.id)
    repo.set_active(b.id)

    actives = session.scalars(select(Resume).where(Resume.is_active.is_(True))).all()

    assert [r.id for r in actives] == [b.id]


def test_delete_active_raises(repo):
    a = repo.create("a")
    repo.set_active(a.id)

    with pytest.raises(ValueError):
        repo.delete(a.id)


def test_delete_inactive_and_sections_cascade(repo, session):
    a = repo.create("a")
    b = repo.create("b")
    repo.set_active(b.id)
    repo.replace_sections(
        a.id,
        [
            {
                "kind": SectionKind.SKILLS,
                "position": 0,
                "content": [{"group": "General", "skills": ["x"]}],
            }
        ],
    )

    repo.delete(a.id)

    assert session.get(Resume, a.id) is None
    assert session.scalars(select(Section).where(Section.resume_id == a.id)).all() == []


def test_replace_sections_rejects_unknown_kind(repo):
    a = repo.create("a")

    with pytest.raises(ValueError):
        repo.replace_sections(a.id, [{"kind": "portfolios", "position": 0, "content": []}])

    assert repo.revision(a.id) == 1


def test_replace_sections_rejects_unknown_field(repo):
    a = repo.create("a")

    with pytest.raises(ValueError):
        repo.replace_sections(
            a.id,
            [{"kind": SectionKind.EDUCATION, "position": 0, "content": [{"degre": "BSc"}]}],
        )

    assert repo.revision(a.id) == 1


def test_replace_sections_rejects_mistyped_list_field(repo):
    a = repo.create("a")

    with pytest.raises(ValueError):
        repo.replace_sections(
            a.id,
            [
                {
                    "kind": SectionKind.SKILLS,
                    "position": 0,
                    "content": [{"group": "G", "skills": "python"}],
                }
            ],
        )

    assert repo.revision(a.id) == 1


def test_replace_sections_rejects_malformed_links(repo):
    a = repo.create("a")

    with pytest.raises(ValueError):
        repo.replace_sections(
            a.id,
            [
                {
                    "kind": SectionKind.CONTACT,
                    "position": 0,
                    "content": {"links": [{"url": "x", "label": "site"}]},
                }
            ],
        )

    assert repo.revision(a.id) == 1


def test_replace_sections_rejects_mistyped_scalar_field(repo):
    a = repo.create("a")

    with pytest.raises(ValueError):
        repo.replace_sections(
            a.id,
            [{"kind": SectionKind.SUMMARY, "position": 0, "content": {"text": ["x"]}}],
        )

    assert repo.revision(a.id) == 1


def test_replace_sections_accepts_uncertainty_markers(repo):
    a = repo.create("a")

    repo.replace_sections(
        a.id,
        [
            {
                "kind": SectionKind.CONTACT,
                "position": 0,
                "content": {"name": {"v": "Y", "uncertain": True}},
            },
            {
                "kind": SectionKind.SKILLS,
                "position": 1,
                "content": [{"group": "General", "skills": [{"v": "Agile", "uncertain": False}]}],
            },
        ],
    )

    assert repo.revision(a.id) == 2


def test_create_from_import_persists_source_and_sections(repo, session):
    resume = repo.create_from_import(
        "Main",
        "uploads/abc.pdf",
        "pdf",
        [
            {"kind": SectionKind.CONTACT, "position": 0, "content": {"name": "Y"}},
            {"kind": SectionKind.SUMMARY, "position": 1, "content": {"text": "t"}},
        ],
    )

    stored = session.get(Resume, resume.id)
    assert stored.name == "Main"
    assert stored.source_path == "uploads/abc.pdf"
    assert stored.source_kind == "pdf"
    assert stored.revision == 1

    sections = list(session.scalars(select(Section).where(Section.resume_id == resume.id)))
    assert [(s.kind, s.position, s.content) for s in sections] == [
        (SectionKind.CONTACT, 0, {"name": "Y"}),
        (SectionKind.SUMMARY, 1, {"text": "t"}),
    ]


def test_create_from_import_rejects_duplicate_name(repo):
    repo.create_from_import("Main", "uploads/abc.pdf", "pdf", [])

    with pytest.raises(ValueError, match="already exists"):
        repo.create_from_import("Main", "uploads/def.pdf", "pdf", [])


def test_create_from_import_rejects_unknown_section_kind(repo):
    with pytest.raises(ValueError):
        repo.create_from_import(
            "Main", "uploads/abc.pdf", "pdf", [{"kind": "nope", "position": 0, "content": []}]
        )
