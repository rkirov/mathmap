# mathmap

Personal log of math books and prerequisites. Read and edited in
Obsidian; reasoned over with an LLM.

## Files

- `books/<id>.md` — one per book. Sections: `## Prerequisites` (wikilinks to books or courses), `## Notes`.
- `courses/<id>.md` — one per topic that multiple books can cover. Sections: `## Members` (wikilinks to books), `## Notes`.
- `status.md` — source of truth for lifecycle: `## Finished`, `## Reading`. Wikilinks to books only.
- `preferences.md` — taste, focus, long-term direction.

Cross-references are Obsidian wikilinks `[[kebab-id]]`. Filenames are kebab-case.

A book's prereqs point only to courses, never directly to books. The
course is the stable naming layer: if a downstream book depended on a
specific book, swapping in a better book later would require editing
every dependent. Even when a course has only one member, downstream
depends on the course. `validate.py` enforces this.

## Scripts

- `scripts/validate.py` — checks invariants (resolved wikilinks, acyclic graph, books have `## Prerequisites`, courses have `## Members` with only books, status only references books, filenames kebab-case). Exits nonzero on failure.
- `scripts/log.py` — prints derived state: Finished, Reading, Open (all prereqs satisfied), Horizon (with unmet prereqs listed).

Book prereqs are satisfied only when the book is in `status.md` `##
Finished`. Course prereqs are satisfied when at least one member book
is finished.
