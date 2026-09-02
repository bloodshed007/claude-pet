"""Unit tests for the platform-independent Agent Pet state model."""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent_pet_state import (DONE_FADE_MS, Session, Tracker, aggregate, format_age,
                          latest_activity_ms, parse_line, sessions, state_dir)

NOW = 1_700_000_000_000


class StateTestCase(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="pipet-test-")
        os.makedirs(state_dir(self.home))

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def write(self, key, line):
        with open(os.path.join(state_dir(self.home), key + ".txt"), "w",
                  encoding="utf-8") as f:
            f.write(line)

    def sess(self, now=NOW):
        return sessions(self.home, now_ms=now)


class TestParse(StateTestCase):
    def test_parses_all_v2_fields(self):
        rec = parse_line("needs-you|123|proj|codex|hub:proj|Should I ship it?")
        self.assertEqual(rec["state"], "needs-you")
        self.assertEqual(rec["ts"], 123)
        self.assertEqual(rec["name"], "proj")
        self.assertEqual(rec["agent"], "codex")
        self.assertEqual(rec["window"], "hub:proj")
        self.assertEqual(rec["hint"], "Should I ship it?")

    def test_accepts_legacy_three_field_line(self):
        rec = parse_line("working|999|p50", key="01a05-abc")
        self.assertEqual((rec["state"], rec["ts"], rec["name"]), ("working", 999, "p50"))
        self.assertEqual((rec["window"], rec["hint"]), ("", ""))
        self.assertEqual(rec["agent"], "pi")

    def test_infers_agent_from_filename_when_field_absent(self):
        self.assertEqual(parse_line("done|1|x", key="claude-abc")["agent"], "claude")
        self.assertEqual(parse_line("done|1|x", key="codex-abc")["agent"], "codex")

    def test_ignores_extra_future_fields(self):
        rec = parse_line("done|5|n|pi|hub:n|hi|v3-extra|more")
        self.assertEqual(rec["hint"], "hi")
        self.assertEqual(rec["name"], "n")

    def test_bad_state_and_timestamp_degrade_to_defaults(self):
        rec = parse_line("weird|nope|n")
        self.assertEqual((rec["state"], rec["ts"]), ("idle", 0))

    def test_hint_is_capped_at_80_chars(self):
        self.assertEqual(len(parse_line("done|1|n|pi||" + "z" * 200)["hint"]), 80)


class TestSessions(StateTestCase):
    def test_priority_order_and_recency(self):
        self.write("a", "done|%d|a|pi||" % NOW)
        self.write("b", "working|%d|b|pi||" % NOW)
        self.write("c", "needs-you|%d|c|claude|hub:c|Which one?" % NOW)
        self.write("d", "idle|%d|d|pi||" % NOW)
        got = [s.name for s in self.sess()]
        self.assertEqual(got, ["c", "b", "a", "d"])

    def test_done_fades_to_idle_after_the_fade_window(self):
        self.write("a", "done|%d|a|pi||" % (NOW - DONE_FADE_MS - 1))
        s = self.sess()[0]
        self.assertEqual(s.state, "idle")
        self.assertEqual(s.raw_state, "done")

    def test_ttl_drops_stale_files(self):
        self.write("old", "working|%d|old|pi||" % (NOW - 10 * 60 * 60 * 1000))
        self.assertEqual(self.sess(), [])

    def test_duplicate_names_get_suffixes_oldest_keeps_plain(self):
        self.write("a", "idle|%d|Project|pi||" % (NOW - 5000))
        self.write("b", "idle|%d|Project|pi||" % (NOW - 1000))
        self.write("c", "idle|%d|Project|pi||" % NOW)
        got = sorted(s.display for s in self.sess())
        self.assertEqual(got, ["Project", "Project #2", "Project #3"])

    def test_clickable_only_when_window_present(self):
        self.write("a", "idle|%d|a|pi|hub:a|" % NOW)
        self.write("b", "idle|%d|b|pi||" % NOW)
        flags = {s.name: s.clickable for s in self.sess()}
        self.assertEqual(flags, {"a": True, "b": False})

    def test_glyph_per_agent(self):
        self.write("claude-1", "idle|%d|a|claude||" % NOW)
        self.write("codex-1", "idle|%d|b|codex||" % NOW)
        self.write("p1", "idle|%d|c|pi||" % NOW)
        glyphs = {s.name: s.glyph for s in self.sess()}
        self.assertEqual(glyphs, {"a": "c·", "b": "x·", "c": "π·"})

    def test_missing_dir_is_empty_not_an_error(self):
        self.assertEqual(sessions(os.path.join(self.home, "nope"), now_ms=NOW), [])


class TestAggregate(StateTestCase):
    def test_highest_priority_state_wins(self):
        self.write("a", "working|%d|a|pi||" % NOW)
        self.write("b", "needs-you|%d|b|pi||" % NOW)
        self.assertEqual(aggregate(self.home, now_ms=NOW), ("needs-you", 1, ["b"]))

    def test_counts_and_names_of_the_winning_bucket(self):
        self.write("a", "working|%d|a|pi||" % NOW)
        self.write("b", "working|%d|b|pi||" % NOW)
        self.write("c", "idle|%d|c|pi||" % NOW)
        self.assertEqual(aggregate(self.home, now_ms=NOW), ("working", 2, ["a", "b"]))

    def test_empty_dir_is_idle(self):
        self.assertEqual(aggregate(self.home, now_ms=NOW), ("idle", 0, []))

    def test_latest_activity_is_the_newest_timestamp(self):
        self.write("a", "idle|%d|a|pi||" % (NOW - 5000))
        self.write("b", "idle|%d|b|pi||" % (NOW - 100))
        self.assertEqual(latest_activity_ms(self.home, now_ms=NOW), NOW - 100)


def mk(key, state, ts, name="n", window="hub:n", hint=""):
    return Session(key=key, state=state, raw_state=state, ts=ts, name=name,
                   agent="pi", window=window, hint=hint, display=name)


class TestTracker(unittest.TestCase):
    def test_first_poll_never_alerts(self):
        t = Tracker(min_work_ms=0)
        self.assertEqual(t.update([mk("a", "needs-you", 10), mk("b", "done", 10)]), [])

    def test_needs_you_fires_on_the_per_session_edge(self):
        t = Tracker()
        t.update([mk("a", "working", 0), mk("b", "working", 0)])
        evs = t.update([mk("a", "needs-you", 100, hint="Ready?"), mk("b", "working", 0)])
        self.assertEqual([(e.kind, e.session.key) for e in evs], [("needs-you", "a")])

    def test_needs_you_does_not_repeat_while_state_holds(self):
        t = Tracker()
        t.update([mk("a", "working", 0)])
        t.update([mk("a", "needs-you", 100)])
        self.assertEqual(t.update([mk("a", "needs-you", 100)]), [])

    def test_done_chime_needs_a_long_enough_run(self):
        t = Tracker(min_work_ms=20000)
        t.update([mk("a", "working", 1000)])
        self.assertEqual(t.update([mk("a", "done", 5000)]), [])

    def test_done_chime_fires_after_a_long_run(self):
        t = Tracker(min_work_ms=20000)
        t.update([mk("a", "working", 1000)])
        evs = t.update([mk("a", "done", 41000)])
        self.assertEqual([(e.kind, e.worked_ms) for e in evs], [("done", 40000)])

    def test_second_session_alerts_independently(self):
        t = Tracker(min_work_ms=0)
        t.update([mk("a", "working", 0)])
        evs = t.update([mk("a", "working", 0), mk("b", "needs-you", 50, name="b")])
        self.assertEqual([e.session.key for e in evs], ["b"])

    def test_forgotten_sessions_are_dropped(self):
        t = Tracker(min_work_ms=0)
        t.update([mk("a", "working", 0)])
        t.update([])
        self.assertEqual(t.update([mk("a", "done", 99)]), [])


class TestFormatAge(unittest.TestCase):
    def test_seconds_minutes_hours(self):
        self.assertEqual(format_age(4200), "4s")
        self.assertEqual(format_age(185000), "3m")
        self.assertEqual(format_age(7300000), "2h")

    def test_zero_is_blank(self):
        self.assertEqual(format_age(0), "")


if __name__ == "__main__":
    unittest.main()
