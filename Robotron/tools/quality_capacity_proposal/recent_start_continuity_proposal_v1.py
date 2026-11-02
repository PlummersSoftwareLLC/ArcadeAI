"""Unselected primitive proposal for the observed recent-START carry edge.

RL_CONFIG is provided by the destination handler. Full-handler, wire, source
propagation and lifecycle proofs remain required before any runtime selection.
"""


def _continuous_play_score_dip(frame, client, previous_score, previous_wave, recent_start):
    """Keep the established guard, adding a conservative banked-reserve case.

    A stale recent-START latch does not itself establish a restart while both
    samples remain alive on the same late wave with unchanged banked reserves.
    Starting reserves and possible configured register wraps remain ambiguous.
    """
    reserves = getattr(frame, "num_lasers", None)
    previous_reserves = client.get("num_lasers")
    starting_lives = getattr(RL_CONFIG, "lives_start", 3)
    modulus = int(getattr(RL_CONFIG, "score_wrap_modulus", 100_000_000))
    banked_reserves = (
        type(reserves) is int and type(previous_reserves) is int
        and type(starting_lives) is int and 1 <= starting_lives < 255
        and starting_lives <= reserves == previous_reserves < 255)
    possible_register_wrap = (int(previous_score) >= 0.9 * modulus
                              and int(frame.game_score) <= 0.1 * modulus)
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
            or (int(frame.level_number) >= 2 and recent_start
                and banked_reserves and not possible_register_wrap)
        )
    )
