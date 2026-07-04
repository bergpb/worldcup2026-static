'use strict';
const test = require('node:test');
const assert = require('node:assert');
const vm = require('node:vm');
const path = require('node:path');
const { extractSymbols } = require('./helpers/extract.js');

const code = extractSymbols(path.join(__dirname, '..', 'bracket.html'), ['scoreSuffix']);
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(code, sandbox);
const { scoreSuffix } = sandbox;

test('scoreSuffix: penalty shootout finish', () => {
  assert.equal(scoreSuffix({ score: { duration: 'PENALTY_SHOOTOUT' } }), 'p');
});

test('scoreSuffix: extra-time finish', () => {
  assert.equal(scoreSuffix({ score: { duration: 'EXTRA_TIME' } }), 'aet');
});

test('scoreSuffix: regular-time finish has no suffix', () => {
  assert.equal(scoreSuffix({ score: { duration: 'REGULAR' } }), '');
});

test('scoreSuffix: missing duration (not yet played) has no suffix', () => {
  assert.equal(scoreSuffix({ score: {} }), '');
  assert.equal(scoreSuffix({}), '');
});
