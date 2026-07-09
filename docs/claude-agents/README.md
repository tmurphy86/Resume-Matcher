# Staged agent definitions

Cowork can't write into `.claude/` directly. Move these into place once:

```bash
mkdir -p .claude/agents && cp docs/claude-agents/*.agent.md .claude/agents/ && cd .claude/agents && for f in *.agent.md; do mv "$f" "${f%.agent.md}.md"; done
```

Then verify with `/agents` inside Claude Code.
