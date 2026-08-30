"""Resolves a container/Lambda's code asset to a human-readable description
by cross-referencing the service-package repo."""
import json
import re
from pathlib import Path


def find_service_dir(image_ref: str, cdk_root: Path, services_root):
    candidates = []
    if services_root:
        candidates.append(services_root / Path(image_ref).name)
    candidates.append((cdk_root / image_ref).resolve())
    candidates.append((cdk_root / "lib" / image_ref).resolve())
    for c in candidates:
        if c.is_dir():
            return c
    if services_root:
        base = Path(image_ref).name
        for d in services_root.iterdir():
            if d.is_dir() and d.name == base:
                return d
    return None


def describe_service_dir(d: Path):
    pkg = d / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
            if data.get("description"):
                return data["description"], "package.json"
        except (json.JSONDecodeError, OSError):
            pass
    readme = next((f for f in d.glob("README*")), None)
    if readme:
        for line in readme.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip().lstrip("#").strip()
            if line:
                return line, readme.name
    dockerfile = d / "Dockerfile"
    if dockerfile.is_file():
        text = dockerfile.read_text(encoding="utf-8", errors="ignore")
        cmd = re.search(r'^(CMD|ENTRYPOINT)\s+(.+)$', text, re.MULTILINE)
        if cmd:
            return f"runs `{cmd.group(2).strip()}` (from Dockerfile, no description found)", "Dockerfile"
    return None, None


def enrich_with_code(obj, cdk_root, services_root):
    obj["description"], obj["description_source"] = None, None
    if obj.get("image_type") == "asset" and obj.get("image_ref"):
        d = find_service_dir(obj["image_ref"], cdk_root, services_root)
        if d:
            desc, src = describe_service_dir(d)
            obj["description"], obj["description_source"], obj["resolved_path"] = desc, src, str(d)
        else:
            obj["description"] = "asset path referenced but not found in the service repo you gave me"
    elif obj.get("image_type") == "registry":
        obj["description"] = f"third-party image ({obj['image_ref']}), not part of your repos"
    elif obj.get("image_type") == "ecr":
        obj["description"] = f"pulled from an existing ECR repo (`{obj['image_ref']}`) — not built from a repo I can inspect"
    else:
        obj["description"] = "couldn't determine the image/code source"
    return obj
