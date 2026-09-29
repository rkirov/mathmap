# mathmap

Personal log of math books and prerequisites. Read and edited in
Obsidian; reasoned over with an LLM.

## Files

- `books/<id>.md` — one per book. Sections: `## Prerequisites` (wikilinks to books or courses), `## Notes`.
- `courses/<id>.md` — one per topic that multiple books can cover. Frontmatter `area:` (subject swimlane in the graph, e.g. `algebra`, `analysis`; see `AREAS` in `scripts/graph.py`). Optional `mathlib:` (`strong` / `partial` / `thin`) — rough guess at how much Mathlib already covers, since exercises go into Lean. Sections: `## Members` (wikilinks to books), `## Notes`.
- `status.md` — source of truth for lifecycle: `## Finished`, `## Reading` (rigorous: cover to cover, all exercises), `## Skimmed` (companion reading, no exercises; never satisfies a prerequisite). Wikilinks to books only; text after the link is free-form notes shown in the graph.
- `preferences.md` — taste, focus, long-term direction. Courses linked under `## Current focus` get a *focus* badge; courses linked under `## Long-term direction` are goals, and the graph shows the shortest remaining route to each.

Cross-references are Obsidian wikilinks `[[kebab-id]]`. Filenames are kebab-case.

A book's prereqs point only to courses, never directly to books. The
course is the stable naming layer: if a downstream book depended on a
specific book, swapping in a better book later would require editing
every dependent. Even when a course has only one member, downstream
depends on the course. `validate.py` enforces this.

Books may carry frontmatter: `role: companion` (skim alongside a
primary; ignored for layout, routes, and edges), `format: problems`
(theory built through problems), `tradition: russian` / `hungarian`
(school of presentation; searchable in the graph), `medium: notes` /
`video` with a `url:` for lecture notes and video series (default is a
book; `url:` is also fine on free books).

## Scripts

- `scripts/validate.py` — checks invariants (resolved wikilinks, acyclic graph, books have `## Prerequisites`, courses have `## Members` with only books, status only references books, filenames kebab-case). Exits nonzero on failure.
- `scripts/log.py` — prints derived state: Finished, Reading, Open (all prereqs satisfied), Horizon (with unmet prereqs listed).
- `scripts/graph.py` — regenerates `graph.html` from the markdown (template: `scripts/graph_template.html`). Rows are subject areas, columns are the earliest stage at which some book in the course becomes readable. Edges go to the whole course card when every member needs the prereq, or to the specific book row otherwise; transitively implied edges are not drawn. Run it after editing any file.

Book prereqs are satisfied only when the book is in `status.md` `##
Finished`. Course prereqs are satisfied when at least one member book
is finished.
