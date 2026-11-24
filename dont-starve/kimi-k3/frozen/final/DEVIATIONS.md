# Deviations from the documented Don't Starve procedure (2026-11-16)

Host-run (`python -m gamescientist.cli trial`, DISPLAY=:1) from worktree /home/ubuntu/gs-ds-kg (origin/main 03de5423e), not a managed environment (Steam QR login not possible).

1. Steam client: the host client had auto-updated to `steamrt64/steam`, which `verify_steam` does not recognise. Marker `~/.steam/debian-installation/.steam-disable-steamrt64-client` created and Steam restarted as `ubuntu12_32/steam` (done by the coordinator).
2. Menu background: snapshot reference screenshots have a teal background (Shipwrecked enabled in the preparer's menu); this base-game-only account shows red. `frame_matches` in `gamescientist/games/dont_starve/integration.py` patched locally (diff: frame_matches.patch in this directory): after the original strict comparison fails, a hue-insensitive fallback accepts a frame if mean grayscale difference < 30 and the z-scored grayscale mean difference < 0.25. Snapshot files unchanged (hash 459353d6...a2afc9, validated). No DLC bought or enabled; world is the base-game save. Post-preparation check (setup.json): age 22.73, cycles 0, health 150, empty inventory, DLC none.
3. Local specs (untracked) in benchmarks/trials/dont-starve/: grok-4-7-live-3h, kimi-k3-1-pro-live-3h, kimi-k3-1-pro-frozen-3h; provider_failure_policy freeze_retry_timeout_credit; live ones carry observation_age_limit_seconds 240.0.
4. `.env` symlinked into the worktree (load_env reads cwd/.env).
5. Failed preparation attempts before the clock started (menu mismatch, stale profile symlink) were infrastructure failures, no score; each spent one pre-run interview call.
6. kimi-frozen-3h hit repeated provider failures at ~04:18 and paused for the operator; coordinator created RESUME_PROVIDER at ~06:28 after a probe returned 200 (operator_pause_seconds ~7766, excluded from charge). autoresume.sh then watches for further pauses.
