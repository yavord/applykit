"""DocumentRepo behavior: insert-only creation, in-place user edits."""

import pytest

from app.data.models import DocKind
from app.data.repositories import DocumentRepo, JobData, JobRepo, ResumeRepo


@pytest.fixture
def repos():
    resumes = ResumeRepo()
    jobs = JobRepo()
    documents = DocumentRepo()

    resume = resumes.create("Main")
    resumes.set_active(resume.id)
    job_id = jobs.upsert(
        JobData(
            source="test",
            title="Engineer",
            company="Acme",
            norm_company="acme",
            norm_title="engineer",
        )
    )

    return documents, resume.id, job_id


def test_create_and_list_for_job(repos, session):
    docs, resume_id, job_id = repos

    d1 = docs.create(resume_id, job_id, DocKind.COVER_LETTER, {"p": 1})
    d2 = docs.create(resume_id, job_id, DocKind.COVER_LETTER, {"p": 2})

    assert [d.id for d in docs.list_for_job(job_id)] == [d1.id, d2.id]
    assert d1.kind == DocKind.COVER_LETTER


def test_multiple_kinds_per_job_allowed(repos):
    docs, resume_id, job_id = repos

    docs.create(resume_id, job_id, DocKind.COVER_LETTER, {"p": 1})
    docs.create(resume_id, job_id, DocKind.TAILORED_RESUME, {"p": 2})

    assert len(docs.list_for_job(job_id)) == 2


def test_update_persists_manual_edit(repos):
    docs, resume_id, job_id = repos
    doc = docs.create(resume_id, job_id, DocKind.COVER_LETTER, {"p": 1})

    docs.update(doc.id, {"p": 99})

    assert docs.get(doc.id).content == {"p": 99}


def test_update_missing_raises(repos):
    docs, _, _ = repos

    with pytest.raises(ValueError):
        docs.update(9999, {"p": 1})


def test_resume_delete_cascades_documents(repos, session):
    docs, resume_id, job_id = repos
    docs.create(resume_id, job_id, DocKind.COVER_LETTER, {"p": 1})

    resumes = ResumeRepo()
    other = resumes.create("Other")
    resumes.set_active(other.id)
    resumes.delete(resume_id)

    assert docs.list_for_job(job_id) == []
