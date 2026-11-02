"""Prospective replacement for one ingestion helper; not deployed.

RL_CONFIG is supplied by the destination socket_server module. This module
imports no numerical runtime and performs no work until the helper is called.
"""


def _continuous_play_score_dip(frame, client, previous_score, previous_wave, recent_start):
    """Preserve uninterrupted live play across small or large score-read dips.

    A late-wave live sample with no recent restart can lose a high decimal
    carry digit. Its size does not establish a new game. Keep the original
    small-dip rule for early waves and recent-start ambiguity; inactive player,
    restart-button and wave-change observations still bypass this guard.
    """
    return (
        bool(frame.player_alive) and not bool(frame.done)
        and bool(client.get("player_alive", False))
        and not bool(frame.start_pressed)
        and previous_wave is not None and int(frame.level_number) == int(previous_wave)
        and (int(frame.game_score) > 0 or not recent_start
             or int(frame.level_number) >= 2)
        and 0 < int(previous_score) - int(frame.game_score)
        and (
            int(previous_score) - int(frame.game_score) <= int(
                getattr(RL_CONFIG, "score_torn_read_tolerance", 100_000))
            or (int(frame.level_number) >= 2 and not recent_start)
        )
    )
