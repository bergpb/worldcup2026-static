import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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

    def test_normal_full_time_has_no_duration_override(self):
        # Regular-time finishes should NOT appear in DURATION_MAP - the frontend
        # treats a missing entry as "REGULAR" and only shows AET/PSO badges
        # when the map says otherwise.
        self.assertNotIn('STATUS_FULL_TIME', fetcher.DURATION_MAP)
        self.assertNotIn('STATUS_FINAL', fetcher.DURATION_MAP)


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
