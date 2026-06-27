# Project skills

This folder holds **project-level skills** for Claude Code. Anything here is
versioned with the repo, so every contributor (and Claude, when working in this
project) gets the same skills — no per-machine install needed.

## How to add a skill

Create one folder per skill, with a `SKILL.md` inside:

```
.claude/skills/
  my-skill/
    SKILL.md        # required
    ...              # optional: scripts, templates, reference files
```

The folder name is the skill's id (use `kebab-case`).

## SKILL.md format

A `SKILL.md` is Markdown with YAML frontmatter. The `description` is what Claude
uses to decide when the skill is relevant, so make it specific and trigger-rich.

```markdown
---
name: my-skill
description: One-line summary of what this does and WHEN to use it. Mention the
  trigger phrases a user would say, e.g. "generate a test contract", "validate a
  template". This text drives whether the skill gets picked.
---

# My skill

Instructions Claude should follow when this skill runs. Be explicit:
- What to do, step by step.
- Which files/commands to use.
- What the output should look like.

You can reference other files in this folder by relative path, and include
example commands, templates, or checklists.
```

## Notes

- Skills here are **additive** — they extend the available set, they don't
  restrict it. To limit which skills Claude may use, use `deny`/`allow` rules on
  the `Skill` tool in `.claude/settings.json` instead.
- To scaffold or refine a skill interactively, use the `skill-creator` skill.
- Keep skills focused: one clear job per skill beats one giant catch-all.

## Ideas for this project (template-genie-app)

- `test-data` — generate a sample `.xlsx` (with multiple sheets / edge cases like
  hyperlinked cells) to exercise the bulk-generation flow.
- `template-check` — validate a `.docx` template's `{{ }}` placeholders before
  uploading (mirrors the in-app brace validation).
