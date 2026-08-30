"""Rule-based structured parser: text lines -> SECTION_SCHEMA-shaped sections.

Ground rule: never silently guess. Every scalar the heuristics leave unfilled
is emitted as the uncertainty marker {"v": "", "uncertain": true}; missing
lists stay []. Sections with zero content are omitted (contact excepted).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.data.models import SectionKind

_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
_DATE = rf"{_MONTH}\s*\d{{4}}|\d{{4}}"
_RANGE_RE = re.compile(
    rf"(?P<start>{_DATE})\s*(?:-|–|—|to)\s*(?P<end>{_DATE}|[Pp]resent|[Cc]urrent)"
)
_SINGLE_DATE_RE = re.compile(rf"\b(?P<date>{_DATE})\b")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
_LINK_RE = re.compile(r"https?://[^\s|,;]+|(?:www\.)?(?:linkedin|github)\.com/[^\s|,;]+")
_LOCATION_RE = re.compile(r"^[\w .-]+,\s*[\w .-]+$")
_GPA_RE = re.compile(r"[Gg][Pp][Aa][:\s]*(\d+(?:\.\d{1,2})?)")
_LINK_HOST_NAMES = {"linkedin.com": "LinkedIn", "github.com": "GitHub"}
_BULLET_PREFIX = ("•", "-", "·", "*", "◦", "▪")
_DEGREE_PREFIX = re.compile(
    r"^(?:Bachelor|Master|Doctor|Associate|PhD|Ph\.?D|MBA|M\.?Eng|Engineer's|"
    r"B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?Sc\.?|M\.?A\.?)(?:\s|$)",
    re.IGNORECASE,
)

_SEP_RE = re.compile(r"\s+[|·]\s+")
_AT_RE = re.compile(r"\s+at\s+")
_COURSEWORK_RE = re.compile(r"^\s*(?:[Rr]elevant )?[Cc]oursework[:]\s*(.+)$")
_SKILL_GROUP_RE = re.compile(r"(?P<group>[^:|,()]+?)\s*[:|]\s*(?P<items>.+)$")
_SKILL_SPLIT_RE = re.compile(r"(?:,|;|\||·)\s*(?![^()]*\))")

_ALIASES = {
    "contact": SectionKind.CONTACT,
    "summary": SectionKind.SUMMARY,
    "professional summary": SectionKind.SUMMARY,
    "career summary": SectionKind.SUMMARY,
    "profile": SectionKind.SUMMARY,
    "objective": SectionKind.SUMMARY,
    "skills": SectionKind.SKILLS,
    "technical skills": SectionKind.SKILLS,
    "core skills": SectionKind.SKILLS,
    "competencies": SectionKind.SKILLS,
    "areas of expertise": SectionKind.SKILLS,
    "technologies": SectionKind.SKILLS,
    "skills and abilities": SectionKind.SKILLS,
    "skills & abilities": SectionKind.SKILLS,
    "experience": SectionKind.EXPERIENCE,
    "work experience": SectionKind.EXPERIENCE,
    "professional experience": SectionKind.EXPERIENCE,
    "employment history": SectionKind.EXPERIENCE,
    "work history": SectionKind.EXPERIENCE,
    "relevant experience": SectionKind.EXPERIENCE,
    "education": SectionKind.EDUCATION,
    "academic background": SectionKind.EDUCATION,
    "academic history": SectionKind.EDUCATION,
    "projects": SectionKind.PROJECTS,
    "personal projects": SectionKind.PROJECTS,
    "academic projects": SectionKind.PROJECTS,
    "certifications": SectionKind.CERTIFICATIONS,
    "certificates": SectionKind.CERTIFICATIONS,
    "licenses": SectionKind.CERTIFICATIONS,
    "licenses & certifications": SectionKind.CERTIFICATIONS,
}

_MARKER = {"v": "", "uncertain": True}


def parse(text: str) -> list[dict]:
    """Split text into sections; each dict is {"kind", "content"}."""
    contact_lines: list[str] = []
    chunks: list[tuple[SectionKind, list[str]]] = []

    for line in text.splitlines():
        kind = _ALIASES.get(_normalize(line))
        if kind is not None:
            chunks.append((kind, []))
        elif chunks:
            chunks[-1][1].append(line)
        else:
            contact_lines.append(line)

    out = [{"kind": SectionKind.CONTACT, "content": _parse_contact(contact_lines)}]

    for kind, lines in chunks:
        content = _PARSERS[kind](lines)
        if content is not None:
            out.append({"kind": kind, "content": content})

    return out


def _normalize(line: str) -> str:
    return " ".join(line.casefold().split())


def _mark(text: str) -> str | dict:
    return text if text.strip() else _MARKER


def _m() -> dict:
    return _MARKER


def _paragraphs(lines: list[str]) -> list[list[str]]:
    paras: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped:
            current.append(stripped)
        elif current:
            paras.append(current)
            current = []

    if current:
        paras.append(current)

    return paras


def _is_bullet(line: str) -> bool:
    return line.startswith(_BULLET_PREFIX)


def _strip_bullet(line: str) -> str:
    for prefix in _BULLET_PREFIX:
        if line.startswith(prefix):
            return line[len(prefix) :].strip()

    return line.strip()


def _parse_contact(lines: list[str]) -> dict:
    tokens = [t.strip() for line in lines for t in re.split(r"[|·;]", line) if t.strip()]
    joined = " ".join(tokens)

    emails = _EMAIL_RE.findall(joined)
    phones = _PHONE_RE.findall(joined)
    links = _LINK_RE.findall(joined)

    residual = []
    for tok in tokens:
        rest = _LINK_RE.sub("", _PHONE_RE.sub("", _EMAIL_RE.sub("", tok))).strip()
        if rest:
            residual.append(rest)

    name = subtitle = location = ""
    tags: list[str] = []

    for i, tok in enumerate(residual):
        if i == 0:
            name = tok
        elif not location and _LOCATION_RE.match(tok):
            location = tok
        elif not subtitle:
            subtitle = tok
        else:
            tags.extend(t.strip() for t in re.split(r"[,|;]", tok) if t.strip())

    return {
        "name": _mark(name),
        "subtitle": _mark(subtitle),
        "email": _mark(emails[0] if emails else ""),
        "phone": _mark(phones[0] if phones else ""),
        "location": _mark(location),
        "tags": tags,
        "links": [{"name": _link_name(url), "url": url} for url in links],
    }


def _link_name(url: str) -> str:
    if url.startswith("http"):
        host = url.split("://", 1)[1].split("/", 1)[0]
        host = host[4:] if host.startswith("www.") else host
    else:
        host = url.split("/", 1)[0]

    return _LINK_HOST_NAMES.get(host, host)


def _parse_summary(lines: list[str]) -> dict | None:
    joined = "\n\n".join(" ".join(para) for para in _paragraphs(lines))

    if not joined.strip():
        return None
    return {"text": _mark(joined)}


def _split_skills(items: str) -> list[str]:
    return [s.strip() for s in _SKILL_SPLIT_RE.split(items) if s.strip()]


def _parse_skills(lines: list[str]) -> list[dict] | None:
    groups: list[tuple[str, list[str]]] = []

    for line in lines:
        stripped = _strip_bullet(line)
        if not stripped:
            continue

        m = _SKILL_GROUP_RE.match(stripped)
        if m:
            groups.append((m.group("group"), [m.group("items")]))
        elif groups and _unclosed_paren(groups[-1][1]):
            # Wrapped bullet continuation: re-split the merged raw text so
            # parentheses balance across the wrap (e.g. GCP (BigQuery, ...) ).
            groups[-1][1].append(stripped)
        else:
            groups.append(("", [stripped]))

    if not groups:
        return None

    return [
        {"group": _mark(group), "skills": _split_skills(" ".join(parts))} for group, parts in groups
    ]


def _unclosed_paren(parts: list[str]) -> bool:
    joined = " ".join(parts)

    return joined.count("(") > joined.count(")")


@dataclass
class _Entry:
    """One work/project entry: header lines, body lines, and full paragraph text."""

    header: list[str] = field(default_factory=list)
    body: list[str] = field(default_factory=list)
    text: str = ""


def _first_range_line(para: list[str]) -> int | None:
    for i, line in enumerate(para):
        if _RANGE_RE.search(line):
            return i

    return None


def _walk_entries(lines: list[str]) -> list[_Entry]:  # noqa: PLR0912
    """Split a chunk into entries; every line with a date range starts one."""
    entries: list[_Entry] = []
    current: _Entry | None = None

    for para in _paragraphs(lines):
        splits = [i for i, line in enumerate(para) if _RANGE_RE.search(line)]

        if not splits:
            if current is not None:
                current.body.extend(para)
                current.text += "\n" + "\n".join(para)
            elif para:
                current = _Entry(header=list(para), text="\n".join(para))
            continue

        if current is not None:
            entries.append(current)
            current = None

        # A paragraph may hold several merged entries (no blank separators): each
        # range-bearing line starts a new entry. Lines are typed first: bullets
        # and their wrapped continuations are body, so they never leak into a
        # following entry's header.
        roles = []
        in_body = False
        for line in para:
            if _is_bullet(line):
                roles.append("body")
                in_body = True
            elif _RANGE_RE.search(line):
                roles.append("range")
                in_body = False
            elif in_body:
                roles.append("body")
            else:
                roles.append("header")

        starts = [0]
        for k in range(1, len(splits)):
            body_before = [i for i in range(splits[k - 1] + 1, splits[k]) if roles[i] == "body"]
            starts.append(body_before[-1] + 1 if body_before else splits[k - 1] + 1)

        ends = [*starts[1:], len(para)]

        for k, split in enumerate(splits):
            start, end = starts[k], ends[k]
            segment = para[start:end]
            rel = split - start
            header = [line for i, line in enumerate(segment[:rel]) if roles[start + i] == "header"]
            header.append(segment[rel])

            cut = next(
                (
                    j
                    for j, line in enumerate(segment[rel + 1 :])
                    if roles[start + rel + 1 + j] == "body"
                ),
                None,
            )
            if cut is None:
                header.extend(segment[rel + 1 :])
                body = []
            else:
                header.extend(segment[rel + 1 : rel + 1 + cut])
                body = segment[rel + 1 + cut :]

            entries.append(_Entry(header=header, body=body, text="\n".join(segment)))

    if current is not None:
        entries.append(current)

    return entries


def _split_header_body(entry: _Entry) -> tuple[list[str], list[str]]:
    """Header = lines before the first bullet; the rest is body."""
    lines = entry.header + entry.body
    bullet_idx = next((i for i, line in enumerate(lines) if _is_bullet(line)), -1)

    if bullet_idx == -1:
        return lines, []

    return lines[:bullet_idx], lines[bullet_idx:]


def _is_date_line(line: str) -> bool:
    return bool(_RANGE_RE.search(line) or _SINGLE_DATE_RE.search(line))


def _parse_header(header: list[str]) -> tuple[str, str, str, str, str, str]:  # noqa: PLR0912
    """Parse an entry header; return (title, org, location, start, end, dates)."""
    title = org = location = start = end = dates = ""
    date_idx: int | None = None
    match = None
    is_range = False

    for i, line in enumerate(header):
        m = _RANGE_RE.search(line)
        if m is not None:
            date_idx, match, is_range = i, m, True
            break

    if date_idx is None:
        for i, line in enumerate(header):
            m = _SINGLE_DATE_RE.search(line)
            if m is not None:
                date_idx, match = i, m
                break

    if date_idx is None or match is None:
        return _parse_header_no_date(header)

    line = header[date_idx]
    pre = line[: match.start()].strip()
    consumed: set[int] = set()

    if is_range:
        start = match.group("start").strip()
        end = match.group("end").strip()
        dates = match.group(0).strip()
    else:
        end = match.group("date").strip()
        dates = match.group(0).strip()

    if _SEP_RE.search(pre):
        title, org = _split_sep(pre)
    elif pre:
        org = pre
    elif date_idx > 0:
        prev = header[date_idx - 1]
        if _SEP_RE.search(prev):
            title, org = _split_sep(prev)
            consumed.add(date_idx - 1)
        elif _AT_RE.search(prev):
            title, org = _split_at(prev)
            consumed.add(date_idx - 1)
        else:
            org = prev
            consumed.add(date_idx - 1)

    for i, line in enumerate(header):
        if i == date_idx or i in consumed:
            continue
        if not location and _LOCATION_RE.match(line):
            location = line
        elif not title and not _is_date_line(line):
            title = line

    return title, org, location, start, end, dates


def _parse_header_no_date(header: list[str]) -> tuple[str, str, str, str, str, str]:
    title = org = ""

    sep_idx = next((i for i, line in enumerate(header) if _SEP_RE.search(line)), None)
    if sep_idx is not None:
        title, org = _split_sep(header[sep_idx])
    elif header and _AT_RE.search(header[0]):
        title, org = _split_at(header[0])
    elif header:
        title = header[0]

    return title, org, "", "", "", ""


def _split_sep(line: str) -> tuple[str, str]:
    parts = _SEP_RE.split(line, maxsplit=1)
    return parts[0].strip(), parts[1].strip()


def _split_at(line: str) -> tuple[str, str]:
    parts = _AT_RE.split(line, maxsplit=1)
    return parts[0].strip(), parts[1].strip()


def _parse_body(body_lines: list[str]) -> tuple[list[str | dict], str]:
    bullets: list[str | dict] = []
    summary_lines: list[str] = []

    for line in body_lines:
        if _is_bullet(line):
            bullets.append(_mark(_strip_bullet(line)))
        else:
            summary_lines.append(line)

    return bullets, " ".join(summary_lines)


def _parse_experience(lines: list[str]) -> list[dict] | None:
    out = []
    for entry in _walk_entries(lines):
        header, body = _split_header_body(entry)
        title, org, location, start, end, _dates = _parse_header(header)
        bullets, summary = _parse_body(body)

        out.append(
            {
                "title": _mark(title),
                "organization": _mark(org),
                "location": _mark(location),
                "start": _mark(start),
                "end": _mark(end),
                "summary": _mark(summary),
                "bullets": bullets,
            }
        )

    return out or None


def _parse_projects(lines: list[str]) -> list[dict] | None:
    out = []
    for entry in _walk_entries(lines):
        header, body = _split_header_body(entry)
        title, org, _loc, _s, _e, dates = _parse_header(header)
        bullets, _summary = _parse_body(body)
        url_match = _LINK_RE.search(entry.text)

        out.append(
            {
                "title": _mark(title),
                "organization": _mark(org),
                "dates": _mark(dates),
                "url": _mark(url_match.group(0).strip() if url_match else ""),
                "bullets": bullets,
            }
        )

    return out or None


def _parse_education(lines: list[str]) -> list[dict] | None:
    out = []

    for para in _paragraphs(lines):
        # A paragraph may hold several merged schools; each range-bearing line
        # starts a new education entry, else the whole paragraph is one.
        splits = [i for i, line in enumerate(para) if _RANGE_RE.search(line)]
        bounds = [0, *splits[1:], len(para)]
        groups = [para[bounds[k] : bounds[k + 1]] for k in range(len(bounds) - 1)]

        for group in groups:
            degree = institution = location = start = end = gpa = ""
            achievements: list[str | dict] = []
            coursework: list[str] = []
            group_text = " ".join(group)

            for line in group:
                match = _RANGE_RE.search(line)
                is_range = match is not None

                if not is_range:
                    match = _SINGLE_DATE_RE.search(line)

                if match is not None and not institution:
                    institution = line[: match.start()].strip().rstrip(",|").strip()
                    if is_range:
                        start = match.group("start").strip()
                        end = match.group("end").strip()
                    else:
                        end = match.group("date").strip()
                    continue

                if not degree and _DEGREE_PREFIX.match(line):
                    degree = line.split(",", 1)[0].strip()
                    continue

                if not location and _LOCATION_RE.match(line):
                    location = line
                    continue

                gpa_match = _GPA_RE.search(group_text)
                if not gpa and gpa_match:
                    gpa = gpa_match.group(1)
                    continue

                coursework_match = _COURSEWORK_RE.match(line)
                if coursework_match:
                    coursework = [
                        s.strip()
                        for s in re.split(r"[,;]\s*", coursework_match.group(1))
                        if s.strip()
                    ]
                    continue

                if _is_bullet(line):
                    achievements.append(_mark(_strip_bullet(line)))
                    continue

            out.append(
                {
                    "degree": _mark(degree),
                    "institution": _mark(institution),
                    "location": _mark(location),
                    "start": _mark(start),
                    "end": _mark(end),
                    "gpa": _mark(gpa),
                    "achievements": achievements,
                    "coursework": coursework,
                }
            )

    return out or None


def _parse_certifications(lines: list[str]) -> list[dict] | None:
    out = []

    for para in _paragraphs(lines):
        parts = [p.strip() for p in para[0].split(",")]

        if len(parts) < 2:
            parts = [p.strip() for p in re.split(r"\s+[–-]\s+", para[0], maxsplit=1)]

        name = parts[0] if parts else ""
        issuer = parts[1] if len(parts) > 1 else ""
        date = next((p for p in parts[2:] if _SINGLE_DATE_RE.fullmatch(p)), "")
        url_match = _LINK_RE.search(" ".join(para))

        out.append(
            {
                "name": _mark(name),
                "issuer": _mark(issuer),
                "date": _mark(date),
                "url": _mark(url_match.group(0).strip() if url_match else ""),
            }
        )

    return out or None


_PARSERS = {
    SectionKind.SUMMARY: _parse_summary,
    SectionKind.SKILLS: _parse_skills,
    SectionKind.EXPERIENCE: _parse_experience,
    SectionKind.EDUCATION: _parse_education,
    SectionKind.PROJECTS: _parse_projects,
    SectionKind.CERTIFICATIONS: _parse_certifications,
}
