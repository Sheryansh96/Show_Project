import argparse
import sys
from pathlib import Path

from .model import build_model
from .render import render_html


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cdk", required=True, help="Root of the CDK app (scanned recursively for .ts files)")
    ap.add_argument("--services", default=None, help="Root containing your service package directories")
    ap.add_argument("--output", default="infra.html")
    args = ap.parse_args(argv)

    cdk_root = Path(args.cdk).resolve()
    if not cdk_root.is_dir():
        ap.error(f"--cdk path does not exist or is not a directory: {cdk_root}")

    services_root = None
    if args.services:
        services_root = Path(args.services).resolve()
        if not services_root.is_dir():
            ap.error(f"--services path does not exist or is not a directory: {services_root}")

    ts_files = list(cdk_root.rglob("*.ts"))
    if not ts_files:
        print(f"warning: no .ts files found under {cdk_root} — output will be empty", file=sys.stderr)

    model = build_model(cdk_root, services_root)
    Path(args.output).write_text(render_html(model), encoding="utf-8")

    n_clusters = len(model["clusters"])
    n_services = sum(len(c["services"]) for c in model["clusters"])
    n_containers = sum(len(s["containers"]) for c in model["clusters"] for s in c["services"])
    print(f"Clusters: {n_clusters}  Services: {n_services}  Containers: {n_containers}  "
          f"Lambdas: {len(model['lambdas'])}  APIs: {len(model['apis'])}  "
          f"Data stores: {len(model['data_stores'])}  Edges: {len(model['edges'])}")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
