#!/usr/bin/env python3
"""Generate graph.html — an interactive map of courses, books, and progress.

Books with `role: companion` frontmatter are for skimming: they are shown
in their course's card but do not affect layout, routes, or edges.

Layout: rows are subject areas (course `area:` frontmatter), columns are
the earliest stage at which some member book becomes readable. Each course is a
card listing its member books. Edges run from a prerequisite course to
the card (when every member needs it) or to the specific book row that
needs it. Edges implied transitively are dropped from the drawing.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "books"
COURSES = ROOT / "courses"
STATUS = ROOT / "status.md"
PREFS = ROOT / "preferences.md"
OUT = ROOT / "graph.html"

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?(?:#[^\]]+)?\]\]")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)

# Row order of the swimlanes. Unknown areas are appended at the end.
AREAS = [
    ("panorama", "Panoramas & history"),
    ("foundations", "Foundations & logic"),
    ("categories", "Categories"),
    ("algebra", "Algebra"),
    ("number-theory", "Number theory"),
    ("algebraic-geometry", "Algebraic geometry"),
    ("topology-geometry", "Topology & geometry"),
    ("analysis", "Analysis"),
    ("probability", "Probability & statistics"),
    ("combinatorics", "Combinatorics"),
]


def read(p):
    return p.read_text() if p.exists() else ""


def section_text(text, heading):
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^##\s", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def section(text, heading):
    return [ln for ln in section_text(text, heading).splitlines() if ln.lstrip().startswith("-")]


def links_in(lines):
    out = []
    for ln in lines:
        out.extend(WIKILINK.findall(ln))
    return out


def title_of(p):
    for line in read(p).splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return p.stem


def notes_of(p):
    return section_text(read(p), "Notes").strip()


def frontmatter(text):
    m = FRONTMATTER.match(text)
    if not m:
        return {}
    pairs = (ln.split(":", 1) for ln in m.group(1).splitlines() if ":" in ln)
    return {k.strip(): v.strip() for k, v in pairs}


def status_details(text, heading):
    """Map book id -> the free text after its wikilink on the status line."""
    out = {}
    for ln in section(text, heading):
        m = WIKILINK.search(ln)
        if m:
            out[m.group(1)] = ln[m.end():].strip().lstrip("—-– ").strip()
    return out


def main():
    book_files = sorted(BOOKS.glob("*.md"))
    course_files = sorted(COURSES.glob("*.md"))
    book_ids = {p.stem for p in book_files}
    course_ids = {p.stem for p in course_files}

    prereqs = {p.stem: [r for r in links_in(section(read(p), "Prerequisites")) if r in course_ids]
               for p in book_files}
    members = {p.stem: [m for m in links_in(section(read(p), "Members")) if m in book_ids]
               for p in course_files}
    fm = {p.stem: frontmatter(read(p)) for p in course_files}
    bfm = {p.stem: frontmatter(read(p)) for p in book_files}
    companion = {b for b in book_ids if bfm[b].get("role") == "companion"}

    def primaries(c):
        """Members that drive layout, routes, and edges (companions are for skimming)."""
        return [m for m in members[c] if m not in companion] or members[c]

    areas = {c: fm[c].get("area", "other") for c in course_ids}

    status_text = read(STATUS)
    finished_details = status_details(status_text, "Finished")
    reading_details = status_details(status_text, "Reading")
    finished = set(finished_details)
    reading = set(reading_details)
    skimmed_details = status_details(status_text, "Skimmed")

    prefs = read(PREFS)
    focus = set(links_in(section(prefs, "Current focus"))) & course_ids
    goals = [g for g in WIKILINK.findall(section_text(prefs, "Long-term direction")) if g in course_ids]

    satisfied = {c for c in course_ids if any(m in finished for m in members[c])}

    def book_status(b):
        if b in finished:
            return "finished"
        if b in reading:
            return "reading"
        return "open" if all(p in satisfied for p in prereqs[b]) else "locked"

    bstatus = {b: book_status(b) for b in book_ids}

    def course_status(c):
        ms = [bstatus[m] for m in members[c]]
        if "finished" in ms:
            return "satisfied"
        if "reading" in ms:
            return "active"
        if any(bstatus[m] == "open" for m in primaries(c)):
            return "open"
        return "locked"

    def course_prereqs(c):
        return sorted({p for m in primaries(c) for p in prereqs[m]})

    @lru_cache(None)
    def book_layer(b):
        return 0 if not prereqs[b] else 1 + max(layer(p) for p in prereqs[b])

    @lru_cache(None)
    def layer(c):
        """Earliest stage at which some member book becomes readable."""
        return min((book_layer(m) for m in primaries(c)), default=0)

    @lru_cache(None)
    def strong_ancestors(c):
        """Courses completed before `c` no matter which member book is used."""
        sets = []
        for m in primaries(c):
            s = set()
            for p in prereqs[m]:
                s |= {p} | strong_ancestors(p)
            sets.append(s)
        return frozenset(set.intersection(*sets)) if sets else frozenset()

    def essential(b):
        ps = prereqs[b]
        return [p for p in ps if not any(p in strong_ancestors(q) for q in ps if q != p)]

    course_of = {}
    for c in sorted(course_ids):
        for m in members[c]:
            course_of.setdefault(m, c)

    edges = []
    for c in sorted(course_ids):
        for p in course_prereqs(c):
            needers = [m for m in primaries(c) if p in prereqs[m]]
            ess = [m for m in needers if p in essential(m)]
            if not ess:
                continue  # implied by another prereq; don't draw
            edges.append({
                "s": p, "t": c,
                "all": len(needers) == len(primaries(c)),
                "books": ess,
            })

    area_order = [a for a, _ in AREAS]
    area_list = [{"id": a, "label": label} for a, label in AREAS if a in areas.values()]
    for a in sorted(set(areas.values()) - set(area_order)):
        area_list.append({"id": a, "label": a.replace("-", " ").capitalize()})

    data = {
        "areas": area_list,
        "goals": goals,
        "courses": [{
            "id": c,
            "label": title_of(COURSES / f"{c}.md"),
            "area": areas[c],
            "layer": layer(c),
            "status": course_status(c),
            "members": members[c],
            "focus": c in focus,
            "mathlib": fm[c].get("mathlib", ""),
            "goal": c in goals,
            "notes": notes_of(COURSES / f"{c}.md"),
        } for c in sorted(course_ids)],
        "books": {b: {
            "label": title_of(BOOKS / f"{b}.md"),
            "status": bstatus[b],
            "covered": bstatus[b] != "finished" and course_of.get(b) in satisfied,
            "skimmed": b in skimmed_details,
            "companion": b in companion,
            "tradition": bfm[b].get("tradition", ""),
            "problems": bfm[b].get("format") == "problems",
            "medium": bfm[b].get("medium", "book"),
            "url": bfm[b].get("url", ""),
            "course": course_of.get(b),
            "prereqs": prereqs[b],
            "detail": finished_details.get(b) or reading_details.get(b) or skimmed_details.get(b) or "",
            "notes": notes_of(BOOKS / f"{b}.md"),
        } for b in sorted(book_ids)},
        "finished": list(finished_details),
        "reading": list(reading_details),
        "skimmed": list(skimmed_details),
        "edges": edges,
    }

    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    OUT.write_text(HTML.replace("__DATA__", data_json))
    print(f"wrote {OUT.relative_to(ROOT)} — {len(course_ids)} courses, {len(book_ids)} books, {len(edges)} edges")


HTML = (Path(__file__).resolve().parent / "graph_template.html").read_text()


if __name__ == "__main__":
    main()
