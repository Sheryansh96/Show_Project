# Show_Project

## infra-mapper

Parses an AWS CDK (TypeScript) repo and renders a self-contained HTML
infrastructure diagram — entry points → compute → data/messaging — with
connector lines drawn only from `grant*()`/env-var/API-integration wiring
actually found in the source, never a guessed connection.

- **[`files/infra-mapper-repo`](files/infra-mapper-repo)** — the tool itself:
  the `infra_mapper` Python package, CLI, and a synthetic example. See its
  own [README](files/infra-mapper-repo/README.md) for usage, what it parses,
  and known limitations.
- **[`claude-skills/infra-mapper`](claude-skills/infra-mapper)** — the same
  tool packaged as a [Claude Code](https://claude.com/claude-code) skill
  (`SKILL.md` + a bundled, self-contained copy of the package), so Claude can
  generate these diagrams on request. See its
  [README](claude-skills/infra-mapper/README.md) for how to install it on a
  machine.
