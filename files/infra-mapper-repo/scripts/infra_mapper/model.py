"""Assembles parsed CDK constructs into the tree the renderer walks."""
from pathlib import Path

from .cdk_parser import parse_cdk
from .enrichment import enrich_with_code


def _label_of(kind, ref):
    if kind == "container":
        return ref.get("name", "?")
    if kind in ("service", "taskdef", "lambda", "api", "resource"):
        return ref.get("id", ref.get("var", "?"))
    return "?"


def build_model(cdk_root: Path, services_root):
    clusters, task_defs, services, resources, edges = parse_cdk(cdk_root)
    cluster_tree = {key: {"id": c["id"], "services": [], "_domid": c["_domid"]} for key, c in clusters.items()}
    unassigned = []

    for svc in services:
        if svc["kind"] == "service":
            td = task_defs.get(svc["taskdef_ref"], {"id": svc["taskdef_ref"], "cpu": None, "memory": None, "containers": [], "depends_on": []})
            svc["task_def"] = td
            containers = td["containers"]
        else:
            c = svc.get("inline_container")
            containers = [c] if c else []
            svc["task_def"] = None
        for c in containers:
            enrich_with_code(c, cdk_root, services_root)
        svc["containers"] = containers
        target = cluster_tree.get(svc["cluster_ref"])
        (target["services"] if target is not None else unassigned).append(svc)

    lambdas = [r for r in resources.values() if r["category"] == "lambda"]
    for lam in lambdas:
        enrich_with_code(lam, cdk_root, services_root)

    apis = [r for r in resources.values() if r["category"] == "api"]
    data_stores = [r for r in resources.values() if r["category"] in ("table", "queue", "topic", "bucket")]

    for e in edges:
        e["from_label"] = _label_of(e["from_kind"], e["from_ref"])
        e["to_label"] = _label_of(e["to_kind"], e["to_ref"])
        e["from_id"] = e["from_ref"].get("_domid")
        e["to_id"] = e["to_ref"].get("_domid")
        e["from_ref"].setdefault("depends_on", []).append(e)
        e["to_ref"].setdefault("used_by", []).append(e)

    # thin serializable edge list for the JS layer (no circular dict refs)
    edge_payload = [{"from": e["from_id"], "to": e["to_id"], "via": e["via"],
                      "from_label": e["from_label"], "to_label": e["to_label"]}
                     for e in edges if e["from_id"] and e["to_id"]]

    return {"clusters": list(cluster_tree.values()), "unassigned": unassigned,
            "lambdas": lambdas, "apis": apis, "data_stores": data_stores,
            "edges": edges, "edge_payload": edge_payload}
