# Show_Project

## infra-mapper

Parses an AWS CDK (TypeScript) repo and renders a self-contained HTML
infrastructure diagram — entry points → compute → data/messaging — with
connector lines drawn only from `grant*()`/env-var/API-integration wiring
actually found in the source, never a guessed connection.

Packaged as a [Claude Code](https://claude.com/claude-code) skill at
**[`claude-skills/infra-mapper`](claude-skills/infra-mapper)** —
`SKILL.md` plus a self-contained copy of the `infra_mapper` Python package,
CLI, and a synthetic example, so Claude can generate these diagrams on
request. See its [README](claude-skills/infra-mapper/README.md) for usage
and how to install it on another machine.
