const fs = require('fs');
const path = require('path');

const DIST = 'dist';
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

// --strip: empty all partial markers in source files (run before committing)
if (process.argv.includes('--strip')) {
  for (const { file } of PAGES) {
    let html = fs.readFileSync(file, 'utf8');
    html = html.replace(
      /<!-- partial:[\w-]+ -->[\s\S]*?<!-- \/partial:[\w-]+ -->/g,
      m => m.replace(/<!-- partial:([\w-]+) -->[\s\S]*?<!-- \/partial:([\w-]+) -->/, '<!-- partial:$1 -->\n<!-- /partial:$2 -->')
    );
    fs.writeFileSync(file, html);
    console.log(`stripped ${file}`);
  }
  console.log('Strip complete.');
  process.exit(0);
}

const CHECK = process.argv.includes('--check');
let stale = false;

if (!CHECK) fs.mkdirSync(DIST, { recursive: true });

for (const { file, nav, canonical, title, description } of PAGES) {
  const src = fs.readFileSync(file, 'utf8');
  let html = src;

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

  // Footer
  html = inject(html, 'footer', readPartial('footer.html'));

  // JSON-LD structured data (index.html only)
  html = inject(html, 'jsonld', readPartial('jsonld.html'));

  if (CHECK) {
    const built = fs.existsSync(path.join(DIST, file)) ? fs.readFileSync(path.join(DIST, file), 'utf8') : null;
    if (html !== built) { console.error(`✗ ${file} is stale — run node build.js`); stale = true; }
    else console.log(`✓ ${file}`);
  } else {
    fs.writeFileSync(path.join(DIST, file), html);
    console.log(`✓ ${file}`);
  }
}

if (CHECK && stale) process.exit(1);

// Copy static assets to dist/ so it's fully self-contained
if (!CHECK) {
  const STATIC_FILES = ['styles.css', 'manifest.json', 'favicon.ico', 'sw.js', 'sitemap.xml', 'data.json', 'scorers.json'];
  for (const f of STATIC_FILES) {
    if (fs.existsSync(f)) fs.copyFileSync(f, path.join(DIST, f));
  }
  function copyDir(src, dest) {
    fs.mkdirSync(dest, { recursive: true });
    for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
      const s = path.join(src, entry.name), d = path.join(dest, entry.name);
      entry.isDirectory() ? copyDir(s, d) : fs.copyFileSync(s, d);
    }
  }
  if (fs.existsSync('icons')) copyDir('icons', path.join(DIST, 'icons'));
}

console.log('Build complete.');
