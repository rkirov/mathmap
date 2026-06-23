#!/usr/bin/env python3
"""Dump Finished / Reading / Open / Horizon, computed from the graph."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "books"
COURSES = ROOT / "courses"
STATUS = ROOT / "status.md"

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?(?:#[^\]]+)?\]\]")


def read(path):
    return path.read_text() if path.exists() else ""


def section(text, heading):
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
    if not m:
        return []
    rest = text[m.end():]
    nxt = re.search(r"^##\s", rest, re.MULTILINE)
    block = rest[: nxt.start()] if nxt else rest
    return [ln for ln in block.splitlines() if ln.lstrip().startswith("-")]


def links(lines):
    out = []
    for ln in lines:
        out.extend(WIKILINK.findall(ln))
    return out


def main():
    book_ids = {p.stem for p in BOOKS.glob("*.md")}
    course_ids = {p.stem for p in COURSES.glob("*.md")}

    prereqs = {p.stem: links(section(read(p), "Prerequisites")) for p in BOOKS.glob("*.md")}
    members = {p.stem: links(section(read(p), "Members")) for p in COURSES.glob("*.md")}

    status = read(STATUS)
    finished = set(links(section(status, "Finished")))
    reading_ordered = links(section(status, "Reading"))
    reading = set(reading_ordered)

    def satisfied(ref):
        if ref in book_ids:
            return ref in finished
        if ref in course_ids:
            return any(m in finished for m in members.get(ref, []))
        return False

    def available(book):
        return all(satisfied(r) for r in prereqs.get(book, []))

    finished_ordered = links(section(status, "Finished"))
    open_books = sorted(
        b for b in book_ids
        if b not in finished and b not in reading and available(b)
    )
    horizon_books = sorted(
        b for b in book_ids
        if b not in finished and b not in reading and not available(b)
    )

    book_to_courses = {b: [] for b in book_ids}
    for c, mems in members.items():
        for b in mems:
            if b in book_to_courses:
                book_to_courses[b].append(c)

    def dump(title, items, unmet=False):
        print(f"## {title}")
        if not items:
            print("(none)")
        else:
            for b in items:
                if unmet:
                    missing = [r for r in prereqs.get(b, []) if not satisfied(r)]
                    suffix = f" — needs {', '.join(f'[[{m}]]' for m in missing)}" if missing else ""
                    print(f"- [[{b}]]{suffix}")
                else:
                    print(f"- [[{b}]]")
        print()

    def dump_open(items):
        print("## Open")
        if not items:
            print("(none)")
            print()
            return
        course_to_books = {}
        orphans = []
        for b in items:
            cs = book_to_courses.get(b, [])
            if cs:
                for c in cs:
                    course_to_books.setdefault(c, []).append(b)
            else:
                orphans.append(b)
        for c in sorted(course_to_books):
            bs = sorted(course_to_books[c])
            print(f"- [[{c}]]: " + ", ".join(f"[[{b}]]" for b in bs))
        for b in sorted(orphans):
            print(f"- [[{b}]]")
        print()

    dump("Finished", finished_ordered)
    dump("Reading", reading_ordered)
    dump_open(open_books)
    dump("Horizon", horizon_books, unmet=True)


if __name__ == "__main__":
    main()
