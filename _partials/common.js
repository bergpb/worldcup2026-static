let _lang = 'en';
try { _lang = localStorage.getItem('wc2026_lang') || 'en'; } catch(e) {}

function t(key) {
  return (LANGS[_lang] || LANGS.en)[key] ?? LANGS.en[key] ?? key;
}
function teamName(n) { return LANGS[_lang]?.teams?.[n] ?? n; }

const LANG_FLAGS  = { en:'us', pt:'br', es:'es' };
const LANG_LABELS = { en:'EN', pt:'PT', es:'ES' };
function langBtnHTML(lang) {
  const code  = LANG_FLAGS[lang];
  const label = LANG_LABELS[lang];
  return `<img src="https://flagcdn.com/w20/${code}.png" alt="${label}" style="width:18px;height:13px;object-fit:cover;border-radius:2px;vertical-align:middle;margin-right:5px;">${label}`;
}

function cycleLang() {
  const order = ['en','pt','es'];
  _lang = order[(order.indexOf(_lang) + 1) % order.length];
  try { localStorage.setItem('wc2026_lang', _lang); } catch(e) {}
  applyLang();
  if (typeof window._onLangChange === 'function') window._onLangChange();
}

function shareApp() {
  const d = { title: 'FIFA World Cup 2026', url: location.href };
  if (navigator.share) navigator.share(d).catch(() => {});
  else navigator.clipboard.writeText(location.href).catch(() => {});
}