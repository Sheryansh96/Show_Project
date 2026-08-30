#!/usr/bin/env python3
"""map_infra.py — Read a CDK repo's constructs (ECS clusters/services/containers,
API Gateway, DynamoDB, SQS, SNS, S3, Lambda) plus a service-package repo, and
render a fixed infrastructure diagram showing what talks to what and, for
anything with source code behind it, what it actually does.

Thin CLI entry point — the actual implementation lives in the `infra_mapper`
package alongside this script (constants.py, text_utils.py, cdk_parser.py,
enrichment.py, model.py, render.py, cli.py). See infra_mapper/__init__.py or
the README for how the pieces fit together.

Usage:
    python map_infra.py --cdk /path/to/cdk-repo --services /path/to/service-package-repo --output infra.html
"""
from infra_mapper.cli import main

if __name__ == "__main__":
    main()
