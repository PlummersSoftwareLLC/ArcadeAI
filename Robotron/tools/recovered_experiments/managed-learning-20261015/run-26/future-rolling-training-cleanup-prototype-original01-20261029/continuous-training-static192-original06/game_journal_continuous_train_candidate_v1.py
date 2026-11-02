"""Raw game/life evidence for experiment comparisons, independent of RL terminals.

``done`` is a lost LIFE.  Whole games end on the ingest layer's accepted score
reset, or confirmed life exhaustion.  Initial attachments and disconnects are
retained as partial records, never silently counted as full games.  Scores have
no minimum admission threshold; zero-point losses are valid observations.
"""
from collections import deque
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import statistics
import threading
import time


def _utc(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def _boundary_start_evidence(inputs, reason):
    """Expand private ingest primitives once per journal game, never per frame."""
    (previous, current, previous_score, previous_wave, previous_alive,
     last_start_before, last_start_after, recent_start, new_game, verdict) = inputs
    def sample(values):
        if values is None:
            return None
        return dict(zip(("raw_score", "raw_wave", "player_alive", "done",
                         "start_pressed", "lives", "accepted_frames_before"), values))
    return dict(
        schema="robotron-game-boundary-inputs-v1",
        scope="private evaluator; connection-local accepted wire samples only",
        journal_start_reason=reason,
        previous_accepted_wire=sample(previous), current_wire=sample(current),
        classifier_previous=dict(raw_score=previous_score, raw_wave=previous_wave,
                                 player_alive=previous_alive),
        last_start_frame_before=last_start_before,
        last_start_frame_after=last_start_after,
        recent_start=recent_start,
        classifier_new_game=new_game, classifier_verdict=verdict,
    )


class GameJournal:
    def __init__(self, directory, lives_start=3, clock=time.time, retire_after_game=False, continuous_train=False):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.games_path = self.directory / "games.jsonl"
        self.lives_path = self.directory / "lives.jsonl"
        self.measurement_starts_path = self.directory / "measurement_starts.jsonl"
        self.clock = clock
        self.lives_start = max(1, int(lives_start))
        self.lock = threading.Lock()
        self.active = {}
        self.completed = deque(maxlen=10000)
        # Keep measurement admissions/results independently of the display
        # deque.  A late high-score tail must remain in its original cohort
        # even after many unrelated games have completed.
        self.measurement_games = {}
        self.sequence = 0
        self.run_id = str(time.time_ns())
        self.retire_after_game = bool(retire_after_game)
        self.continuous_train = bool(continuous_train)
        if self.continuous_train and not self.retire_after_game:
            raise ValueError("Continuous training requires late-confirmed durable journal mode")
        self.retirements_path = self.directory / "completed_clients.jsonl"
        self.retirements = {}

    @classmethod
    def from_environment(cls, model_dir, lives_start=3):
        directory = os.getenv("ROBOTRON_RUN_DIR")
        if not directory:
            directory = Path(model_dir).parent / "logs" / (
                "game-journal-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ"))
        return cls(directory, lives_start=lives_start,
                   retire_after_game=os.getenv("ROBOTRON_RETIRE_AFTER_GAME", "0") == "1",
                   continuous_train=os.getenv("ROBOTRON_CONTINUOUS_TRAINING_MODE", "0") == "1")

    def _write(self, path, row):
        # One small append per life/game, outside the frame/inference critical
        # sections.  Closing each append also flushes it for live analysis.
        with path.open("a") as stream:
            stream.write(json.dumps(row, allow_nan=False, separators=(",", ":")) + "\n")
            if self.retire_after_game and path in (self.games_path, self.retirements_path):
                stream.flush()
                os.fsync(stream.fileno())
        if self.retire_after_game and path in (self.games_path, self.retirements_path):
            fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def _begin(self, cid, frame, cs, context, known_start, reason, boundary_inputs=None):
        self.sequence += 1
        now = self.clock()
        ctx = context()
        if boundary_inputs is not None:
            ctx = dict(ctx, game_boundary_diagnostics=
                       _boundary_start_evidence(boundary_inputs, reason))
        game = dict(
            journal_game_id=f"{self.run_id}:{self.sequence}",
            client_id=int(cid), client_slot=int(cs.get("client_slot", cid)),
            game_uid=int(cs.get("game_uid", 0)),
            eval_only=bool(cs.get("eval_only", False) or ctx.get("measurement_active", False)),
            start_utc=_utc(now), start_unix_s=now, start=ctx,
            known_start=bool(known_start), start_reason=reason,
            score=int(frame.game_score), max_level=int(frame.level_number) if not known_start else 0,
            playable_frames=0, observed_frames=0, deaths=0,
            life_start_score=int(frame.game_score), life_frames=0,
            last_alive=False, last_done=False, seen_positive_lives=False,
            mixed_experiment=False, finished=False, restart_pulse=False,
            measurement_active=bool(ctx.get("measurement_active", False)),
            measurement_generation=int(ctx.get("measurement_generation", 0)),
            mixed_measurement=False, first_play_level=None, result=None,
            initial_start_pulse=False,
            start_frame=dict(score=int(frame.game_score), level=int(frame.level_number),
                             player_alive=bool(frame.player_alive),
                             lives=int(getattr(frame, "lives", -1)),
                             start_pressed=bool(frame.start_pressed)),
        )
        self.active[cid] = game
        if game["measurement_active"]:
            self.measurement_games[game["journal_game_id"]] = game
            if known_start:
                self._write(self.measurement_starts_path, dict(
                    journal_game_id=game["journal_game_id"], client_id=game["client_id"],
                    client_slot=game["client_slot"], game_uid=game["game_uid"],
                    start_utc=game["start_utc"], start_unix_s=now,
                    experiment=ctx.get("experiment", ""), measurement_active=True,
                    measurement_generation=game["measurement_generation"],
                    known_start=True, start_reason=reason, context=ctx,
                    start_frame=game["start_frame"],
                ))
        return game

    def _finish(self, game, context, reason, complete):
        if game["finished"]:
            return
        now = self.clock()
        end = context()
        mixed = (game["mixed_experiment"]
                 or game["start"].get("experiment") != end.get("experiment"))
        mixed_policy = (game["mixed_measurement"]
                        or game["measurement_active"] != bool(end.get("measurement_active", False))
                        or game["measurement_generation"] != int(end.get("measurement_generation", 0)))
        invalid_start = game["measurement_active"] and game["first_play_level"] != 1
        eligible = bool(complete and game["known_start"]
                        and game["playable_frames"] > 0 and not mixed and not mixed_policy
                        and not invalid_start)
        excluded = ("" if eligible else "experiment_changed" if mixed else
                    "measurement_policy_changed" if mixed_policy else
                    "startup_attachment" if not game["known_start"] else
                    "measurement_start_not_wave_1" if invalid_start else
                    "no_playable_frames" if not game["playable_frames"] else reason)
        row = {key: game[key] for key in (
            "journal_game_id", "client_id", "client_slot", "game_uid", "eval_only",
            "start_utc", "start_unix_s", "start_reason", "known_start", "score",
            "max_level", "playable_frames", "observed_frames", "deaths", "first_play_level",
            "measurement_active", "measurement_generation", "start_frame")}
        row.update(
            end_utc=_utc(now), end_unix_s=now, duration_s=now-game["start_unix_s"],
            boundary_reason=reason, complete=bool(complete), eligible=eligible,
            excluded_reason=excluded, experiment=game["start"].get("experiment", ""),
            start_context=game["start"], end_context=end,
        )
        self._write(self.games_path, row)
        if (self.retire_after_game and (not self.continuous_train or game["eval_only"])
                and eligible and game["client_id"] not in self.retirements
                and reason in ("score_reset", "zero_score_restart")):
            # Commit both the ordinary score and the supervisor's completion
            # receipt before permitting an exit request on the action stream.
            self._write(self.retirements_path, row)
            self.retirements[game["client_id"]] = row
        game["finished"] = True
        game["result"] = row
        self.completed.append(row)

    def observe(self, cid, frame, cs, *, new_game=False, context, boundary_inputs=None, confirmed_boundary=None):
        """Observe one accepted, score-unwrapped frame without changing training.

        ``new_game`` comes from the existing ingest classifier, without the
        ratchet's 5,000-point cutoff.  A zero-point game has no score decrease:
        confirmed exhaustion followed by an autoboot pulse and a new alive edge
        supplies that otherwise invisible boundary.  Wire lives alone are not
        sufficient there (Lua's lives counter itself resets on a score drop),
        so all-zero games additionally use the configured starting life count.
        """
        with self.lock:
            game = self.active.get(cid)
            if game is None:
                game = self._begin(cid, frame, cs, context, bool(new_game),
                                   "score_reset" if new_game else "initial_attachment",
                                   boundary_inputs=boundary_inputs)
            elif new_game or int(cs.get("game_uid", 0)) != game["game_uid"]:
                self._finish(game, context, "score_reset" if new_game else "game_uid_changed", True)
                game = self._begin(cid, frame, cs, context, True,
                                   "score_reset" if new_game else "game_uid_changed",
                                   boundary_inputs=boundary_inputs)
            elif (self.retire_after_game and game["score"] == 0
                  and game["deaths"] >= self.lives_start and game["restart_pulse"]
                  and frame.player_alive and not game["last_alive"]):
                self._finish(game, context, "zero_score_restart", True)
                if confirmed_boundary is not None:
                    # Actual natural-boundary decision, after old final row is
                    # durable and before the new game/any life row is created.
                    confirmed_boundary("zero_score_restart", game["result"])
                game = self._begin(cid, frame, cs, context, True, "zero_score_restart",
                                   boundary_inputs=boundary_inputs)
            elif game["finished"]:
                game["restart_pulse"] |= bool(frame.start_pressed)
                if (game["score"] == 0 and game["restart_pulse"]
                        and frame.player_alive and not game["last_alive"]):
                    game = self._begin(cid, frame, cs, context, True, "zero_score_restart",
                                       boundary_inputs=boundary_inputs)
                else:
                    game["last_alive"] = bool(frame.player_alive)
                    return

            if (self.retire_after_game and not game["known_start"]
                    and game["start_reason"] == "initial_attachment"
                    and game["score"] == 0):
                # Boot/attract RAM can report alive before the first start
                # pulse. Require that pulse at zero score, then live wave 1;
                # those attract frames must not hide the actual first game.
                game["initial_start_pulse"] |= bool(frame.start_pressed and frame.game_score == 0)
                if (game["initial_start_pulse"] and frame.player_alive
                        and int(frame.level_number) == 1):
                    self._finish(game, context, "startup_attachment", False)
                    game = self._begin(cid, frame, cs, context, True, "observed_boot_start",
                                       boundary_inputs=boundary_inputs)

            # Mark cross-experiment games for exclusion even if the label later
            # returns to its old value before game end.
            label = cs.get("journal_experiment", game["start"].get("experiment", ""))
            game["mixed_experiment"] |= label != game["start"].get("experiment", "")
            game["mixed_measurement"] |= (
                bool(cs.get("journal_measurement_active", game["measurement_active"]))
                != game["measurement_active"]
                or int(cs.get("journal_measurement_generation", game["measurement_generation"]))
                != game["measurement_generation"])
            game["observed_frames"] += 1
            game["score"] = max(game["score"], int(frame.game_score))
            # A real score reset can precede the old wave byte clearing.
            # Fresh-start validation and its maximum begin at live play;
            # later inactive wave-clear frames still count normally.
            if (not game["known_start"] or frame.player_alive or game["playable_frames"] > 0):
                game["max_level"] = max(game["max_level"], int(frame.level_number))
            game["playable_frames"] += int(bool(frame.player_alive))
            game["life_frames"] += int(bool(frame.player_alive))
            lives = int(getattr(frame, "lives", -1))
            game["seen_positive_lives"] |= 0 < lives < 255
            if (game["first_play_level"] is None and frame.player_alive
                    and int(frame.level_number) >= 1 and 0 <= lives < 255):
                game["first_play_level"] = int(frame.level_number)
                if (boundary_inputs is not None and game["measurement_active"]
                        and game["known_start"] and game["first_play_level"] != 1):
                    # Preserve the later rejecting first-play inputs too when
                    # reset occurred on an inactive/zero-wave frame. No new
                    # write: existing completion/disconnect retains this copy.
                    game["start"] = dict(game["start"], first_play_not_wave_1_inputs=
                                         _boundary_start_evidence(boundary_inputs, "first_play_not_wave_1"))
            # Lua initializes previous_player_alive=1 at script load.  Its
            # first inactive/attract frame can therefore have done=1 without
            # any observed life; never turn that synthetic edge into a death.
            if frame.done and not game["last_done"] and game["life_frames"] > 0:
                game["deaths"] += 1
                ctx = context()
                self._write(self.lives_path, dict(
                    utc=_utc(self.clock()), journal_game_id=game["journal_game_id"],
                    client_id=int(cid), client_slot=game["client_slot"],
                    game_uid=game["game_uid"], eval_only=game["eval_only"],
                    known_game_start=game["known_start"], life=game["deaths"],
                    cumulative_score=int(frame.game_score),
                    life_score=max(0, int(frame.game_score)-game["life_start_score"]),
                    level=int(frame.level_number), playable_frames=game["life_frames"],
                    lives=lives, context=ctx,
                ))
                game["life_start_score"] = int(frame.game_score)
                game["life_frames"] = 0
                zero_exhausted = game["score"] == 0 and game["deaths"] >= self.lives_start
                if not self.retire_after_game and ((lives == 0 and game["seen_positive_lives"]) or zero_exhausted):
                    self._finish(game, context, "zero_score_lives_exhausted" if zero_exhausted
                                 else "wire_lives_exhausted", True)
            if self.retire_after_game and game["score"] == 0 and game["deaths"] >= self.lives_start:
                game["restart_pulse"] |= bool(frame.start_pressed)
            game["last_alive"] = bool(frame.player_alive)
            game["last_done"] = bool(frame.done)

    def retirement_for_client(self, cid):
        """Only a durably recorded, confirmed whole game can request exit."""
        with self.lock:
            return self.retirements.get(int(cid))

    def disconnect(self, cid, context):
        with self.lock:
            game = self.active.pop(cid, None)
            if game is not None:
                self._finish(game, context, "disconnect", False)
            # Connection IDs can be reused by a later training round. Its
            # first frame must never inherit the preceding client's exit bit.
            self.retirements.pop(int(cid), None)

    def policy_boundary(self, cid, context):
        """Exclude a game already in flight when the measured policy changes."""
        with self.lock:
            game = self.active.pop(cid, None)
            if game is not None:
                self._finish(game, context, "measurement_generation_changed", False)

    def cohort_status(self, experiment, start_ts, close_ts):
        """Fixed start-side window; completions after close_ts remain required.

        Starts during [start_ts, close_ts] belong permanently to this cohort.
        Disconnects, changed policies and invalid starts remain explicit
        abandoned members.  They never reduce the denominator or become zero
        scores, and no timeout silently decides on faster completions.
        """
        if close_ts < start_ts:
            raise ValueError("Cohort close_ts must be at or after start_ts")
        with self.lock:
            games = [game for game in self.measurement_games.values()
                     if game["known_start"] and game["start"].get("experiment") == experiment
                     and start_ts <= game["start_unix_s"] <= close_ts]
            rows, pending, abandoned, reasons = [], [], [], {}
            for game in games:
                identifier = game["journal_game_id"]
                row = game["result"]
                if row is not None:
                    if row["eligible"]:
                        rows.append(dict(row))
                    else:
                        abandoned.append(identifier)
                        reasons[identifier] = row["excluded_reason"] or row["boundary_reason"]
                elif game["mixed_experiment"] or game["mixed_measurement"]:
                    abandoned.append(identifier)
                    reasons[identifier] = "policy_or_experiment_changed"
                elif game["first_play_level"] not in (None, 1):
                    abandoned.append(identifier)
                    reasons[identifier] = "measurement_start_not_wave_1"
                else:
                    pending.append(identifier)
            started_ids = [game["journal_game_id"] for game in games]
            actor_slots = sorted({game["client_slot"] for game in games})
        rows.sort(key=lambda row: (row["start_unix_s"], row["journal_game_id"]))
        scores = [row["score"] for row in rows]
        n = len(scores)
        sd = statistics.stdev(scores) if n > 1 else 0.0
        closed = self.clock() >= close_ts
        return dict(
            experiment=experiment, start_ts=start_ts, close_ts=close_ts, closed=closed,
            complete=closed and bool(started_ids) and not pending and not abandoned,
            valid=not abandoned, rows=rows, count=n,
            mean=statistics.mean(scores) if n else 0.0,
            median=statistics.median(scores) if n else 0.0,
            sd=sd, se=sd/math.sqrt(n) if n else 0.0,
            started=len(started_ids), pending=len(pending), abandoned=len(abandoned),
            started_ids=started_ids, pending_ids=pending, abandoned_ids=abandoned,
            abandonment_reasons=reasons, started_actor_slots=actor_slots,
        )

    def summary(self, experiment=None, eval_only=True):
        """Non-overlapping raw GAME count and dispersion, never life count."""
        with self.lock:
            rows = [row for row in self.completed if row["eligible"]
                    and (not eval_only or row["eval_only"])
                    and (experiment is None or row["experiment"] == experiment)]
        scores = [row["score"] for row in rows]
        n = len(scores)
        sd = statistics.stdev(scores) if n > 1 else 0.0
        return dict(count=n, mean=statistics.mean(scores) if n else 0.0,
                    median=statistics.median(scores) if n else 0.0,
                    sd=sd, se=sd/math.sqrt(n) if n else 0.0,
                    max=max(scores, default=0),
                    last_end_utc=rows[-1]["end_utc"] if rows else "")
