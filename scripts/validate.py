#!/usr/bin/env python3
"""Validate the mathmap graph. Prints errors to stderr; exits 1 on any."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "books"
COURSES = ROOT / "courses"
STATUS = ROOT / "status.md"

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?(?:#[^\]]+)?\]\]")
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def read(path):
    return path.read_text() if path.exists() else ""


def section(text, heading):
    """Return bullet lines under `## <heading>`, or None if no such heading."""
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^##\s", rest, re.MULTILINE)
    block = rest[: nxt.start()] if nxt else rest
    return [ln.lstrip("- ").rstrip() for ln in block.splitlines() if ln.lstrip().startswith("-")]


def links(items):
    out = []
    for line in items or []:
        out.extend(WIKILINK.findall(line))
    return out


def main():
    errs = []
    book_files = sorted(BOOKS.glob("*.md"))
    course_files = sorted(COURSES.glob("*.md"))
    book_ids = {p.stem for p in book_files}
    course_ids = {p.stem for p in course_files}
    all_ids = book_ids | course_ids

    for p in book_files + course_files:
        if not KEBAB.match(p.stem):
            errs.append(f"non-kebab filename: {p.relative_to(ROOT)}")

    prereqs = {}
    for p in book_files:
        rel = p.relative_to(ROOT)
        text = read(p)
        pr = section(text, "Prerequisites")
        if pr is None:
            errs.append(f"{rel}: missing ## Prerequisites")
            pr = []
        if section(text, "Members") is not None:
            errs.append(f"{rel}: book has ## Members")
        refs = links(pr)
        prereqs[p.stem] = refs
        for r in refs:
            if r not in all_ids:
                errs.append(f"{rel}: unresolved [[{r}]]")
            elif r in book_ids:
                errs.append(f"{rel}: book prereq must be a course, got book [[{r}]]")

    members = {}
    for p in course_files:
        rel = p.relative_to(ROOT)
        text = read(p)
        mb = section(text, "Members")
        if mb is None:
            errs.append(f"{rel}: missing ## Members")
            mb = []
        if section(text, "Prerequisites") is not None:
            errs.append(f"{rel}: course has ## Prerequisites")
        refs = links(mb)
        members[p.stem] = refs
        if not refs:
            errs.append(f"{rel}: course has no members")
        for r in refs:
            if r not in all_ids:
                errs.append(f"{rel}: unresolved [[{r}]]")
            elif r in course_ids:
                errs.append(f"{rel}: course references course [[{r}]]")

    status_text = read(STATUS)
    if status_text:
        for heading in ("Finished", "Reading"):
            for r in links(section(status_text, heading)):
                if r not in book_ids:
                    errs.append(f"status.md: ## {heading} references non-book [[{r}]]")

    graph = {**prereqs, **members}
    color = {n: 0 for n in graph}  # 0=white 1=gray 2=black

    def dfs(node, path):
        color[node] = 1
        for dep in graph.get(node, ()):
            if dep not in color:
                continue  # unresolved link, already flagged
            if color[dep] == 1:
                cyc = path[path.index(dep):] + [dep]
                errs.append("cycle: " + " -> ".join(cyc))
                return
            if color[dep] == 0:
                dfs(dep, path + [dep])
        color[node] = 2

    for n in list(graph):
        if color[n] == 0:
            dfs(n, [n])

    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        sys.exit(1)
    print(f"ok — {len(book_ids)} books, {len(course_ids)} courses")


if __name__ == "__main__":
    main()
