'use strict';
const test = require('node:test');
// Plain (non-/strict) assert: objects/arrays produced inside the vm sandbox are
// cross-realm, so deepStrictEqual's prototype check would false-fail on them.
const assert = require('node:assert');
const vm = require('node:vm');
const path = require('node:path');
const { extractSymbols } = require('./helpers/extract.js');

const commonCode = extractSymbols(
  path.join(__dirname, '..', '_partials', 'common.js'),
  ['API_NAME_MAP', 'normalise']
);
const groupsCode = extractSymbols(
  path.join(__dirname, '..', 'groups.html'),
  [
    'GROUPS', 'GROUP_FIXTURES', 'OUTCOMES',
    'buildGroupStatsFromResults', 'buildResultsLookup', 'getGroupFixtureStatus',
    'allTeamsPlayedTwo', 'generateScenarios', 'calcGroupBadges',
    'h2hStats', 'sortTeams', 'calcStandings',
  ]
);

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(commonCode, sandbox);
vm.runInContext(groupsCode, sandbox);
const { calcGroupBadges, sortTeams, GROUPS } = sandbox;

// Build a finished-results map the same shape calcStandings() produces,
// keyed "grp|home|away" -> {hg, ag}
function results(grp, entries) {
  const map = {};
  entries.forEach(([home, away, hg, ag]) => { map[`${grp}|${home}|${away}`] = { hg, ag }; });
  return map;
}

test('sortTeams ranks by points, then head-to-head, then goal difference', () => {
  const teams = ['Mexico', 'South Korea', 'South Africa', 'Czechia'];
  const stats = {
    Mexico:       { p: 3, w: 2, d: 1, l: 0, gf: 5, ga: 2, pts: 7 },
    'South Korea':{ p: 3, w: 1, d: 1, l: 1, gf: 3, ga: 3, pts: 4 },
    'South Africa':{ p: 3, w: 1, d: 1, l: 1, gf: 2, ga: 3, pts: 4 },
    Czechia:      { p: 3, w: 0, d: 1, l: 2, gf: 1, ga: 5, pts: 1 },
  };
  // South Korea beat South Africa head-to-head 2-1 despite identical overall points
  const h2h = results('A', [['South Korea', 'South Africa', 2, 1]]);
  const sorted = sortTeams(teams, 'A', stats, h2h);
  assert.deepEqual(sorted, ['Mexico', 'South Korea', 'South Africa', 'Czechia']);
});

test('calcGroupBadges: team mathematically eliminated after 2 group-stage losses with no path to 3rd', () => {
  // Group L: England, Croatia, Ghana, Panama - each plays 3 games.
  // Simulate Panama having lost its first two with a wide enough goal-difference
  // gap that no plausible remaining result keeps them out of last place.
  // Result keys must use each fixture's actual home/away order from GROUP_FIXTURES
  const finished = results('L', [
    ['England', 'Croatia', 3, 0],
    ['Ghana', 'Panama', 3, 0],
    ['England', 'Ghana', 4, 0],
    ['Panama', 'Croatia', 0, 3],
  ]);
  const badges = calcGroupBadges('L', GROUPS.L, finished);
  assert.equal(badges.England, '1');
  assert.equal(badges.Panama, 'E');
});

test('calcGroupBadges: returns {} when fewer than all teams have played 2 games', () => {
  const finished = results('A', [['Mexico', 'South Africa', 1, 0]]);
  const badges = calcGroupBadges('A', GROUPS.A, finished);
  assert.deepEqual(badges, {});
});

test('calcGroupBadges: qualified (Q) badge when team can only finish 1st or 2nd', () => {
  const finished = results('A', [
    ['Mexico', 'South Africa', 5, 0],
    ['South Korea', 'Czechia', 5, 0],
    ['Mexico', 'South Korea', 5, 0],
    ['Czechia', 'South Africa', 0, 0],
  ]);
  // Mexico has beaten both South Africa and South Korea by 5 goals each with one
  // game left (vs Czechia) - cannot drop below 2nd regardless of that result.
  const badges = calcGroupBadges('A', GROUPS.A, finished);
  assert.ok(badges.Mexico === '1' || badges.Mexico === 'Q');
});
