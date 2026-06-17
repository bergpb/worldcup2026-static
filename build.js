const fs = require('fs');
const path = require('path');

const PAGES = [
  { file: 'index.html',   nav: 'schedule' },
  { file: 'groups.html',  nav: 'groups'   },
  { file: 'bracket.html', nav: 'knockout' },
  { file: 'scorers.html', nav: 'scorers'  },
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

for (const { file, nav } of PAGES) {
  let html = fs.readFileSync(file, 'utf8');

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

  fs.writeFileSync(file, html);
  console.log(`✓ ${file}`);
}

console.log('Build complete.');
