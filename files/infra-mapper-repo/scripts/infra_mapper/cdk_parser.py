"""Extracts CDK constructs and the edges between them from a repo's .ts files.

Variable scoping note: every lookup table keyed by a construct's local
variable name (`clusters`, `task_defs`, `resources`, and the internal
`var_lookup`) is built **per source file** and merged into the returned dict
under a `f{file_index}:varname` key. Two stack files that both write
`const cluster = new ecs.Cluster(...)` are extremely common in real
multi-stack CDK apps, and a single shared global table would let the second
file's `cluster` silently clobber the first — dropping an entire resource
from the diagram with no warning. Edge resolution (grant calls, env-var
references, route integrations) is likewise resolved against the *same
file's* variable table, since a bare identifier can only meaningfully refer
to something declared in that file anyway.
"""
import re
from pathlib import Path

from .constants import (
    ADD_CONTAINER_RE, ADD_METHOD_RE, ADD_RESOURCE_ASSIGN_RE, ADD_ROUTES_RE,
    ALB_INTEGRATION_RE, CLASS_TO_CTYPE, CLUSTER_REF_RE, CODE_ASSET_RE, COMMAND_RE,
    CONSTRUCT_RE, CPU_RE, DESIRED_RE, ENTRY_JOIN_RE, ENTRY_LITERAL_RE, ENV_VAR_REF_RE,
    GRANT_RE, HANDLER_RE, IGNORE_DIRS, IMAGE_ASSET_RE, IMAGE_ECR_RE,
    IMAGE_REGISTRY_RE, IMPORT_ALIAS_RE, INTEGRATION_ASSIGN_RE, KNOWN_NAMESPACES,
    LAMBDA_INTEGRATION_BARE_RE, LAMBDA_INTEGRATION_ROUTE_RE, MEM_RE, PARTITION_KEY_RE,
    PORT_RE, RESOURCE_TYPES, RUNTIME_RE, TASKDEF_REF_RE, TASK_IMAGE_OPTS_RE,
)
from .text_utils import dom_id, extract_block, extract_options, find_matching, parse_env_pairs


def build_alias_map(text):
    """Map a file's local import alias (e.g. `apig`) to the canonical CDK
    namespace (`apigatewayv2`) so `new apig.HttpApi(...)` is recognized the
    same as `new apigatewayv2.HttpApi(...)`. Real code aliases imports
    constantly — this must not assume the textbook names."""
    amap = {}
    for alias, module in IMPORT_ALIAS_RE.findall(text):
        amap[alias] = module.replace("-", "_")
    return amap


def parse_container_options(text):
    image_type, image_ref = None, None
    m = IMAGE_ASSET_RE.search(text)
    if m:
        image_type, image_ref = "asset", m.group(1)
    else:
        m = IMAGE_REGISTRY_RE.search(text)
        if m:
            image_type, image_ref = "registry", m.group(1)
        else:
            m = IMAGE_ECR_RE.search(text)
            if m:
                image_type, image_ref = "ecr", m.group(1)
    env_pairs = parse_env_pairs(text)
    cmd_m = COMMAND_RE.search(text)
    return {
        "image_type": image_type,
        "image_ref": image_ref,
        "env_pairs": env_pairs,
        "env_keys": [k for k, _ in env_pairs],
        "ports": [int(p) for p in PORT_RE.findall(text)],
        "command": [c.strip().strip("'\"") for c in cmd_m.group(1).split(",")] if cmd_m else [],
        "depends_on": [],
    }


def _resolve_entry_dir(opts, f):
    """Resolve a `NodejsFunction`'s `entry: join(__dirname, 'lambdas', 'x.ts')`
    or `entry: 'lambdas/x.ts'` to the directory containing it, so the
    existing asset-directory enrichment machinery (package.json/README
    lookup) can describe it the same way as a `Code.fromAsset(...)` dir."""
    m = ENTRY_JOIN_RE.search(opts)
    if m:
        parts = re.findall(r"['\"]([^'\"]+)['\"]", m.group(1))
        if not parts:
            return None
        entry_path = (f.parent / Path(*parts)).resolve()
        return str(entry_path.parent)
    m = ENTRY_LITERAL_RE.search(opts)
    if m:
        entry_path = (f.parent / m.group(1)).resolve()
        return str(entry_path.parent)
    return None


def _parse_file_constructs(text, ns, f, clusters, task_defs, services, resources):
    """Parse one file's `new x.Y(this, 'Id', {...})` and `.addContainer(...)`
    calls into the shared (already-namespaced) collections, returning a
    var_lookup local to this file only."""
    alias_map = build_alias_map(text)
    var_lookup = {}

    for m in CONSTRUCT_RE.finditer(text):
        var, ns_alias, cls, cid = m.group(1), m.group(2), m.group(3), m.group(4)
        if ns_alias:
            canonical_ns = alias_map.get(ns_alias, ns_alias)
            if canonical_ns not in KNOWN_NAMESPACES:
                continue
            ctype = f"{canonical_ns}.{cls}"
        else:
            # Named-import style: `import { Table } from 'aws-cdk-lib/aws-dynamodb'`
            # then `new Table(this, 'Id', {...})` with no namespace at all.
            ctype = CLASS_TO_CTYPE.get(cls)
            if ctype is None:
                continue
        local_key = var or cid
        key = f"{ns}:{local_key}"
        opts = extract_options(text, m.end()) or ""
        category = RESOURCE_TYPES.get(ctype)

        if ctype == "ecs.Cluster":
            clusters[key] = {"id": cid, "_domid": dom_id("cluster", key)}

        elif ctype in ("ecs.FargateTaskDefinition", "ecs.Ec2TaskDefinition"):
            cpu_m, mem_m = CPU_RE.search(opts), MEM_RE.search(opts)
            td = {"id": cid, "cpu": cpu_m.group(1) if cpu_m else None,
                  "memory": mem_m.group(1) if mem_m else None, "containers": [], "depends_on": [],
                  "_domid": dom_id("taskdef", key)}
            task_defs[key] = td
            var_lookup[local_key] = ("taskdef", td)

        elif ctype in ("ecs.FargateService", "ecs.Ec2Service"):
            cref = CLUSTER_REF_RE.search(opts)
            tref = TASKDEF_REF_RE.search(opts)
            dcount = DESIRED_RE.search(opts)
            cluster_local = (cref.group(1) if cref and cref.group(1) else "cluster") if cref else None
            taskdef_local = (tref.group(1) if tref and tref.group(1) else "taskDefinition") if tref else None
            svc = {
                "id": cid, "kind": "service",
                "cluster_ref": f"{ns}:{cluster_local}" if cluster_local else None,
                "taskdef_ref": f"{ns}:{taskdef_local}" if taskdef_local else None,
                "desired_count": dcount.group(1) if dcount else "1",
                "depends_on": [], "_domid": dom_id("service", key),
            }
            services.append(svc)
            var_lookup[local_key] = ("service", svc)

        elif ctype.startswith("ecs_patterns.") and "FargateService" in ctype:
            cref = CLUSTER_REF_RE.search(opts)
            dcount = DESIRED_RE.search(opts)
            tio = TASK_IMAGE_OPTS_RE.search(opts)
            container = None
            if tio:
                end = find_matching(opts, tio.end() - 1)
                if end != -1:
                    c = parse_container_options(opts[tio.end():end])
                    c["name"] = cid + " (web)"
                    c["_domid"] = dom_id("container", key + "__inline")
                    container = c
            cluster_local = (cref.group(1) if cref and cref.group(1) else "cluster") if cref else None
            svc = {
                "id": cid, "kind": "load-balanced",
                "cluster_ref": f"{ns}:{cluster_local}" if cluster_local else None,
                "taskdef_ref": None, "desired_count": dcount.group(1) if dcount else "1",
                "inline_container": container, "depends_on": [], "_domid": dom_id("service", key),
            }
            services.append(svc)
            var_lookup[local_key] = ("service", svc)
            if container is not None:
                var_lookup[local_key] = ("container", container)  # listener/.grants usually target the service itself

        elif category == "table":
            pk_block = extract_block(opts, "partitionKey")
            pk = PARTITION_KEY_RE.search(pk_block).group(1) if pk_block and PARTITION_KEY_RE.search(pk_block) else None
            r = {"var": local_key, "id": cid, "category": "table", "partition_key": pk, "used_by": [], "_domid": dom_id("resource", key)}
            resources[key] = r
            var_lookup[local_key] = ("resource", r)

        elif category in ("queue", "topic", "bucket"):
            r = {"var": local_key, "id": cid, "category": category, "used_by": [], "_domid": dom_id("resource", key)}
            resources[key] = r
            var_lookup[local_key] = ("resource", r)

        elif category == "lambda":
            runtime_m, handler_m, code_m = RUNTIME_RE.search(opts), HANDLER_RE.search(opts), CODE_ASSET_RE.search(opts)
            if code_m:
                image_type, image_ref = "asset", code_m.group(1)
            else:
                entry_dir = _resolve_entry_dir(opts, f)
                image_type, image_ref = ("asset", entry_dir) if entry_dir else (None, None)
            r = {
                "var": local_key, "id": cid, "category": "lambda",
                "runtime": runtime_m.group(1) if runtime_m else None,
                "handler": handler_m.group(1) if handler_m else None,
                "image_type": image_type,
                "image_ref": image_ref,
                "env_pairs": parse_env_pairs(opts), "used_by": [], "depends_on": [],
                "_domid": dom_id("lambda", key),
            }
            resources[key] = r
            var_lookup[local_key] = ("lambda", r)

        elif category == "api":
            r = {"var": local_key, "id": cid, "category": "api",
                 "flavor": "http" if "apigatewayv2" in ctype else "rest",
                 "used_by": [], "depends_on": [], "_domid": dom_id("api", key)}
            resources[key] = r
            var_lookup[local_key] = ("api", r)

    for m in ADD_CONTAINER_RE.finditer(text):
        cvar, owner, cname = m.group(1), m.group(2), m.group(3)
        opts = extract_options(text, m.end()) or ""
        c = parse_container_options(opts)
        c["name"] = cname
        owner_key = f"{ns}:{owner}"
        c["_domid"] = dom_id("container", owner_key + "__" + cname)
        task_defs.setdefault(owner_key, {"id": owner, "cpu": None, "memory": None, "containers": [], "depends_on": [], "_domid": dom_id("taskdef", owner_key)})
        task_defs[owner_key]["containers"].append(c)
        if cvar:
            var_lookup[cvar] = ("container", c)

    return var_lookup


def _resolve_env_edges(containers_and_lambdas, var_lookup, edges):
    for kind, obj in containers_and_lambdas:
        for key, val in obj.get("env_pairs", []):
            vm = ENV_VAR_REF_RE.match(val)
            if not vm:
                continue
            res_entry = var_lookup.get(vm.group(1))
            if res_entry and res_entry[0] == "resource":
                edges.append({"from_kind": kind, "from_ref": obj, "to_kind": "resource",
                              "to_ref": res_entry[1], "via": f"env:{key}"})


def _resolve_grant_edges(text, var_lookup, edges):
    for m in GRANT_RE.finditer(text):
        res_var, grant_method, consumer_var = m.groups()
        res_entry = var_lookup.get(res_var)
        consumer_entry = var_lookup.get(consumer_var)
        if res_entry and res_entry[0] == "resource" and consumer_entry:
            edges.append({"from_kind": consumer_entry[0], "from_ref": consumer_entry[1],
                          "to_kind": "resource", "to_ref": res_entry[1], "via": f"grant{grant_method}"})


def _resolve_resource_owner_map(text, var_lookup):
    """Track `const child = parent.addResource('name')` (and further chained
    `child2 = child.addResource(...)`) back to the api var it ultimately
    hangs off of — real API Gateway code very often builds the resource tree
    across several statements rather than one chained expression."""
    owner = {}
    for m in ADD_RESOURCE_ASSIGN_RE.finditer(text):
        child, parent = m.groups()
        parent_entry = var_lookup.get(parent)
        if parent_entry and parent_entry[0] == "api":
            owner[child] = parent
        elif parent in owner:
            owner[child] = owner[parent]
    return owner


def _resolve_two_step_method_edges(text, var_lookup, edges):
    """Handles `const x = new LambdaIntegration(fn); resource.addMethod('GET', x)`
    — an integration built as its own variable rather than inlined into the
    addMethod() call, which LAMBDA_INTEGRATION_ROUTE_RE/BARE_RE don't cover."""
    resource_owner = _resolve_resource_owner_map(text, var_lookup)
    integration_lookup = dict(INTEGRATION_ASSIGN_RE.findall(text))
    seen = {(e["from_ref"].get("_domid"), e["to_ref"].get("_domid")) for e in edges if e["via"] == "LambdaIntegration"}

    for m in ADD_METHOD_RE.finditer(text):
        resource_var, arg_var = m.groups()
        api_var = resource_owner.get(resource_var)
        if not api_var:
            continue
        api_entry = var_lookup.get(api_var)
        if not api_entry or api_entry[0] != "api":
            continue
        lambda_var = integration_lookup.get(arg_var, arg_var)
        lam_entry = var_lookup.get(lambda_var)
        if not lam_entry or lam_entry[0] != "lambda":
            continue
        edge_key = (api_entry[1].get("_domid"), lam_entry[1].get("_domid"))
        if edge_key in seen:
            continue
        seen.add(edge_key)
        edges.append({"from_kind": "api", "from_ref": api_entry[1], "to_kind": "lambda",
                      "to_ref": lam_entry[1], "via": "LambdaIntegration"})


def _resolve_api_edges(text, var_lookup, rest_apis, edges):
    for m in LAMBDA_INTEGRATION_ROUTE_RE.finditer(text):
        api_var, lambda_var = m.groups()
        api_entry, lam_entry = var_lookup.get(api_var), var_lookup.get(lambda_var)
        if api_entry and lam_entry and api_entry[0] == "api" and lam_entry[0] == "lambda":
            edges.append({"from_kind": "api", "from_ref": api_entry[1], "to_kind": "lambda",
                          "to_ref": lam_entry[1], "via": "LambdaIntegration"})

    # fallback: bare LambdaIntegration(fn) resolves only when there is a single
    # REST api in the whole repo and this file didn't already match an explicit route
    matched_lambdas = {m.group(2) for m in LAMBDA_INTEGRATION_ROUTE_RE.finditer(text)}
    for m in LAMBDA_INTEGRATION_BARE_RE.finditer(text):
        lambda_var = m.group(1)
        if lambda_var in matched_lambdas:
            continue
        lam_entry = var_lookup.get(lambda_var)
        if lam_entry and lam_entry[0] == "lambda" and len(rest_apis) == 1:
            edges.append({"from_kind": "api", "from_ref": rest_apis[0], "to_kind": "lambda",
                          "to_ref": lam_entry[1], "via": "LambdaIntegration"})

    for m in ADD_ROUTES_RE.finditer(text):
        api_var = m.group(1)
        paren_end = find_matching(text, m.end() - 1, "(", ")")
        if paren_end == -1:
            continue
        block = text[m.end():paren_end]
        alb_m = ALB_INTEGRATION_RE.search(block)
        api_entry = var_lookup.get(api_var)
        if alb_m and api_entry and api_entry[0] == "api":
            svc_entry = var_lookup.get(alb_m.group(1))
            if svc_entry and svc_entry[0] in ("service", "container"):
                to_kind = "service" if svc_entry[0] == "service" else "container"
                edges.append({"from_kind": "api", "from_ref": api_entry[1], "to_kind": to_kind,
                              "to_ref": svc_entry[1], "via": "HttpAlbIntegration"})

    _resolve_two_step_method_edges(text, var_lookup, edges)


def parse_cdk(cdk_root: Path):
    clusters, task_defs, services, resources = {}, {}, [], {}
    edges = []

    ts_files = sorted(p for p in cdk_root.rglob("*.ts") if not any(part in IGNORE_DIRS for part in p.parts))
    full_texts = {}
    var_lookup_by_file = {}

    for file_idx, f in enumerate(ts_files):
        text = f.read_text(encoding="utf-8", errors="ignore")
        full_texts[f] = text
        ns = f"f{file_idx}"
        var_lookup = _parse_file_constructs(text, ns, f, clusters, task_defs, services, resources)
        var_lookup_by_file[f] = var_lookup
        for td in task_defs.values():
            for c in td["containers"]:
                c.setdefault("_file", f)
        for r in resources.values():
            if r["category"] == "lambda":
                r.setdefault("_file", f)

    rest_apis = [r for r in resources.values() if r["category"] == "api" and r["flavor"] == "rest"]

    for f, text in full_texts.items():
        var_lookup = var_lookup_by_file[f]
        _resolve_grant_edges(text, var_lookup, edges)

        # env-var reference edges: only for containers/lambdas actually declared
        # in this file, matched against this file's own variable table — doing
        # this globally on every iteration was producing one duplicate edge per
        # file in the repo.
        own_sources = [("container", c) for td in task_defs.values() for c in td["containers"] if c.get("_file") == f]
        own_sources += [("lambda", r) for r in resources.values() if r["category"] == "lambda" and r.get("_file") == f]
        _resolve_env_edges(own_sources, var_lookup, edges)

        _resolve_api_edges(text, var_lookup, rest_apis, edges)

    return clusters, task_defs, services, resources, edges
