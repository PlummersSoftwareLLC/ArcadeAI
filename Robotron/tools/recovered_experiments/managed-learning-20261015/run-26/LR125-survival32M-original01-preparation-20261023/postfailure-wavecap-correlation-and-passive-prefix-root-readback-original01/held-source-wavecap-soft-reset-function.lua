local function wavecap_check(frame_idx, wave, player_alive, score)
    -- EDGE-triggered only: fire exactly on the (cap-1) -> cap wave advance
    -- of a live, real game.  A level-triggered check here caused a reset
    -- loop (2026-07-27): soft_reset reloads this script (wiping any
    -- cooldown global) while the wave byte still holds the old deep value
    -- during boot/attract, so the cap re-fired every cycle.  Edge + score
    -- guard can't refire across a reset: after reload prev_wave is nil and
    -- a fresh game's score is far below the threshold.  Legacy marathons
    -- already past the cap are left to finish naturally.
    local w = math.floor(wave or 0)
    local fire = WAVE_RESET_CAP > 0 and not SERVER_IS_EVAL and EVAL_MODE ~= 1
        and (player_alive or 0) ~= 0
        and wavecap_prev_wave == WAVE_RESET_CAP - 1
        and w == WAVE_RESET_CAP
        and math.floor(score or 0) >= 50000
    wavecap_prev_wave = w
    if fire then
        print(string.format(
            "[WAVECAP] wave advance %d -> %d - soft reset (training-data rebalance)",
            WAVE_RESET_CAP - 1, w))
        pcall(function() manager.machine:soft_reset() end)
    end
end
