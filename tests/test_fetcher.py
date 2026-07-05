import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import fetcher


class StatusMapTests(unittest.TestCase):
    """Regression coverage for db757db: ESPN's AET/in-progress statuses were
    missing from STATUS_MAP, defaulting to TIMED. The live-state guard then
    mistook that for a transient glitch and kept matches stuck on IN_PLAY
    forever once they were decided in extra time."""

    def test_final_aet_maps_to_finished(self):
        self.assertEqual(fetcher.STATUS_MAP['STATUS_FINAL_AET'], 'FINISHED')

    def test_final_aet_duration_is_extra_time(self):
        self.assertEqual(fetcher.DURATION_MAP['STATUS_FINAL_AET'], 'EXTRA_TIME')

    def test_in_progress_maps_to_in_play(self):
        self.assertEqual(fetcher.STATUS_MAP['STATUS_IN_PROGRESS'], 'IN_PLAY')

    def test_final_pen_maps_to_finished_and_penalty_shootout(self):
        self.assertEqual(fetcher.STATUS_MAP['STATUS_FINAL_PEN'], 'FINISHED')
        self.assertEqual(fetcher.DURATION_MAP['STATUS_FINAL_PEN'], 'PENALTY_SHOOTOUT')

    def test_overtime_maps_to_in_play_and_extra_time(self):
        # ESPN uses STATUS_OVERTIME (not STATUS_EXTRA_TIME) for at least some
        # live knockout matches. Missing this entry caused the live-state guard
        # to freeze a match's score/goals at its pre-extra-time state for the
        # entire duration of extra time (Argentina 1-1 Cape Verde stuck while
        # the real match had gone to 2-2 with two more goals scored in ET).
        self.assertEqual(fetcher.STATUS_MAP['STATUS_OVERTIME'], 'IN_PLAY')
        self.assertEqual(fetcher.DURATION_MAP['STATUS_OVERTIME'], 'EXTRA_TIME')
        self.assertEqual(fetcher.PERIOD_MAP['STATUS_OVERTIME'], 'EXTRA_TIME')

    def test_halftime_et_maps_to_paused_and_extra_time(self):
        # ESPN's break between extra-time halves came through as STATUS_HALFTIME_ET,
        # a third distinct string (alongside STATUS_EXTRA_TIME_HALF_TIME) for the
        # same real-world event. Missing this one dropped the match straight to
        # null scores because the fetcher's live-state cache had just been reset
        # by a container restart, so there was no stale state to fall back on.
        self.assertEqual(fetcher.STATUS_MAP['STATUS_HALFTIME_ET'], 'PAUSED')
        self.assertEqual(fetcher.DURATION_MAP['STATUS_HALFTIME_ET'], 'EXTRA_TIME')
        self.assertEqual(fetcher.PERIOD_MAP['STATUS_HALFTIME_ET'], 'EXTRA_TIME')

    def test_normal_full_time_has_no_duration_override(self):
        # Regular-time finishes should NOT appear in DURATION_MAP - the frontend
        # treats a missing entry as "REGULAR" and only shows AET/PSO badges
        # when the map says otherwise.
        self.assertNotIn('STATUS_FULL_TIME', fetcher.DURATION_MAP)
        self.assertNotIn('STATUS_FINAL', fetcher.DURATION_MAP)


class StateFallbackTests(unittest.TestCase):
    """Regression coverage for the STATUS_HALFTIME_ET incident: an unrecognised
    ESPN status name used to default straight to TIMED (null scores). Now it
    falls back to ESPN's generic lifecycle state (type.state: in/post/pre) so
    a live match stays live even before we've explicitly mapped its exact
    status string."""

    def test_in_state_falls_back_to_in_play(self):
        self.assertEqual(fetcher._STATE_FALLBACK['in'], 'IN_PLAY')

    def test_post_state_falls_back_to_finished(self):
        self.assertEqual(fetcher._STATE_FALLBACK['post'], 'FINISHED')

    def test_pre_state_falls_back_to_timed(self):
        self.assertEqual(fetcher._STATE_FALLBACK['pre'], 'TIMED')


class DisplayNameTests(unittest.TestCase):
    def test_known_aliases_normalise(self):
        self.assertEqual(fetcher._display('Korea Republic'), 'South Korea')
        self.assertEqual(fetcher._display('Türkiye'), 'Turkiye')
        self.assertEqual(fetcher._display('Turkey'), 'Turkiye')
        self.assertEqual(fetcher._display('Bosnia-Herz'), 'Bosnia')

    def test_unknown_name_passes_through(self):
        self.assertEqual(fetcher._display('Brazil'), 'Brazil')


class ParseEventClockTests(unittest.TestCase):
    def test_plain_minute(self):
        self.assertEqual(fetcher.parse_event_clock("23'"), (23, None))

    def test_injury_time(self):
        self.assertEqual(fetcher.parse_event_clock("45+2'"), (45, 2))

    def test_missing_value(self):
        self.assertEqual(fetcher.parse_event_clock(""), (None, None))
        self.assertEqual(fetcher.parse_event_clock(None), (None, None))


class NormalizeDateTests(unittest.TestCase):
    def test_adds_missing_seconds(self):
        self.assertEqual(fetcher.normalize_date('2026-06-11T19:00Z'), '2026-06-11T19:00:00Z')

    def test_leaves_full_timestamp_untouched(self):
        self.assertEqual(fetcher.normalize_date('2026-06-11T19:00:00Z'), '2026-06-11T19:00:00Z')


class BuildDetailEntryTests(unittest.TestCase):
    def test_own_goal_is_flagged_and_side_not_flipped_here(self):
        # own-goal side-flipping happens in the frontend display layer, not here -
        # this just verifies the raw event is typed correctly as OWN.
        events = [{
            'scoringPlay': True,
            'type': {'type': 'own-goal'},
            'participants': [{'athlete': {'displayName': 'J. Player'}}],
            'clock': {'displayValue': "60'"},
            'team': {'displayName': 'Brazil'},
        }]
        entry = fetcher.build_detail_entry('FINISHED', 1, 0, events)
        self.assertEqual(entry['goals'][0]['type'], 'OWN')
        self.assertEqual(entry['goals'][0]['minute'], 60)

    def test_yellow_red_card_distinct_from_red(self):
        events = [
            {'scoringPlay': False, 'type': {'type': 'yellow-red-card'},
             'participants': [{'athlete': {'displayName': 'A'}}],
             'clock': {'displayValue': "80'"}, 'team': {'displayName': 'Spain'}},
            {'scoringPlay': False, 'type': {'type': 'red-card'},
             'participants': [{'athlete': {'displayName': 'B'}}],
             'clock': {'displayValue': "85'"}, 'team': {'displayName': 'Spain'}},
        ]
        entry = fetcher.build_detail_entry('FINISHED', 0, 0, events)
        cards = {b['player']['name']: b['card'] for b in entry['bookings']}
        self.assertEqual(cards['A'], 'YELLOW_RED')
        self.assertEqual(cards['B'], 'RED')

    def test_penalty_shootout_score_included_only_when_provided(self):
        entry = fetcher.build_detail_entry('FINISHED', 1, 1, [], pen_home=4, pen_away=3)
        self.assertEqual(entry['score']['penShootout'], {'home': 4, 'away': 3})

        entry_no_pens = fetcher.build_detail_entry('FINISHED', 2, 0, [])
        self.assertNotIn('penShootout', entry_no_pens['score'])


if __name__ == '__main__':
    unittest.main()
