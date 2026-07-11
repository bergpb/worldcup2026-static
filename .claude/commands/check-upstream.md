# Check Upstream Changes

Fetch all commits by `Kingdoggydog` from the upstream repo and diff the current state of their key files against ours, then report what's new and worth porting.

## Steps

1. Fetch the list of commits authored by Kingdoggydog:
```bash
curl -s "https://api.github.com/repos/Kingdoggydog/worldcup2026/commits?per_page=100&author=Kingdoggydog" | python3 -c "
import json, sys
commits = json.load(sys.stdin)
for c in commits:
    sha = c['sha'][:7]
    msg = c['commit']['message'].split('\n')[0]
    date = c['commit']['committer']['date'][:10]
    print(f'{sha}  {date}  {msg}')
"
```

2. Fetch the current upstream versions of the key files and diff them against ours:
```bash
curl -s "https://raw.githubusercontent.com/Kingdoggydog/worldcup2026/main/index.html" > /tmp/upstream_index.html
curl -s "https://raw.githubusercontent.com/Kingdoggydog/worldcup2026/main/bracket.html" > /tmp/upstream_bracket.html
curl -s "https://raw.githubusercontent.com/Kingdoggydog/worldcup2026/main/groups.html" > /tmp/upstream_groups.html
```

3. For each file, produce a focused diff showing only JS and CSS changes (ignore structural differences from our partial system):
```bash
diff /tmp/upstream_index.html /home/bergpb/workspace/worldcup2026-static/index.html
diff /tmp/upstream_bracket.html /home/bergpb/workspace/worldcup2026-static/bracket.html
diff /tmp/upstream_groups.html /home/bergpb/workspace/worldcup2026-static/groups.html
```

4. Analyse the diffs and report:
   - **New features** we don't have yet
   - **Bug fixes** worth porting
   - **Things to skip** (test files, Google Analytics, GitHub Pages URLs, their CI workflow)

Focus on `index.html`, `bracket.html`, and `groups.html` — ignore `fetch-scores.yml`, `indextest.html`, `brackettest.html`, `dummy.json`, and any `data.json` changes.

Upstream repo: https://github.com/Kingdoggydog/worldcup2026
Our branch: `personal`
