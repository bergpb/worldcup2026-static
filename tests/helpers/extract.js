'use strict';
const fs = require('node:fs');

// Pulls named top-level `function foo(...) {...}` or `const foo = {...|[...]};`
// declarations out of a source file by brace/bracket matching, so tests can
// load just the pure logic they need without executing page/DOM code.
function extractSymbols(filePath, names) {
  const src = fs.readFileSync(filePath, 'utf8');
  const decls = names.map(name => extractOne(src, name)).join('\n\n');
  // top-level `const`/`function` in a vm context don't attach to the context
  // object the way `var` does, so re-expose everything the caller asked for
  const exposes = names.map(name => `globalThis.${name} = ${name};`).join('\n');
  return `${decls}\n\n${exposes}`;
}

function extractOne(src, name) {
  const decl = src.match(new RegExp(`(function\\s+${name}\\s*\\(|const\\s+${name}\\s*=)`));
  if (!decl) throw new Error(`Symbol "${name}" not found`);
  const start = decl.index;

  // first '{' or '[' after the declaration keyword is the body/literal we match braces from
  let openIdx = start;
  while (openIdx < src.length && src[openIdx] !== '{' && src[openIdx] !== '[') openIdx++;
  const openChar = src[openIdx];
  const closeChar = openChar === '{' ? '}' : ']';

  let depth = 0, i = openIdx;
  for (; i < src.length; i++) {
    if (src[i] === openChar) depth++;
    else if (src[i] === closeChar) {
      depth--;
      if (depth === 0) break;
    }
  }
  if (depth !== 0) throw new Error(`Unbalanced braces extracting "${name}"`);

  // include trailing semicolon for const declarations
  let end = i + 1;
  if (src[end] === ';') end++;

  return src.slice(start, end);
}

module.exports = { extractSymbols };
