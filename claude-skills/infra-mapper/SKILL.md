---
name: infra-mapper
description: Generate a visual infrastructure diagram from an AWS CDK (TypeScript) repo showing entry points → compute → data/messaging, with real connector lines from grant()/env-var/API-integration wiring found in the source. Use when the user asks to "map/visualize/diagram my infra/CDK stack", "show what talks to what" in a CDK app, or wants an infra overview of an ECS/Lambda/API Gateway/DynamoDB/SQS/SNS/S3 CDK project.
---

# Infra Mapper

Parses a CDK (TypeScript) repo's constructs — ECS clusters/services/containers,
Lambda, API Gateway (REST + HTTP), DynamoDB, SQS, SNS, S3 — plus an optional
service-package repo, and renders a self-contained HTML diagram: **entry
points → compute → data/messaging**, with connector lines drawn only from
wiring actually found in the source (`grant*()` IAM calls, environment
variable values referencing a resource, `LambdaIntegration`/`HttpAlbIntegration`
routes) — never a guessed connection.

It is regex + brace-balancing, not a TypeScript compiler. It covers common
CDK L2 idioms well but is not exhaustive — see "Known limitations" below
before promising a user it caught everything.

## When to use

- User asks to visualize, diagram, or map a CDK app's infrastructure.
- User asks "what talks to what" / "what does this stack actually do" about
  a CDK repo.
- User wants a shareable overview of ECS/Lambda/API Gateway/DynamoDB/SQS/SNS/S3
  wiring, including which container/Lambda source describes what (pulled from
  `package.json`/`README`/`Dockerfile` in the referenced service repo).

Not a fit for: Terraform/CloudFormation-only repos, CDK apps in Python/Java/Go
(TypeScript `.ts` only), or a request for live/deployed infra state (this only
reads source, never calls AWS).

## Usage

```bash
python3 scripts/map_infra.py --cdk /path/to/cdk-repo --services /path/to/service-package-repo --output infra.html
```

- `--cdk` — required. Root of the CDK app; scanned recursively for `.ts` files.
- `--services` — optional. Root containing service package directories, used
  to resolve `fromAsset()`/`entry` paths and pull real descriptions from
  `package.json`. Omit it and local-asset containers/Lambdas are flagged
  "not found" instead of described.
- `--output` — where to write the HTML (default `infra.html`).

Both paths are validated up front — a typo'd path fails fast with a clear
error rather than silently writing an empty diagram. The CLI also prints a
one-line summary (`Clusters: N Services: N ... Edges: N`) — a good sanity
check that it actually found something before opening the file.

After generating, open the HTML in a browser, or hand it to the user via
SendUserFile / publish it as an Artifact (self-contained, no external deps
except inline SVG/CSS/JS — safe for the Artifact CSP).

### Try it on the bundled example first if unsure of expected output

```bash
python3 scripts/map_infra.py --cdk examples/demo-cdk --services examples/demo-services --output /tmp/demo.html
```

Expect: `Clusters: 1  Services: 2  Containers: 3  Lambdas: 1  APIs: 2  Data stores: 3  Edges: 9`.

## What it recognizes

Both CDK import styles are supported and can be mixed within a repo:

```ts
// namespaced (import * as ns from 'aws-cdk-lib/aws-X')
new ecs.Cluster(this, 'Id', {...})
new dynamodb.Table(this, 'Id', {...})

// named-import (import { Table } from 'aws-cdk-lib/aws-X') — equally common
new Table(this, 'Id', {...})
new NodejsFunction(this, 'Id', { entry: join(__dirname, 'lambdas', 'x.ts'), environment })
```

- **ECS**: clusters, Fargate/EC2 task defs + services, manual `addContainer()`
  and the `ecs_patterns.ApplicationLoadBalancedFargateService` shortcut,
  sidecar containers.
- **Lambda**: `lambda.Function` and `NodejsFunction`/`GoFunction`/
  `PythonFunction`/`DockerImageFunction`; code source from `Code.fromAsset()`
  or a `NodejsFunction`'s `entry:` (both `join(__dirname, ...)` and a plain
  string literal).
- **API Gateway**: REST and HTTP APIs. Lambda routes are tracked whether
  written as one chained expression (`api.root.addResource(...).addMethod(...,
  new LambdaIntegration(fn))`) or built across several statements (`const
  items = api.root.addResource(...); const x = new LambdaIntegration(fn);
  items.addMethod('GET', x)`) — the latter is arguably the more common
  real-world style.
- **DynamoDB** (with partition key), **SQS**, **SNS**, **S3**.
- Edges from `grant*()`, from env-var values that reference a resource
  (`QUEUE_URL: queue.queueUrl`), and from API↔compute integrations.

For each container/Lambda built from a local asset, it cross-references the
path/entry-directory against `--services` and pulls a description from
`package.json`'s `description`, then `README`'s first line, then the
Dockerfile `CMD`/`ENTRYPOINT`.

## Known limitations — set expectations before running

- **Regex, not an AST.** Unusual formatting, options assembled outside the
  constructor call, or a construct built via a helper function that doesn't
  take `this` as the literal first arg won't parse.
- **Multi-stack repos are variable-scoped per file** (correct by design):
  two files can each declare `const cluster = ...` without colliding, but a
  variable can't be resolved across file boundaries (no import-of-variable
  tracking) — this matches CDK's actual scoping in practice, since local
  `const`s aren't importable anyway.
- **Low-level `Cfn*` constructs aren't understood** — VpcLink-based private
  integrations via raw `CfnIntegration`/`CfnRoute` show the boxes but no line.
- **No VPC/networking layer, no RDS.** Only DynamoDB is a "data store" today.
- **SNS subscriptions aren't tracked** unless also wired via `grant()`/env var.
- **An inline `new LambdaIntegration(fn)` passed directly into `.addMethod()`
  on a resource variable from an earlier statement** isn't matched (the fully
  chained form and the separate-integration-variable form both are).
- When something can't be confidently resolved, it's flagged in the output
  (e.g. "asset path referenced but not found") rather than guessed — call
  this out to the user rather than treating a sparse diagram as an error.

If the CLI's summary line comes back all-zero, don't report success — check
whether the repo uses an unrecognized idiom (e.g. CloudFormation `Cfn*`
constructs throughout) before assuming the diagram is complete.

## Verified against

Tested against the bundled synthetic example (ECS + Lambda + API Gateway +
DynamoDB/SQS/S3, both import styles, sidecar containers) and against a real
open-source CDK app (`aws-samples/aws-cdk-examples`,
`api-cors-lambda-crud-dynamodb`: 5 Lambdas + DynamoDB + REST API, named-import
style, multi-statement route wiring) — correctly resolved all 5 Lambdas, the
table, the API, all 5 `grantReadWriteData` edges, and all 5 API→Lambda
integration edges, plus pulled the real shared `package.json` description for
each Lambda.
