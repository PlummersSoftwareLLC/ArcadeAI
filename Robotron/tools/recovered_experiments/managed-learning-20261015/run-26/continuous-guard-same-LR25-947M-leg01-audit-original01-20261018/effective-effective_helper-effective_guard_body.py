def _continuous_play_score_dip(frame, client, previous_score, previous_wave, recent_start):
    """A small carry tear during uninterrupted play is not a new game.

    The <=100K fresh-game allowance also contains ordinary early-game BCD
    carry tears.  Establish continuous live play before applying that broad
    allowance.  A zero near an autoboot pulse remains a possible real reset;
    inactive/alive edges and wave resets are never hidden by this guard.
    """
    return (
        bool(frame.player_alive) and not bool(frame.done)
        and bool(client.get("player_alive", False))
        and not bool(frame.start_pressed)
        and previous_wave is not None and int(frame.level_number) == int(previous_wave)
        and (int(frame.game_score) > 0 or not recent_start
             or int(frame.level_number) >= 2)
        and 0 < int(previous_score)-int(frame.game_score) <= int(
            getattr(RL_CONFIG, "score_torn_read_tolerance", 100_000))
    )

