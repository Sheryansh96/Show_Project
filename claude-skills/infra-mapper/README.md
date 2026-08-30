# infra-mapper (Claude Code skill)

A [Claude Code](https://claude.com/claude-code) skill that generates a visual
infrastructure diagram from an AWS CDK (TypeScript) repo — entry points →
compute → data/messaging, with connector lines drawn only from `grant*()`/
env-var/API-integration wiring actually found in the source.

This folder is self-contained and is the only copy of the tool in this repo:
`SKILL.md` (the instructions Claude reads — also the best reference for what
it parses and its known limitations), `scripts/` (the `infra_mapper` Python
package + CLI, zero external dependencies), and `examples/` (a synthetic CDK
app for sanity-checking).

## Install on a machine

```bash
git clone https://github.com/Sheryansh96/Show_Project.git
mkdir -p ~/.claude/skills
cp -R Show_Project/claude-skills/infra-mapper ~/.claude/skills/
```

Claude Code picks up anything under `~/.claude/skills/` automatically — no
restart or registration step. Already have the repo cloned? Just `git pull`
then rerun the `cp` line.

## Updating

This is a copy, not a synced link — after changing the skill, re-copy it to
each machine's `~/.claude/skills/infra-mapper`:

```bash
git pull
rm -rf ~/.claude/skills/infra-mapper
cp -R claude-skills/infra-mapper ~/.claude/skills/
```

## Verify it after installing

```bash
cd ~/.claude/skills/infra-mapper
python3 scripts/map_infra.py --cdk examples/demo-cdk --services examples/demo-services --output /tmp/demo.html
```

Expect: `Clusters: 1  Services: 2  Containers: 3  Lambdas: 1  APIs: 2  Data stores: 3  Edges: 9`.
