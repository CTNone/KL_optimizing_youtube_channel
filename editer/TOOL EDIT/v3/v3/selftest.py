from pathlib import Path
from engine import RenderSettings, build_sequence, fmt_time

tracks = [Path(f"song_{i}.mp3") for i in range(1, 11)]
durations = {p: 240.0 for p in tracks}
first = tracks[:5]

seq, starts, cycles = build_sequence(
    tracks=tracks,
    first_five=first,
    durations=durations,
    target_seconds=3600,
    transition_mode="Crossfade",
    transition_seconds=2,
    seed=123456,
)

assert seq[:5] == first
assert starts[0] == 0
assert abs(starts[1] - 238.0) < 1e-6
assert starts[-1] < 3600
assert starts[-1] + durations[seq[-1]] >= 3600

# The randomized remainder is chosen once, then the entire playlist repeats.
repeat_seq, _, _ = build_sequence(
    tracks=tracks,
    first_five=first,
    durations=durations,
    target_seconds=5000,
    transition_mode="None",
    transition_seconds=0,
    seed=123456,
)
assert repeat_seq[:10] == repeat_seq[10:20]

s = RenderSettings()
assert s.duration_seconds == 3600
assert fmt_time(3600, True) == "01:00:00"

print("SELFTEST OK")
print("tracks:", len(seq))
print("cycles:", cycles)
print("last end:", starts[-1] + durations[seq[-1]])
