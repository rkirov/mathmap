#!/usr/bin/env python3
"""Generate graph.html — interactive hierarchical visualization."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "books"
COURSES = ROOT / "courses"
STATUS = ROOT / "status.md"
OUT = ROOT / "graph.html"

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?(?:#[^\]]+)?\]\]")


def read(p):
    return p.read_text() if p.exists() else ""


def section(text, heading):
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
    if not m:
        return []
    rest = text[m.end():]
    nxt = re.search(r"^##\s", rest, re.MULTILINE)
    block = rest[: nxt.start()] if nxt else rest
    return [ln for ln in block.splitlines() if ln.lstrip().startswith("-")]


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
    text = read(p)
    m = re.search(r"^##\s+Notes\s*$", text, re.MULTILINE)
    if not m:
        return ""
    body = text[m.end():]
    nxt = re.search(r"^##\s", body, re.MULTILINE)
    return (body[: nxt.start()] if nxt else body).strip()


def main():
    book_files = sorted(BOOKS.glob("*.md"))
    course_files = sorted(COURSES.glob("*.md"))
    book_ids = {p.stem for p in book_files}
    course_ids = {p.stem for p in course_files}

    prereqs = {p.stem: links_in(section(read(p), "Prerequisites")) for p in book_files}
    members = {p.stem: links_in(section(read(p), "Members")) for p in course_files}

    status_text = read(STATUS)
    finished = set(links_in(section(status_text, "Finished")))
    reading = set(links_in(section(status_text, "Reading")))

    def satisfied(ref):
        if ref in book_ids:
            return ref in finished
        if ref in course_ids:
            return any(m in finished for m in members.get(ref, []))
        return False

    def book_status(b):
        if b in finished:
            return "finished"
        if b in reading:
            return "reading"
        if all(satisfied(r) for r in prereqs.get(b, [])):
            return "open"
        return "horizon"

    def course_status(c):
        mems = members.get(c, [])
        if any(m in finished for m in mems):
            return "satisfied"
        if any(book_status(m) == "open" for m in mems):
            return "open"
        return "locked"

    def book_covered(b):
        if b in finished:
            return False
        for c in course_ids:
            if b in members.get(c, []):
                if any(m != b and m in finished for m in members.get(c, [])):
                    return True
        return False

    depth_cache = {}

    def book_depth(b):
        k = ("b", b)
        if k in depth_cache:
            return depth_cache[k]
        depth_cache[k] = 0  # cycle guard
        prs = [c for c in prereqs.get(b, []) if c in course_ids]
        d = 0 if not prs else 1 + max(course_depth(c) for c in prs)
        depth_cache[k] = d
        return d

    def course_depth(c):
        k = ("c", c)
        if k in depth_cache:
            return depth_cache[k]
        depth_cache[k] = 0  # cycle guard
        mems = [m for m in members.get(c, []) if m in book_ids]
        d = 0 if not mems else 1 + min(book_depth(m) for m in mems)
        depth_cache[k] = d
        return d

    def strong_course_prereqs(c):
        mems = [m for m in members.get(c, []) if m in book_ids]
        if not mems:
            return set()
        sets = [set(p for p in prereqs.get(m, []) if p in course_ids) for m in mems]
        return set.intersection(*sets)

    # Each book belongs to at most one "home" course (first course listing it as member).
    book_parent = {}
    for c in sorted(course_ids):
        for m in members.get(c, []):
            if m in book_ids and m not in book_parent:
                book_parent[m] = c

    nodes = []
    for p in course_files:
        nodes.append({"data": {
            "id": p.stem,
            "label": title_of(p),
            "type": "course",
            "status": course_status(p.stem),
            "depth": course_depth(p.stem),
            "notes": notes_of(p),
        }})
    for p in book_files:
        d = {
            "id": p.stem,
            "label": title_of(p),
            "type": "book",
            "status": book_status(p.stem),
            "covered": book_covered(p.stem),
            "depth": book_depth(p.stem),
            "notes": notes_of(p),
        }
        if p.stem in book_parent:
            d["parent"] = book_parent[p.stem]
        nodes.append({"data": d})

    edges = []
    # Course-level strong prereqs: edge iff every member of target needs source
    for c in sorted(course_ids):
        for src in sorted(strong_course_prereqs(c)):
            edges.append({"data": {"id": f"cp:{src}->{c}", "source": src, "target": c, "kind": "course-prereq"}})
    # Book-level prereqs (hidden by default, surfaced on click)
    for book, prs in prereqs.items():
        for pr in prs:
            edges.append({"data": {"id": f"bp:{pr}->{book}", "source": pr, "target": book, "kind": "book-prereq"}})

    data_json = json.dumps({"nodes": nodes, "edges": edges}).replace("</", "<\\/")
    OUT.write_text(HTML.replace("__DATA__", data_json))
    print(f"wrote {OUT.relative_to(ROOT)} — {len(nodes)} nodes, {len(edges)} edges")


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>mathmap</title>
<style>
  html, body { margin: 0; padding: 0; height: 100%; font-family: system-ui, -apple-system, sans-serif; }
  #cy { position: absolute; top: 0; left: 0; right: 340px; bottom: 0; background: #fafafa; }
  #panel { position: absolute; top: 0; right: 0; width: 340px; bottom: 0; padding: 20px; box-sizing: border-box; overflow-y: auto; background: #fff; border-left: 1px solid #e5e7eb; }
  #panel h2 { margin: 0 0 4px 0; font-size: 16px; line-height: 1.3; }
  #panel .meta { color: #6b7280; font-size: 12px; margin-bottom: 14px; text-transform: uppercase; letter-spacing: 0.04em; }
  #panel .row { margin: 10px 0; font-size: 13px; }
  #panel .row b { color: #374151; display: block; margin-bottom: 4px; font-weight: 600; }
  #panel a.chip { display: inline-block; margin: 2px 4px 2px 0; padding: 3px 8px; background: #f3f4f6; border-radius: 3px; cursor: pointer; color: #111827; text-decoration: none; font-size: 12px; }
  #panel a.chip:hover { background: #e5e7eb; }
  #panel .notes { font-size: 13px; line-height: 1.55; color: #374151; margin-top: 14px; white-space: pre-wrap; }
  #search { position: absolute; top: 12px; left: 12px; padding: 7px 10px; font-size: 13px; border: 1px solid #d1d5db; border-radius: 4px; width: 220px; background: #fff; z-index: 10; }
  .legend { position: absolute; bottom: 12px; left: 12px; background: #fff; padding: 10px 12px; border: 1px solid #e5e7eb; border-radius: 4px; font-size: 12px; line-height: 1.8; z-index: 10; }
  .legend .item { display: flex; align-items: center; }
  .legend .sw { display: inline-block; width: 18px; height: 12px; margin-right: 8px; border: 1.5px solid #374151; border-radius: 2px; }
  .legend .dash { border-style: dashed; background: #fff; }
</style>
</head>
<body>
<div id="cy"></div>
<input id="search" placeholder="Search books / courses…">
<div id="panel">
  <h2>mathmap</h2>
  <div class="meta">click a node</div>
  <div class="row">Flow is left→right. Courses are dashed boxes enclosing their member books. Solid arrows show prereq dependencies. Click a node to highlight ancestors (what to finish first) and descendants (what it unlocks).</div>
  <div class="row" style="color:#6b7280;font-size:12px"><b>Keys:</b> ← → navigate prereq chain · ↑ ↓ same column · <code>/</code> search · <code>Esc</code> reset</div>
</div>
<div class="legend">
  <div class="item"><span class="sw" style="background:#86efac"></span>Finished</div>
  <div class="item"><span class="sw" style="background:#fcd34d"></span>Reading</div>
  <div class="item"><span class="sw" style="background:#93c5fd"></span>Open</div>
  <div class="item"><span class="sw" style="background:#d1d5db"></span>Horizon</div>
  <div class="item"><span class="sw dash" style="border-color:#22c55e"></span>Course (satisfied)</div>
  <div class="item"><span class="sw dash" style="border-color:#3b82f6"></span>Course (open)</div>
  <div class="item"><span class="sw dash" style="border-color:#6b7280"></span>Course (locked)</div>
  <div class="item"><span class="sw" style="background:#93c5fd; opacity:0.35; border-style:dotted"></span>Book (covered)</div>
</div>
<script src="https://cdn.jsdelivr.net/npm/cytoscape@3.30.2/dist/cytoscape.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/elkjs@0.9.3/lib/elk.bundled.js"></script>
<script src="https://cdn.jsdelivr.net/npm/cytoscape-elk@2.2.0/dist/cytoscape-elk.js"></script>
<script>
const DATA = __DATA__;

const statusFill = { finished:'#86efac', reading:'#fcd34d', open:'#93c5fd', horizon:'#d1d5db' };

const cy = cytoscape({
  container: document.getElementById('cy'),
  elements: DATA,
  wheelSensitivity: 0.2,
  autoungrabify: true,
  boxSelectionEnabled: false,
  style: [
    { selector: 'node', style: {
        'label': 'data(label)',
        'text-wrap': 'wrap', 'text-max-width': 150,
        'text-valign': 'center', 'text-halign': 'center',
        'font-size': 10.5, 'font-family': 'system-ui, sans-serif',
        'color': '#111827',
        'width': 170, 'height': 54,
        'border-width': 1.5, 'border-color': '#1f2937',
      }},
    { selector: 'node[type="book"]', style: {
        'shape': 'rectangle',
        'background-color': ele => statusFill[ele.data('status')] || '#d1d5db',
        'background-opacity': 0.95,
        'border-width': 1.5,
      }},
    { selector: 'node[type="book"][?covered]', style: {
        'background-opacity': 0.35,
        'border-style': 'dotted',
        'border-color': '#6b7280',
        'color': '#6b7280',
      }},
    { selector: 'node[type="course"]', style: {
        'shape': 'round-rectangle',
        'background-opacity': 0.6,
        'border-style': 'dashed', 'border-width': 2,
        'font-style': 'italic',
        'font-weight': 600,
        'font-size': 16,
        'color': '#1f2937',
        'text-valign': 'top',
        'text-halign': 'center',
        'text-margin-y': 4,
        'padding': '32px',
        'compound-sizing-wrt-labels': 'include',
        'min-width': 200,
      }},
    { selector: 'node[type="course"][status="satisfied"]', style: {
        'background-color': '#dcfce7',
        'border-color': '#22c55e',
      }},
    { selector: 'node[type="course"][status="open"]', style: {
        'background-color': '#dbeafe',
        'border-color': '#3b82f6',
      }},
    { selector: 'node[type="course"][status="locked"]', style: {
        'background-color': '#f9fafb',
        'border-color': '#6b7280',
      }},
    { selector: 'edge', style: {
        'curve-style': 'taxi',
        'taxi-direction': 'horizontal',
        'taxi-turn': '30px',
        'taxi-turn-min-distance': '10px',
        'width': 1.2,
        'line-color': '#9ca3af',
        'target-arrow-color': '#9ca3af',
      }},
    { selector: 'edge[kind="course-prereq"]', style: {
        'target-arrow-shape': 'triangle',
        'arrow-scale': 1.2,
        'line-color': '#334155',
        'target-arrow-color': '#334155',
        'width': 1.7,
      }},
    { selector: 'edge[kind="book-prereq"]', style: {
        'line-style': 'dashed',
        'line-color': '#94a3b8',
        'target-arrow-color': '#94a3b8',
        'target-arrow-shape': 'triangle',
        'arrow-scale': 0.9,
        'width': 1,
        'opacity': 0,
        'events': 'no',
      }},
    { selector: 'edge[kind="book-prereq"].revealed', style: {
        'opacity': 1,
        'events': 'yes',
      }},
    { selector: '.faded', style: { 'opacity': 0.15 } },
    { selector: '.focus', style: { 'border-width': 3, 'border-color': '#dc2626' } },
  ],
  layout: {
    name: 'elk',
    fit: false,
    elk: {
      algorithm: 'layered',
      'elk.direction': 'RIGHT',
      'elk.edgeRouting': 'ORTHOGONAL',
      'elk.spacing.nodeNode': 18,
      'elk.layered.spacing.nodeNodeBetweenLayers': 80,
      'elk.layered.spacing.edgeNodeBetweenLayers': 24,
      'elk.padding': '[top=34,left=22,bottom=22,right=22]',
      'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
      'elk.layered.layering.strategy': 'COFFMAN_GRAHAM',
      'elk.layered.layering.coffmanGraham.layerBound': 5,
      'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
      'elk.layered.nodePlacement.strategy': 'NETWORK_SIMPLEX',
      'elk.layered.nodePlacement.favorStraightEdges': 'true',
      'elk.aspectRatio': 2.5,
    },
    stop: () => {
      // snap course compound centers to a regular column grid so they line up visually
      const courses = cy.nodes('[type="course"]').toArray();
      const uniqX = [...new Set(courses.map(c => Math.round(c.position('x'))))].sort((a, b) => a - b);
      const colGap = 320;
      const colMap = new Map(uniqX.map((x, i) => [x, i * colGap]));
      courses.forEach(c => {
        const oldX = Math.round(c.position('x'));
        const newX = colMap.get(oldX);
        if (newX !== undefined && newX !== oldX) {
          const dx = newX - c.position('x');
          c.shift({ x: dx, y: 0 });  // moves compound + children together
        }
      });
      cy.zoom(1.2);
      const leftmost = cy.nodes().toArray().sort((a, b) => a.position('x') - b.position('x'))[0];
      if (leftmost) {
        const w = cy.width(), h = cy.height();
        cy.pan({ x: w * 0.15 - leftmost.position('x') * 1.2, y: h / 2 - leftmost.position('y') * 1.2 });
      }
    },
  },
});

const panel = document.getElementById('panel');
const DEFAULT_PANEL = panel.innerHTML;

function renderChips(nodes) {
  return [...nodes].map(n => `<a class="chip" data-id="${n.id()}">${n.data('label')}</a>`).join('');
}

function showPanel(id) {
  const n = cy.$id(id);
  if (!n.length) return;
  const d = n.data();
  let html = `<h2>${d.label}</h2><div class="meta">${d.type} · ${d.status}</div>`;
  if (d.type === 'book') {
    const prereqs = n.incomers('edge[kind="prereq"]').sources();
    const courses = n.outgoers('edge[kind="member"]').targets();
    if (prereqs.length) html += `<div class="row"><b>Prerequisites</b>${renderChips(prereqs)}</div>`;
    if (courses.length) html += `<div class="row"><b>In course</b>${renderChips(courses)}</div>`;
  } else {
    const mems = n.incomers('edge[kind="member"]').sources();
    const feeds = n.outgoers('edge[kind="prereq"]').targets();
    if (mems.length) html += `<div class="row"><b>Members</b>${renderChips(mems)}</div>`;
    if (feeds.length) html += `<div class="row"><b>Unlocks</b>${renderChips(feeds)}</div>`;
  }
  if (d.notes) html += `<div class="notes">${d.notes}</div>`;
  panel.innerHTML = html;
  panel.querySelectorAll('a.chip').forEach(a => {
    a.addEventListener('click', () => selectNode(a.dataset.id));
  });
}

function revealCourseBookEdges(course) {
  // Books are always visible; reveal their book-level prereq edges on demand.
  course.children().forEach(k => {
    k.connectedEdges('edge[kind="book-prereq"]').addClass('revealed');
  });
}

function collapseAll() {
  cy.elements().removeClass('revealed faded focus');
  panel.innerHTML = DEFAULT_PANEL;
}

function visibleElements() {
  // Everything except hidden book-prereq edges.
  return cy.nodes().union(cy.edges('[kind="course-prereq"]')).union(cy.$('.revealed'));
}

function selectNode(id) {
  const n = cy.$id(id);
  if (!n.length) return;
  cy.elements().removeClass('faded focus');
  if (n.data('type') === 'course') {
    revealCourseBookEdges(n);
    const chain = n.predecessors('node, edge[kind="course-prereq"]')
      .union(n.successors('node, edge[kind="course-prereq"]'))
      .union(n).union(n.children());
    visibleElements().difference(chain).addClass('faded');
    n.addClass('focus');
  } else {
    const chain = n.predecessors().union(n).union(n.successors()).union(n.parent());
    // reveal every book-prereq edge along the chain, not just direct ones
    chain.filter('edge[kind="book-prereq"]').addClass('revealed');
    visibleElements().difference(chain).addClass('faded');
    n.addClass('focus');
  }
  showPanel(id);
  cy.animate({ center: { eles: n }, duration: 200 });
}

cy.on('tap', 'node', e => selectNode(e.target.id()));
cy.on('tap', e => {
  if (e.target === cy) collapseAll();
});

function currentFocus() {
  return cy.nodes('.focus')[0] || null;
}

function nearestIn(candidates, from) {
  let best = null, bestD = Infinity;
  candidates.forEach(n => {
    const dx = n.position('x') - from.position('x');
    const dy = n.position('y') - from.position('y');
    const d = dx*dx + dy*dy;
    if (d < bestD) { bestD = d; best = n; }
  });
  return best;
}

function keyNav(dir) {
  let sel = currentFocus();
  if (!sel) {
    // start at the leftmost course
    const courses = cy.nodes('[type="course"]');
    if (!courses.length) return;
    sel = courses.toArray().sort((a, b) => a.position('x') - b.position('x'))[0];
    selectNode(sel.id());
    return;
  }
  const pos = sel.position();
  let candidates = [];

  if (dir === 'right' || dir === 'left') {
    // prefer direct graph neighbors via prereq edges
    const edgeKind = sel.data('type') === 'course' ? 'edge[kind="course-prereq"]' : 'edge[kind="book-prereq"]';
    const neigh = dir === 'right' ? sel.outgoers(edgeKind).targets() : sel.incomers(edgeKind).sources();
    candidates = neigh.toArray();
    if (!candidates.length) {
      // fall back to any same-type node to the side
      const sameType = cy.nodes(`[type="${sel.data('type')}"]`);
      candidates = sameType.toArray().filter(n => n.id() !== sel.id() && (dir === 'right' ? n.position('x') > pos.x + 10 : n.position('x') < pos.x - 10));
    }
  } else {
    // up/down: same column, nearest vertically
    const sameCol = cy.nodes().toArray().filter(n => n.id() !== sel.id() && Math.abs(n.position('x') - pos.x) < 100);
    candidates = sameCol.filter(n => dir === 'up' ? n.position('y') < pos.y - 10 : n.position('y') > pos.y + 10);
  }

  if (!candidates.length) return;
  const best = nearestIn(candidates, sel);
  if (best) selectNode(best.id());
}

document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
    if (e.key === 'Escape') { e.target.blur(); e.target.value = ''; e.target.dispatchEvent(new Event('input')); }
    return;
  }
  switch (e.key) {
    case 'ArrowRight': keyNav('right'); e.preventDefault(); break;
    case 'ArrowLeft':  keyNav('left');  e.preventDefault(); break;
    case 'ArrowUp':    keyNav('up');    e.preventDefault(); break;
    case 'ArrowDown':  keyNav('down');  e.preventDefault(); break;
    case 'Escape':     collapseAll();   break;
    case '/':          document.getElementById('search').focus(); e.preventDefault(); break;
  }
});

document.getElementById('search').addEventListener('input', e => {
  const q = e.target.value.trim().toLowerCase();
  if (!q) { cy.elements().removeClass('faded'); return; }
  cy.elements().addClass('faded');
  const matches = cy.nodes().filter(n =>
    n.data('label').toLowerCase().includes(q) || n.id().toLowerCase().includes(q));
  matches.removeClass('faded');
  matches.forEach(n => n.connectedEdges().connectedNodes().removeClass('faded'));
});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
