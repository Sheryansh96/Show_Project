# infra-mapper

Reads a CDK (TypeScript) repo and a service-package repo, and renders a fixed
left-to-right infrastructure diagram: **Entry points (API Gateway) → Compute
(ECS/Lambda) → Data & Messaging (DynamoDB/SQS/SNS/S3)**, with real connector
lines drawn between the boxes that actually reference each other in your CDK
source — via `grant*()` calls, environment variable values, or API
integrations (`LambdaIntegration`, `HttpAlbIntegration`).

Not a generic import-graph tool — it understands specific CDK L2 idioms:

```ts
new ecs.Cluster(this, 'Id', {...})
new ecs.FargateTaskDefinition(this, 'Id', {...})
taskDef.addContainer('Name', { image, environment, portMappings, command })
new ecs_patterns.ApplicationLoadBalancedFargateService(this, 'Id', {...})
new dynamodb.Table / sqs.Queue / sns.Topic / s3.Bucket(this, 'Id', {...})
new lambda.Function(this, 'Id', { runtime, handler, code, environment })
new apigateway.RestApi / apigatewayv2.HttpApi(this, 'Id', {...})

resource.grant*(consumer)                        // -> compute uses resource
environment: { KEY: resourceVar.someProperty }    // -> compute uses resource
api.root.addResource(...).addMethod(..., new apigateway.LambdaIntegration(fn))
httpApi.addRoutes({ integration: new HttpAlbIntegration(id, service.listener) })
```

Import aliases are resolved from your `import * as X from "aws-cdk-lib/aws-Y"`
statements, so `apig.HttpApi` is recognized the same as `apigatewayv2.HttpApi`
regardless of what you named the import. The equally common named-import
style also works — `import { Table } from 'aws-cdk-lib/aws-dynamodb'` plus
`new Table(this, 'Id', {...})` (no namespace prefix at all) resolves the same
as `new dynamodb.Table(...)`, including `NodejsFunction`/`GoFunction`/
`PythonFunction`/`DockerImageFunction` as Lambda, and a `NodejsFunction`'s
`entry: join(__dirname, 'lambdas', 'x.ts')` (or a plain string literal) is
resolved to that file's directory the same way a `Code.fromAsset()` dir is.
API Gateway routes built across several statements — `const items =
api.root.addResource('items'); const x = new LambdaIntegration(fn);
items.addMethod('GET', x)` — are tracked too, not just the single-expression
chained form.

For each container/Lambda built from a local asset (`ContainerImage.fromAsset(...)`,
`Code.fromAsset(...)`), it cross-references that path against your service
package repo and pulls a real description from `package.json`'s
`description` field, falling back to the first line of `README.md`, then the
`CMD`/`ENTRYPOINT` in the `Dockerfile`.

## Usage

```bash
python3 scripts/map_infra.py --cdk /path/to/your-cdk-repo --services /path/to/your-service-packages --output infra.html
```

- `--cdk` — required. Root of the CDK app (scans all `.ts` files recursively).
- `--services` — optional. Root containing your service package directories
  (used to resolve `fromAsset()` paths and pull descriptions). Omit it and
  containers/Lambdas built from local assets will just be flagged as
  "not found" instead of described.
- `--output` — where to write the HTML (default `infra.html`).

Open the output file in a browser. It's a single self-contained HTML file —
no server, no external dependencies except a CDN-hosted font-free vanilla JS
(no D3, no build step).

## Try it on the bundled example

```bash
python3 scripts/map_infra.py --cdk examples/demo-cdk --services examples/demo-services --output demo.html
```

This is a synthetic stack (ECS Fargate services, a Lambda, DynamoDB, SQS, S3,
both REST and HTTP APIs) used to validate the parser end to end — a good
sanity check before pointing it at a real repo.

## What it gets right today

- ECS: clusters, Fargate/EC2 task definitions and services, both the manual
  `addContainer()` pattern and the `ecs_patterns.ApplicationLoadBalancedFargateService`
  shortcut, including sidecar containers.
- Lambda: runtime, handler, and code source.
- API Gateway: both REST (`apigateway.RestApi`) and HTTP (`apigatewayv2.HttpApi`).
- DynamoDB (with partition key), SQS, SNS, S3.
- Dependency edges from IAM `grant*()` calls and from environment variable
  values that reference a resource (e.g. `QUEUE_URL: queue.queueUrl`).
- API → compute edges from `LambdaIntegration` and `HttpAlbIntegration`.

## Known limitations

- **Regex + brace-balancing, not a TS compiler.** Covers common CDK idioms;
  unusual formatting or indirection (e.g. options objects assembled outside
  the constructor call) may not parse.
- **Low-level `Cfn*` constructs aren't understood.** If your stack wires API
  Gateway to a backend via raw `CfnIntegration`/`CfnRoute` (common with
  VpcLink-based private integrations) rather than the higher-level
  `HttpAlbIntegration`/`LambdaIntegration` constructs, that edge won't be
  detected — it'll show the boxes but no connecting line, rather than
  guessing at a connection.
- **No VPC/networking layer.** Security groups, subnets, VpcLinks aren't
  modeled.
- **No RDS.** Only DynamoDB is covered under "data stores" today.
- **SNS subscriptions aren't tracked** unless wired via `grant()` or an env
  var — `topic.addSubscription(...)` alone won't produce an edge.
- **An inline `new LambdaIntegration(fn)` passed directly to `.addMethod()`
  on a resource variable declared in an earlier statement** (rather than the
  fully chained one-liner, or a separately-declared integration variable —
  both of which *are* handled) isn't matched yet.
- Circular imports/dependencies between ECS files can land a node in a
  slightly arbitrary position, though the parser detects cycles and forces
  progress rather than hanging.

When something can't be confidently resolved, the tool flags it in the output
(e.g. "asset path referenced but not found") rather than fabricating a
description or a connection.

## Extending

The implementation lives in `scripts/infra_mapper/`, split by concern:

- `constants.py` — ignore lists, resource-type tables, every compiled regex
- `text_utils.py` — brace/string/comment-aware text scanning shared by the parser
- `cdk_parser.py` — `parse_cdk()`: construct extraction + edge resolution
- `enrichment.py` — resolves a container/Lambda's code asset to a description
- `model.py` — `build_model()`: assembles parsed constructs into the render tree
- `render.py` — `render_html()`: emits the self-contained HTML/CSS/JS page
- `cli.py` — argument parsing and `main()`

`scripts/map_infra.py` is now a thin shim that calls `infra_mapper.cli.main()`,
kept so the documented `python map_infra.py --cdk ...` usage above still works.

To add a new resource type, add an entry to `RESOURCE_TYPES` / `KNOWN_NAMESPACES`
in `constants.py` and a small parsing block inside the `CONSTRUCT_RE` loop in
`cdk_parser.py`.

### Notes on correctness

- CDK variable names (`cluster`, `queue`, `taskDef`, ...) are scoped **per
  source file**, not globally. Two stack files that each declare
  `const cluster = new ecs.Cluster(...)` are common in real multi-stack
  repos; a global lookup table would let the second file's `cluster` silently
  clobber the first, dropping a whole resource from the diagram with no
  warning. Edge resolution (grants, env vars, route integrations) is
  similarly resolved against the same file's variable table only.
- Brace/paren balancing (`find_matching`) skips over `//` and `/* */`
  comments and over string/template literals, so a stray `{`/`}` in a
  comment, a Docker `command`, or a JSON literal in an env var doesn't
  desynchronize the scan.
- `--cdk` and `--services` are validated up front; a typo'd path fails fast
  with a clear error instead of silently producing an empty diagram.
