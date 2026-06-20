# Session Wrap-Up

Update CLAUDE.md and project memory to reflect everything that changed this session.

## Steps

1. **Review the session's changes**
   ```bash
   git log --oneline origin/personal..HEAD
   git diff --stat origin/personal..HEAD
   ```
   If no upstream comparison exists, use `git log --oneline -10` and `git diff --stat HEAD~5`.

2. **Update `CLAUDE.md`** (checked into the repo) — add or correct:
   - New files in the Pages table (`match-details.json`, `group-winners.json`, etc.)
   - New fetcher outputs in the Data pipeline section
   - New JS globals, functions, or architectural patterns in the JS architecture section
   - New sections for pages that gained significant logic (e.g. `groups.html`)
   - New nginx location blocks
   - New known quirks or gotchas discovered this session
   - Remove anything that's now stale or wrong

3. **Update project memory** at `/home/bergpb/.claude/projects/-home-bergpb-workspace-worldcup2026-static/memory/project-worldcup2026.md`:
   - Keep it accurate and concise — it's loaded every session
   - Focus on things not obvious from reading the code: ordering constraints, gotchas, why decisions were made
   - Remove stale info (wrong API URLs, outdated function names, superseded patterns)
   - Update `MEMORY.md` index if the description line changed

4. **Commit CLAUDE.md** if it changed:
   ```bash
   git add CLAUDE.md && git commit -m "docs: update CLAUDE.md with session changes"
   ```
   Do NOT commit the memory files — they live outside the repo.

5. **Report** what was updated and what was skipped (and why).

## What to capture vs skip

**Capture:**
- New data files the fetcher generates and nginx serves
- New JS functions at global scope or critical ordering constraints
- New features with non-obvious implementation details
- Bugs found and their root causes (as gotchas)
- Infrastructure changes (nginx rules, Docker behaviour)

**Skip:**
- Ephemeral task state or in-progress work
- Things already documented in CLAUDE.md
- Code patterns obvious from reading the source
- Git history (belongs in commit messages, not docs)
