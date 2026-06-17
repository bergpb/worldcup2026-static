const fs = require('fs');
const path = require('path');

const PAGES = [
  { file: 'index.html',   nav: 'schedule', canonical: './',            title: 'World Cup 2026 Schedule - Live Scores & Local Times',   description: 'All 104 matches with live scores, standings and bracket. Times in your timezone. Free, no ads.'            },
  { file: 'groups.html',  nav: 'groups',   canonical: 'groups.html',   title: 'World Cup 2026 Group Standings - Live & Updated',        description: 'Live standings updated as matches are played. All 12 groups with FIFA tiebreaker logic.'                   },
  { file: 'bracket.html', nav: 'knockout', canonical: 'bracket.html',  title: 'World Cup 2026 Knockout Bracket',                        description: 'Full bracket from Round of 32 to the Final. Match times in your local timezone.'                           },
  { file: 'scorers.html', nav: 'scorers',  canonical: 'scorers.html',  title: 'World Cup 2026 Top Scorers - Golden Boot Race',          description: 'FIFA World Cup 2026 Golden Boot race - top scorers updated live throughout the tournament.'                 },
];

function readPartial(name) {
  return fs.readFileSync(path.join('_partials', name), 'utf8').trimEnd();
}

function inject(html, partialName, content) {
  const re = new RegExp(
    `(<!-- partial:${partialName} -->)[\\s\\S]*?(<!-- /partial:${partialName} -->)`,
    'g'
  );
  if (!re.test(html)) return html;
  return html.replace(
    new RegExp(`(<!-- partial:${partialName} -->)[\\s\\S]*?(<!-- /partial:${partialName} -->)`, 'g'),
    `$1\n${content}\n$2`
  );
}

const CHECK = process.argv.includes('--check');
let stale = false;

for (const { file, nav, canonical, title, description } of PAGES) {
  const before = fs.readFileSync(file, 'utf8');
  let html = before;

  // Head: inject with per-page variable substitution
  let headHtml = readPartial('head.html')
    .replace(/\{\{PAGE_TITLE\}\}/g, title)
    .replace(/\{\{PAGE_DESCRIPTION\}\}/g, description)
    .replace(/\{\{PAGE_CANONICAL\}\}/g, canonical);
  html = inject(html, 'head', headHtml);

  // Shared LANGS_COMMON (must come before page LANGS)
  html = inject(html, 'langs', readPartial('langs.html'));

  // Nav: inject and mark active page
  let navHtml = readPartial('nav.html');
  navHtml = navHtml.replace(
    `class="nav-btn" id="nav-${nav}"`,
    `class="nav-btn active" id="nav-${nav}"`
  );
  html = inject(html, 'nav', navHtml);

  // Timezone options (only pages that have the marker)
  html = inject(html, 'tz-options', readPartial('tz-options.html'));

  // Common JS
  html = inject(html, 'common-js', readPartial('common.js'));

  if (CHECK) {
    if (html !== before) { console.error(`✗ ${file} is stale — run node build.js`); stale = true; }
    else console.log(`✓ ${file}`);
  } else {
    fs.writeFileSync(file, html);
    console.log(`✓ ${file}`);
  }
}

if (CHECK && stale) process.exit(1);
console.log('Build complete.');
