let _lang = 'en';
try { _lang = localStorage.getItem('wc2026_lang') || 'en'; } catch(e) {}

function t(key) {
  return (LANGS[_lang] || LANGS.en)[key] ?? LANGS.en[key] ?? key;
}
function teamName(n) { return LANGS[_lang]?.teams?.[n] ?? n; }

// Maps API name variants (ESPN shortDisplayName / other endpoints) to our canonical display name
const API_NAME_MAP = {
  'Korea Republic':'South Korea', 'United States':'USA',
  'Bosnia-H.':'Bosnia','Bosnia-Herzegovina':'Bosnia','Bosnia & Herz.':'Bosnia',
  'Curaçao':'Curacao', 'Turkey':'Turkiye', 'Türkiye':'Turkiye',
  'Bosnia-Herz':'Bosnia',
  'Cape Verde Islands':'Cape Verde', 'Cape Verde':'Cape Verde',
  'Congo DR':'Congo DR', 'Ivory Coast':'Ivory Coast',
};
function normalise(name) {
  return API_NAME_MAP[name] || name;
}

// Country name -> flagcdn.com country code. Superset of every alias/variant
// each page has historically needed (raw API names, canonical names, etc.)
const FLAGS = {
  'Algeria':'dz','Argentina':'ar','Australia':'au','Austria':'at',
  'Belgium':'be','Bosnia':'ba','Bosnia-H.':'ba','Bosnia & Herz.':'ba','Bosnia-Herzegovina':'ba','Brazil':'br',
  'Canada':'ca','Cape Verde':'cv','Colombia':'co','Congo DR':'cd',
  'Croatia':'hr','Curacao':'cw','Curaçao':'cw','Czechia':'cz','Ecuador':'ec',
  'Egypt':'eg','England':'gb-eng','France':'fr','Germany':'de',
  'Ghana':'gh','Haiti':'ht','Iran':'ir','Iraq':'iq',
  'Ivory Coast':'ci','Japan':'jp','Jordan':'jo','Korea Republic':'kr','Mexico':'mx',
  'Morocco':'ma','Netherlands':'nl','New Zealand':'nz','Norway':'no',
  'Panama':'pa','Paraguay':'py','Portugal':'pt','Qatar':'qa',
  'Saudi Arabia':'sa','Scotland':'gb-sct','Senegal':'sn','S. Korea':'kr',
  'South Africa':'za','South Korea':'kr','Spain':'es','Sweden':'se','Switzerland':'ch','Tunisia':'tn',
  'Turkiye':'tr','Turkey':'tr','Uruguay':'uy','USA':'us','United States':'us','Uzbekistan':'uz',
};

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