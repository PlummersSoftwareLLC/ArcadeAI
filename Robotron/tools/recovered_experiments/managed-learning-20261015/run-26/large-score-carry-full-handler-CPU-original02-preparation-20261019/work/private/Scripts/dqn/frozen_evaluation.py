"""Isolated protocol primitives for an inference-only frozen evaluation.

Nothing imports this module in the live trainer yet. A controller must own model
and stream locking, queue barriers, policy publication and exception-safe resume.
These helpers deliberately never load checkpoints or touch optimizer state.
"""

from dataclasses import dataclass, field
import math


@dataclass(frozen=True)
class FrozenPolicy:
    label: str
    generation: int

    def controls(self):
        """Apply before the eval-client/training-client action branches."""
        return dict(
            epsilon=0.0, expert_ratio=0.0, action_source="measurement",
            count_learner=False, store_replay=False, update_schedules=False,
        )


def reset_client_replay_segment(client, current_score):
    """Call in the owning client thread on entry AND exit generation changes.

    History is intentionally discarded at the policy boundary. The containing
    life is partial: the caller must suppress elite admission until the next
    natural life boundary, and acknowledge the generation after this reset.
    Existing stored replay and schedule clocks are untouched.
    """
    nstep = client.get("nstep")
    if nstep is not None:
        nstep.reset()
    history = client.get("frame_history")
    if history is not None:
        history.clear()
    for key in ("last_state", "last_action", "prev_action_source"):
        client[key] = None
    for key in ("total_reward", "ep_dqn_reward", "ep_dqn_score_reward", "ep_expert_reward",
                "ep_subj_reward", "ep_obj_reward", "ep_death_reward", "ep_frames",
                "ep_dqn_frames", "no_human_no_score_frames", "fire_hold_count"):
        client[key] = 0
    client["fire_hold_dir"] = client["fire_pending_dir"] = -1
    client["ep_start_score"] = int(current_score)
    client["replay_episode_partial"] = True


def reset_async_episode_tracking(buffer):
    """Consumer-thread barrier callback, after pre-boundary commands drain.

    The producer gate must already be closed. Do not call this directly from
    the controller while the asynchronous consumer is mutating these maps.
    Retain stored replay, bank data and adaptive admission-threshold history.
    """
    buffer._client_indices.clear()
    buffer._episode_indices.clear()


@dataclass
class FrozenCohort:
    """Fixed start-side quota per actor; every admitted game must finish.

    Start notifications must be delivered in start order, independent of
    completion order. Timeout/disconnect/changed-policy games make a leg
    inconclusive; they are never replaced silently or assigned a zero score.
    """

    policy: FrozenPolicy
    actor_slots: frozenset
    games_per_actor: int = 2
    admitted: dict = field(default_factory=dict)
    completed: dict = field(default_factory=dict)
    invalid: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.actor_slots or self.games_per_actor < 1:
            raise ValueError("A cohort needs actor slots and a positive game quota")

    def start(self, game_id, actor_slot, *, known_start, generation):
        if (not known_start or generation != self.policy.generation
                or actor_slot not in self.actor_slots or game_id in self.admitted):
            return False
        count = sum(slot == actor_slot for slot in self.admitted.values())
        if count >= self.games_per_actor:
            return False
        self.admitted[game_id] = actor_slot
        return True

    def finish(self, game_id, *, score, eligible, generation, reason="ineligible_game"):
        if game_id not in self.admitted or game_id in self.completed or game_id in self.invalid:
            return False
        if not eligible or generation != self.policy.generation:
            self.invalid[game_id] = reason
        elif not math.isfinite(score) or score < 0:
            self.invalid[game_id] = "invalid_score"
        else:
            self.completed[game_id] = float(score)
        return True

    def abort(self, reason):
        """Mark every unresolved slot; never turn a timeout into acceptance."""
        self.invalid.setdefault("__cohort__", reason)

    @property
    def complete(self):
        expected = len(self.actor_slots) * self.games_per_actor
        return not self.invalid and len(self.completed) == expected

    def scores_by_actor(self):
        if not self.complete:
            raise RuntimeError("Incomplete or invalid start-side cohort")
        return {slot: [self.completed[game_id] for game_id, actor in self.admitted.items() if actor == slot]
                for slot in sorted(self.actor_slots)}
