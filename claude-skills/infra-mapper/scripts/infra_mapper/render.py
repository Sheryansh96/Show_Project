"""Renders a parsed infra model into a single self-contained HTML file."""
import json

from .text_utils import esc

PAGE_STYLE = """
body{margin:0;padding:32px;background:#0d1117;color:#c9d1d9;font-family:-apple-system,Helvetica,Arial,sans-serif;}
h1{font-size:18px;margin:0 0 4px;}
.col-hd{font-size:13px;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;margin:0 0 16px;padding-bottom:8px;border-bottom:2px solid #21262d;display:flex;align-items:center;gap:8px;}
.col-hd .num{background:#21262d;color:#c9d1d9;border-radius:50%;width:18px;height:18px;display:inline-flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;}
.sub-hd{font-size:10px;color:#6e7681;text-transform:uppercase;letter-spacing:.04em;margin:18px 0 10px;}
.sub-hd:first-of-type{margin-top:0;}
.sub{color:#6e7681;font-size:12px;margin-bottom:24px;max-width:900px;}
.layout{display:grid;grid-template-columns:260px 1fr 260px;gap:56px;align-items:start;}
.col{min-width:0;}
.cluster{border:1px solid #30363d;border-radius:10px;padding:16px;margin-bottom:16px;background:#0f1520;}
.cluster-hd{font-size:14px;font-weight:700;color:#58a6ff;margin-bottom:12px;}
.stack{display:flex;flex-direction:column;gap:12px;}
.service{border:1px solid #30363d;border-radius:8px;padding:12px;background:#161b22;width:100%;box-sizing:border-box;}
.card{border:1px solid #30363d;border-radius:8px;padding:12px;background:#161b22;width:100%;box-sizing:border-box;margin-bottom:12px;}
.service-hd,.card-hd{font-weight:600;font-size:13px;margin-bottom:2px;}
.service-meta,.card-meta{color:#6e7681;font-size:11px;margin-bottom:8px;}
.taskdef-tag{color:#8b949e;font-size:10px;text-transform:uppercase;letter-spacing:.04em;margin:8px 0 6px;}
.container{border:1px solid #21262d;border-left:3px solid #58a6ff;border-radius:6px;padding:8px 10px;margin-bottom:8px;background:#0d1117;}
.container.sidecar{border-left-color:#f0883e;}
.container-name{font-weight:600;font-size:12.5px;}
.container-image{color:#6e7681;font-size:11px;font-family:ui-monospace,monospace;margin:2px 0 6px;}
.desc{font-size:12px;color:#c9d1d9;line-height:1.4;}
.desc.warn{color:#f0883e;}
.chips{margin-top:6px;display:flex;flex-wrap:wrap;gap:4px;}
.chip{background:#21262d;border-radius:10px;padding:1px 8px;font-size:10px;color:#8b949e;}
.chip.dep{background:#132436;color:#58a6ff;}
.deps{margin-top:8px;font-size:11px;color:#8b949e;}
.deps-label{color:#6e7681;margin-right:4px;}
.src{font-size:10px;color:#484f58;margin-top:4px;}
.unassigned{border:1px dashed #f0883e;border-radius:8px;padding:12px;color:#f0883e;font-size:12px;margin-top:24px;}
.badge{display:inline-block;background:#1f6feb33;color:#58a6ff;border-radius:4px;padding:1px 6px;font-size:10px;margin-left:6px;}
.badge.data{background:#3fb95033;color:#3fb950;}
"""

CONNECTOR_STYLE = """
#connectors{position:absolute;top:0;left:0;pointer-events:none;z-index:1;}
body{position:relative;}
.card,.service,.container,.cluster{position:relative;z-index:2;}
#legend{position:fixed;bottom:14px;left:14px;background:rgba(22,27,34,.95);border:1px solid #30363d;border-radius:8px;padding:10px 14px;font-size:11px;color:#8b949e;z-index:10;line-height:1.9;}
.lg-hd{color:#c9d1d9;font-weight:600;margin-bottom:4px;}
.ln{display:inline-block;width:22px;height:0;border-top:2px solid;margin-right:6px;vertical-align:middle;}
.ln.blue{border-color:#58a6ff;}
.ln.teal{border-color:#3fb9a8;}
.ln.orange{border-color:#f0883e;}
.ln.dashed{border-top-style:dashed;}
.card.hi,.service.hi,.container.hi{outline:2px solid #f0883e;}
#tooltip{position:fixed;pointer-events:none;background:#161b22;border:1px solid #30363d;padding:6px 10px;border-radius:6px;font-size:12px;display:none;z-index:20;}
"""

CONNECTOR_SCRIPT = """
function colorFor(via) {
  if (via.startsWith('env:')) return {stroke:'#3fb9a8', dash:'5,4'};
  if (via.startsWith('grant')) return {stroke:'#58a6ff', dash:'none'};
  return {stroke:'#f0883e', dash:'none'};
}

function drawConnectors() {
  const svg = document.getElementById('connectors');
  const docW = Math.max(document.body.scrollWidth, document.documentElement.scrollWidth);
  const docH = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
  svg.setAttribute('width', docW);
  svg.setAttribute('height', docH);
  svg.setAttribute('viewBox', `0 0 ${docW} ${docH}`);
  svg.innerHTML = '';

  const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
  ['blue','teal','orange'].forEach(name => {
    const color = name === 'blue' ? '#58a6ff' : name === 'teal' ? '#3fb9a8' : '#f0883e';
    const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
    marker.setAttribute('id', 'arrow-' + name);
    marker.setAttribute('viewBox', '0 0 10 10');
    marker.setAttribute('refX', '8'); marker.setAttribute('refY', '5');
    marker.setAttribute('markerWidth', '6'); marker.setAttribute('markerHeight', '6');
    marker.setAttribute('orient', 'auto-start-reverse');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M0,0 L10,5 L0,10 z');
    path.setAttribute('fill', color);
    marker.appendChild(path);
    defs.appendChild(marker);
  });
  svg.appendChild(defs);

  EDGES.forEach(e => {
    const a = document.getElementById(e.from);
    const b = document.getElementById(e.to);
    if (!a || !b) return;
    const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    const scrollX = window.scrollX, scrollY = window.scrollY;
    let ax, ay, bx, by;
    if (ra.left <= rb.left) {
      ax = ra.right + scrollX; ay = ra.top + ra.height/2 + scrollY;
      bx = rb.left + scrollX; by = rb.top + rb.height/2 + scrollY;
    } else {
      ax = ra.left + scrollX; ay = ra.top + ra.height/2 + scrollY;
      bx = rb.right + scrollX; by = rb.top + rb.height/2 + scrollY;
    }
    const {stroke, dash} = colorFor(e.via);
    const colorName = stroke === '#58a6ff' ? 'blue' : stroke === '#3fb9a8' ? 'teal' : 'orange';

    const midX = (ax + bx) / 2;
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M${ax},${ay} C${midX},${ay} ${midX},${by} ${bx},${by}`);
    path.setAttribute('stroke', stroke);
    path.setAttribute('stroke-width', '1.6');
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke-opacity', '0.55');
    if (dash !== 'none') path.setAttribute('stroke-dasharray', dash);
    path.setAttribute('marker-end', `url(#arrow-${colorName})`);
    path.dataset.from = e.from; path.dataset.to = e.to;
    path.style.pointerEvents = 'stroke';
    path.style.cursor = 'pointer';

    const tooltip = document.getElementById('tooltip');
    path.addEventListener('mouseenter', (ev) => {
      path.setAttribute('stroke-width', '3'); path.setAttribute('stroke-opacity', '1');
      a.classList.add('hi'); b.classList.add('hi');
      tooltip.style.display = 'block';
      tooltip.innerHTML = `<b>${e.from_label}</b> \\u2192 <b>${e.to_label}</b><br>${e.via}`;
    });
    path.addEventListener('mousemove', (ev) => {
      tooltip.style.left = (ev.clientX + 12) + 'px'; tooltip.style.top = (ev.clientY + 12) + 'px';
    });
    path.addEventListener('mouseleave', () => {
      path.setAttribute('stroke-width', '1.6'); path.setAttribute('stroke-opacity', '0.55');
      a.classList.remove('hi'); b.classList.remove('hi');
      tooltip.style.display = 'none';
    });
    svg.appendChild(path);
  });
}

window.addEventListener('load', drawConnectors);
window.addEventListener('resize', () => setTimeout(drawConnectors, 100));
"""


def render_deps_chip(obj, direction):
    items = obj.get("depends_on" if direction == "out" else "used_by", [])
    if not items:
        return ""
    chips = []
    for e in items:
        chips.append(f'{e["to_label"]} ({e["via"]})' if direction == "out" else f'{e["from_label"]} ({e["via"]})')
    label = "connects to" if direction == "out" else "used by"
    return f'<div class="deps"><span class="deps-label">{label}:</span> ' + \
           "".join(f'<span class="chip dep">{esc(c)}</span>' for c in chips) + '</div>'


def _render_apis(model):
    if not model["apis"]:
        return '<div class="desc" style="color:#484f58">none found</div>'
    parts = ['<div class="stack">']
    for api in model["apis"]:
        parts.append(f'<div class="card" id="{esc(api["_domid"])}"><div class="card-hd">{esc(api["id"])}<span class="badge">{esc(api["flavor"].upper())}</span></div>')
        parts.append(render_deps_chip(api, "out"))
        parts.append('</div>')
    parts.append('</div>')
    return "".join(parts)


def _render_container(c, sidecar_cls):
    parts = [f'<div class="container{sidecar_cls}" id="{esc(c.get("_domid",""))}"><div class="container-name">{esc(c.get("name"))}</div>']
    img_label = c.get("image_ref") or "(unknown image)"
    parts.append(f'<div class="container-image">{esc(c.get("image_type") or "?")}: {esc(img_label)}</div>')
    warn = " warn" if not c.get("image_type") or (c.get("image_type") == "asset" and "not found" in (c.get("description") or "")) else ""
    parts.append(f'<div class="desc{warn}">{esc(c.get("description"))}</div>')
    if c.get("description_source"):
        parts.append(f'<div class="src">source: {esc(c.get("resolved_path", ""))} ({esc(c["description_source"])})</div>')
    chips = [f'port {p}' for p in c.get("ports", [])] + [f'env: {k}' for k in c.get("env_keys", [])] + ([f'cmd: {" ".join(c["command"])}'] if c.get("command") else [])
    if chips:
        parts.append('<div class="chips">' + "".join(f'<span class="chip">{esc(ch)}</span>' for ch in chips) + '</div>')
    parts.append(render_deps_chip(c, "out"))
    parts.append('</div>')
    return "".join(parts)


def _render_compute(model):
    parts = []
    if model["clusters"]:
        parts.append('<div class="sub-hd">ECS</div>')
    for cl in model["clusters"]:
        parts.append(f'<div class="cluster" id="{esc(cl["_domid"])}"><div class="cluster-hd">🗄 Cluster: {esc(cl["id"])}</div><div class="stack">')
        for svc in cl["services"]:
            kind_note = "load-balanced (ALB)" if svc["kind"] == "load-balanced" else "service"
            parts.append(f'<div class="service" id="{esc(svc["_domid"])}"><div class="service-hd">{esc(svc["id"])}</div>')
            parts.append(f'<div class="service-meta">{kind_note} · desired count: {esc(svc["desired_count"])}</div>')
            parts.append(render_deps_chip(svc, "in"))
            if svc.get("task_def"):
                td = svc["task_def"]
                spec = " · ".join(x for x in [f"{td['cpu']} cpu" if td["cpu"] else None, f"{td['memory']} MiB" if td["memory"] else None] if x)
                parts.append(f'<div class="taskdef-tag" id="{esc(td.get("_domid",""))}">Task definition: {esc(td["id"])}{" — " + spec if spec else ""}</div>')
                parts.append(render_deps_chip(td, "out"))
            for i, c in enumerate(svc["containers"]):
                sidecar_cls = " sidecar" if i > 0 and svc["kind"] == "service" else ""
                parts.append(_render_container(c, sidecar_cls))
            if not svc["containers"]:
                parts.append('<div class="desc warn">no containers resolved for this service</div>')
            parts.append('</div>')
        parts.append('</div></div>')

    if model["lambdas"]:
        parts.append('<div class="sub-hd">Lambda</div><div class="stack">')
        for lam in model["lambdas"]:
            parts.append(f'<div class="card" id="{esc(lam["_domid"])}"><div class="card-hd">{esc(lam["id"])}</div>')
            meta = " · ".join(x for x in [lam.get("runtime"), lam.get("handler")] if x)
            parts.append(f'<div class="card-meta">{esc(meta)}</div>')
            parts.append(render_deps_chip(lam, "in"))
            parts.append(f'<div class="desc">{esc(lam.get("description"))}</div>')
            if lam.get("description_source"):
                parts.append(f'<div class="src">source: {esc(lam.get("resolved_path",""))} ({esc(lam["description_source"])})</div>')
            if lam.get("env_pairs"):
                parts.append('<div class="chips">' + "".join(f'<span class="chip">env: {esc(k)}</span>' for k, _ in lam["env_pairs"]) + '</div>')
            parts.append(render_deps_chip(lam, "out"))
            parts.append('</div>')
        parts.append('</div>')

    if not model["clusters"] and not model["lambdas"]:
        parts.append('<div class="desc" style="color:#484f58">none found</div>')
    return "".join(parts)


def _render_data_stores(model):
    if not model["data_stores"]:
        return '<div class="desc" style="color:#484f58">none found</div>'
    icons = {"table": "🗂", "queue": "📬", "topic": "📢", "bucket": "🪣"}
    parts = ['<div class="stack">']
    for r in model["data_stores"]:
        parts.append(f'<div class="card" id="{esc(r["_domid"])}"><div class="card-hd">{icons.get(r["category"],"")} {esc(r["id"])}<span class="badge data">{esc(r["category"])}</span></div>')
        if r.get("partition_key"):
            parts.append(f'<div class="card-meta">partition key: {esc(r["partition_key"])}</div>')
        parts.append(render_deps_chip(r, "in"))
        parts.append('</div>')
    parts.append('</div>')
    return "".join(parts)


def render_html(model):
    parts = [f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Infra Map</title>
<style>{PAGE_STYLE}</style></head><body>
<h1>Infrastructure Map</h1>
<div class="sub">Left → right is the request path: entry point → compute → data. Parsed straight from CDK constructs; the lines are the actual grant()/env-var/integration wiring found in your source, not a guess.</div>
<div class="layout">
<div class="col col-apis">
<div class="col-hd"><span class="num">1</span>Entry points</div>
{_render_apis(model)}
</div>
<div class="col col-compute"><div class="col-hd"><span class="num">2</span>Compute</div>
{_render_compute(model)}
</div>
<div class="col col-data"><div class="col-hd"><span class="num">3</span>Data &amp; messaging</div>
{_render_data_stores(model)}
</div>
</div>
"""]

    if model["unassigned"]:
        parts.append('<div class="unassigned"><b>Unassigned services</b> (couldn\'t match to a parsed cluster variable): ')
        parts.append(", ".join(esc(s["id"]) for s in model["unassigned"]))
        parts.append('</div>')

    edge_json = json.dumps(model["edge_payload"])
    parts.append(f"""
<svg id="connectors"></svg>
<div id="legend">
  <div class="lg-hd">Connections</div>
  <div><span class="ln solid blue"></span> grant (IAM permission)</div>
  <div><span class="ln dashed teal"></span> env var reference</div>
  <div><span class="ln solid orange"></span> API integration / route</div>
</div>
<div id="tooltip"></div>
<style>{CONNECTOR_STYLE}</style>
<script>
const EDGES = {edge_json};
{CONNECTOR_SCRIPT}
</script>
""")
    parts.append("</body></html>")
    return "".join(parts)
