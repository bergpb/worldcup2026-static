'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const path = require('node:path');
const { extractSymbols } = require('./helpers/extract.js');

const code = extractSymbols(
  path.join(__dirname, '..', '_partials', 'common.js'),
  ['API_NAME_MAP', 'normalise', 'FLAGS']
);

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(code, sandbox);
const { normalise, FLAGS } = sandbox;

test('normalise() maps known API name variants to canonical display name', () => {
  assert.equal(normalise('Korea Republic'), 'South Korea');
  assert.equal(normalise('United States'), 'USA');
  assert.equal(normalise('Türkiye'), 'Turkiye');
  assert.equal(normalise('Turkey'), 'Turkiye');
  assert.equal(normalise('Bosnia-Herz'), 'Bosnia');
  assert.equal(normalise('Bosnia-Herzegovina'), 'Bosnia');
  assert.equal(normalise('Bosnia & Herz.'), 'Bosnia');
  assert.equal(normalise('Curaçao'), 'Curacao');
});

test('normalise() passes through names with no known alias', () => {
  assert.equal(normalise('Brazil'), 'Brazil');
  assert.equal(normalise('Netherlands'), 'Netherlands');
});

test('FLAGS has a code for every alias normalise() can produce', () => {
  const canonicalNames = new Set(Object.values(sandbox.API_NAME_MAP));
  for (const name of canonicalNames) {
    assert.ok(FLAGS[name], `expected FLAGS to have a code for canonical name "${name}"`);
  }
});

test('FLAGS covers raw API variants directly (scorers.html looks these up without normalising)', () => {
  // Note: 'Türkiye' (accented) is not among these - every page that can see it
  // runs it through normalise() first. Only scorers.html looks up FLAGS directly.
  for (const variant of ['Curaçao', 'Turkey', 'Korea Republic', 'United States', 'Bosnia-Herzegovina']) {
    assert.ok(FLAGS[variant], `expected FLAGS to have a code for "${variant}"`);
  }
});
