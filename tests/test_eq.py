import numpy as np
import pytest

from pilite_eq.display import COLS, ROWS, command, frame_string, render_text
from pilite_eq.spectrum import Analyzer, Meter, band_edges, bars_grid
from pilite_eq.__main__ import staircase

RATE = 22050
N = 2048


def tone(freq, amp=0.5, n=N, rate=RATE):
    t = np.arange(n) / rate
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_command_framing():
    assert command("ALL,OFF") == b"$$$ALL,OFF\r"
    assert command("B3,50") == b"$$$B3,50\r"


def one_pixel(r, c):
    g = [[False] * COLS for _ in range(ROWS)]
    g[r][c] = True
    return g


def test_frame_string_orders_and_flips():
    top_left = one_pixel(0, 0)
    assert frame_string(top_left, "cols").index("1") == 0
    assert frame_string(top_left, "rows").index("1") == 0
    # pixel at row 1, col 0: second char column-wise, 15th row-wise
    assert frame_string(one_pixel(1, 0), "cols").index("1") == 1
    assert frame_string(one_pixel(1, 0), "rows").index("1") == COLS
    assert frame_string(top_left, "cols", flip_x=True).index("1") == (COLS - 1) * ROWS
    assert frame_string(top_left, "cols", flip_y=True).index("1") == ROWS - 1
    assert len(frame_string(top_left)) == 126


def test_frame_string_rejects_wrong_size():
    with pytest.raises(ValueError):
        frame_string([[False] * COLS])


def test_band_edges_span_and_are_log_spaced():
    e = band_edges()
    assert len(e) == COLS + 1
    assert e[0] == pytest.approx(60) and e[-1] == pytest.approx(10000)
    ratios = e[1:] / e[:-1]
    assert np.allclose(ratios, ratios[0])


@pytest.mark.parametrize("band", range(COLS))
def test_tone_lands_in_its_band(band):
    a = Analyzer(RATE, N)
    e = band_edges()
    centre = float(np.sqrt(e[band] * e[band + 1]))
    db = a.band_db(tone(centre))
    assert int(np.argmax(db)) == band


def test_full_scale_sine_is_about_0db():
    a = Analyzer(RATE, N)
    db = a.band_db(tone(1000, amp=1.0))
    assert db.max() == pytest.approx(0, abs=1.5)


def test_every_band_has_bins():
    a = Analyzer(RATE, N)
    assert all(m.any() for m in a.masks)


def test_silence_stays_dark():
    m = Meter()
    h, p = m.update(np.full(COLS, -90.0), 0.1)
    assert not h.any() and not p.any()


def test_loud_band_fills_and_falls_gradually():
    m = Meter()
    db = np.full(COLS, -80.0)
    db[3] = -10.0
    h, _ = m.update(db, 0.1)
    assert h[3] == pytest.approx(ROWS)
    h, _ = m.update(np.full(COLS, -90.0), 0.1)  # sound stops
    assert 0 < h[3] < ROWS  # falling, not gone
    for _ in range(20):
        h, _ = m.update(np.full(COLS, -90.0), 0.1)
    assert h[3] == 0


def test_peak_hangs_then_drops():
    m = Meter(peak_hold=0.5)
    db = np.full(COLS, -80.0)
    db[0] = -10.0
    m.update(db, 0.1)
    quiet = np.full(COLS, -90.0)
    _, p = m.update(quiet, 0.2)
    assert p[0] == pytest.approx(ROWS)  # still held
    for _ in range(4):
        _, p = m.update(quiet, 0.2)
    assert p[0] < ROWS


def test_agc_adapts_to_quiet_music():
    m = Meter(range_db=40, gate_db=-65)
    db = np.full(COLS, -60.0)
    db[5] = -20.0
    for _ in range(100):
        h, _ = m.update(db, 0.1)
    assert h[5] == pytest.approx(ROWS)  # loudest band reaches the top
    assert h[0] == 0                     # 40 dB below it is empty


def test_bars_grid_grows_from_bottom_with_peak_dot():
    g = bars_grid(np.array([3.0] + [0.0] * (COLS - 1)), np.array([6.0] + [0.0] * (COLS - 1)))
    col0 = [g[r][0] for r in range(ROWS)]
    assert col0 == [False, False, False, True, False, False, True, True, True]
    assert not any(g[r][c] for r in range(ROWS) for c in range(1, COLS))


def test_staircase_shape():
    g = staircase()
    heights = [sum(g[r][c] for r in range(ROWS)) for c in range(COLS)]
    assert heights[0] == 0 and heights[-1] == ROWS
    assert heights == sorted(heights)
    assert render_text(g).splitlines()[-1].startswith(".#")
