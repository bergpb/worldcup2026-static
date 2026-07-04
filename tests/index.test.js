'use strict';
const test = require('node:test');
const assert = require('node:assert');
const vm = require('node:vm');
const path = require('node:path');
const { extractSymbols } = require('./helpers/extract.js');

const getScoreCode = extractSymbols(
  path.join(__dirname, '..', 'index.html'),
  ['getScore']
);

function makeSandbox() {
  const sandbox = {
    _lang: 'en',
    LANGS: { en: { ht_label: 'HT', live_label: 'LIVE' } },
    scoreMap: {},
    scoreMapById: {},
  };
  vm.createContext(sandbox);
  vm.runInContext(getScoreCode, sandbox);
  return sandbox;
}

const commonCode = extractSymbols(
  path.join(__dirname, '..', '_partials', 'common.js'),
  ['API_NAME_MAP', 'normalise']
);
const buildLiveCardEventsCode = extractSymbols(
  path.join(__dirname, '..', 'index.html'),
  ['buildLiveCardEvents']
);

function makeLiveCardSandbox(matchDetails) {
  const sandbox = {
    document: { body: { classList: { contains: () => false } } },
    matchDetails,
  };
  vm.createContext(sandbox);
  vm.runInContext(`${commonCode}\n${buildLiveCardEventsCode}`, sandbox);
  return sandbox;
}

test('getScore: FINISHED regular-time match carries no AET/PSO duration', () => {
  const sandbox = makeSandbox();
  sandbox.scoreMap['Brazil|Argentina'] = { status: 'FINISHED', home: 2, away: 1, duration: 'REGULAR' };
  const score = sandbox.getScore('Brazil v Argentina', null);
  assert.equal(score.cls, 'score-ft');
  assert.equal(score.duration, 'REGULAR');
});

test('getScore: FINISHED extra-time match reports duration EXTRA_TIME, not stuck live', () => {
  // Regression for db757db: ESPN's AET status used to fall through to a
  // status the frontend didn't recognise as terminal, so getScore() kept
  // treating the match as unresolved instead of a finished score.
  const sandbox = makeSandbox();
  sandbox.scoreMap['Belgium|Senegal'] = { status: 'FINISHED', home: 2, away: 2, duration: 'EXTRA_TIME' };
  const score = sandbox.getScore('Belgium v Senegal', null);
  assert.equal(score.cls, 'score-ft');
  assert.equal(score.duration, 'EXTRA_TIME');
  assert.equal(score.home, 2);
  assert.equal(score.away, 2);
});

test('getScore: IN_PLAY match returns a live score with minute label', () => {
  const sandbox = makeSandbox();
  sandbox.scoreMap['France|Morocco'] = { status: 'IN_PLAY', home: 1, away: 0, minute: 63 };
  const score = sandbox.getScore('France v Morocco', null);
  assert.equal(score.cls, 'score-live');
  assert.equal(score.minute, "63'");
});

test('getScore: PAUSED match uses the half-time label', () => {
  const sandbox = makeSandbox();
  sandbox.scoreMap['Japan|Netherlands'] = { status: 'PAUSED', home: 1, away: 1 };
  const score = sandbox.getScore('Japan v Netherlands', null);
  assert.equal(score.cls, 'score-live');
  assert.equal(score.label, 'HT');
});

test('getScore: unresolved match with no score data returns null', () => {
  const sandbox = makeSandbox();
  const score = sandbox.getScore('Spain v Italy', null);
  assert.equal(score, null);
});

test('getScore: knockout matches resolve by ESPN id before falling back to name lookup', () => {
  const sandbox = makeSandbox();
  sandbox.scoreMapById[537417] = { status: 'FINISHED', home: 3, away: 1, duration: 'PENALTY_SHOOTOUT' };
  const score = sandbox.getScore('Win Group A v 2nd Group B', 537417);
  assert.equal(score.duration, 'PENALTY_SHOOTOUT');
});

test('getScore: "Bosnia & Herz." display name maps to the API\'s "Bosnia" score key', () => {
  const sandbox = makeSandbox();
  sandbox.scoreMap['Bosnia|Austria'] = { status: 'FINISHED', home: 1, away: 0, duration: 'REGULAR' };
  const score = sandbox.getScore('Bosnia & Herz. v Austria', null);
  assert.equal(score.home, 1);
});

test('buildLiveCardEvents: own goal is credited to the benefiting team, not flipped', () => {
  // Regression: g.team on an own-goal keyEvent is ESPN's credited (benefiting)
  // side already. A previous version of this code flipped it, assuming it was
  // the scorer's own team - which moved the benefiting team's goal into the
  // opponent's column. Verified live: Argentina 3-2 Cape Verde, where a Cape
  // Verde player's own goal raised Argentina's own tally (team.name: "Argentina").
  const sandbox = makeLiveCardSandbox({
    '760500': {
      status: 'IN_PLAY',
      goals: [
        { minute: 29, type: null, scorer: { name: 'Lionel Messi' }, team: { name: 'Argentina' } },
        { minute: 92, type: null, scorer: { name: 'Lisandro Martinez' }, team: { name: 'Argentina' } },
        { minute: 111, type: 'OWN', scorer: { name: 'Diney Borges' }, team: { name: 'Argentina' } },
        { minute: 59, type: null, scorer: { name: 'Deroy Duarte' }, team: { name: 'Cape Verde' } },
      ],
      bookings: [],
    },
  });
  const html = sandbox.buildLiveCardEvents({
    id: 760500,
    homeTeam: { name: 'Argentina' },
    awayTeam: { name: 'Cape Verde' },
  });
  const [homeCol, awayCol] = html.split('width:64px;flex-shrink:0;');
  assert.match(homeCol, /Lionel Messi/);
  assert.match(homeCol, /Lisandro Martinez/);
  assert.match(homeCol, /Diney Borges \(OG\)/);
  assert.doesNotMatch(awayCol, /Diney Borges/);
  assert.match(awayCol, /Deroy Duarte/);
});
