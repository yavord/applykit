"""FitRepo behavior: cache row per job with staleness keys."""

from app.data.repositories import FitRepo, JobData, JobRepo, ResumeRepo

COMPONENTS = {
    "skills": {"weight": 50, "score": 90, "evidence": [], "missing": []},
    "experience": {"weight": 30, "score": 80, "evidence": [], "missing": []},
    "role": {"weight": 20, "score": 70, "evidence": [], "missing": []},
    "missing_requirements": [],
}


def make_job() -> int:
    return JobRepo().upsert(
        JobData(
            source="test",
            title="Engineer",
            company="Acme",
            norm_company="acme",
            norm_title="engineer",
        )
    )


_n = 0


def make_resume() -> int:
    global _n

    _n += 1

    return ResumeRepo().create(f"R{_n}").id


def test_set_get_round_trip():
    repo = FitRepo()
    job_id = make_job()
    resume_id = make_resume()

    repo.set(job_id, resume_id, 84, COMPONENTS, resume_rev=3, profile_rev=2)

    score = repo.get(job_id, resume_id)
    assert score.total == 84
    assert score.components["skills"]["score"] == 90
    assert score.computed_at is not None


def test_set_upserts_per_job_resume_pair():
    repo = FitRepo()
    job_id = make_job()
    resume_id = make_resume()

    repo.set(job_id, resume_id, 84, COMPONENTS, resume_rev=3, profile_rev=2)
    repo.set(job_id, resume_id, 91, COMPONENTS, resume_rev=4, profile_rev=2)

    score = repo.get(job_id, resume_id)
    assert score.total == 91
    assert score.resume_rev == 4


def test_scores_for_two_resumes_coexist():
    repo = FitRepo()
    job_id = make_job()
    first = make_resume()
    second = make_resume()

    repo.set(job_id, first, 84, COMPONENTS, resume_rev=1, profile_rev=2)
    repo.set(job_id, second, 91, COMPONENTS, resume_rev=1, profile_rev=2)

    assert repo.get(job_id, first).total == 84
    assert repo.get(job_id, second).total == 91


def test_keys_stored_for_staleness_check():
    repo = FitRepo()
    job_id = make_job()
    resume_id = make_resume()

    repo.set(job_id, resume_id, 84, COMPONENTS, resume_rev=3, profile_rev=2)

    score = repo.get(job_id, resume_id)
    assert (score.resume_rev, score.profile_rev) == (3, 2)


def test_missing_job_returns_none():
    assert FitRepo().get(9999, 9999) is None
