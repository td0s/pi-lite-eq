"""Pi-Lite EQ meter.

    python3 -m pilite_eq                 run from the USB mic to the Pi-Lite
    python3 -m pilite_eq --test          orientation test pattern on the Pi-Lite
    python3 -m pilite_eq --sim           show the meter in the terminal instead
    python3 -m pilite_eq --sim --wav song.wav
"""

from __future__ import annotations

import argparse
import signal
import sys
import time

from .audio import MicSource, WavSource, find_usb_mic
from .display import COLS, ROWS, PiLite, TextDisplay
from .spectrum import Analyzer, Meter, bars_grid

N_FFT = 2048


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="pilite_eq", description="14-band EQ meter on a Pi-Lite")
    p.add_argument("--port", default="/dev/serial0", help="serial port (default /dev/serial0)")
    p.add_argument("--device", help="ALSA capture device (default: first USB mic found)")
    p.add_argument("--rate", type=int, default=22050, help="mic sample rate (default 22050)")
    p.add_argument("--fmin", type=float, default=60.0, help="lowest band edge, Hz")
    p.add_argument("--fmax", type=float, default=10000.0, help="highest band edge, Hz")
    p.add_argument("--range", dest="range_db", type=float, default=40.0,
                   help="dB from empty to full bar (default 40; lower = jumpier)")
    p.add_argument("--gate", dest="gate_db", type=float, default=-65.0,
                   help="below this level (dBFS) the display goes dark (default -65)")
    p.add_argument("--no-peaks", action="store_true", help="hide the falling peak dots")
    p.add_argument("--order", choices=["cols", "rows"], default="cols",
                   help="frame-buffer order the board expects (see --test)")
    p.add_argument("--flip-x", action="store_true", help="mirror left/right")
    p.add_argument("--flip-y", action="store_true", help="mirror top/bottom")
    p.add_argument("--settle", type=float, default=0.0,
                   help="extra seconds to wait after each frame, if the board garbles")
    p.add_argument("--test", action="store_true", help="show the orientation test pattern")
    p.add_argument("--sim", action="store_true", help="draw in the terminal, no Pi-Lite")
    p.add_argument("--wav", help="analyse a 16-bit WAV file instead of the mic")
    return p.parse_args(argv)


def staircase() -> list[list[bool]]:
    """Column c lit to height c*9/13: low on the left, full on the right."""
    return bars_grid([round(c * ROWS / (COLS - 1)) for c in range(COLS)])


def test_pattern(lite: PiLite) -> None:
    def step(msg: str, secs: float = 6.0) -> None:
        print(msg, flush=True)
        time.sleep(secs)

    lite.send("ALL,ON")
    step("1. Every LED should be on. (If not, check the serial setup.)", 3)
    lite.clear()
    lite.send("P1,1,ON")
    step("2. One LED is lit: that corner is the board's (1,1).")
    lite.clear()
    lite.send("F" + "1" * ROWS + "0" * (ROWS * COLS - ROWS))
    step("3. The first 9 frame-buffer characters. A full 9-LED column means\n"
         "   the board is column-ordered (--order cols, the default).\n"
         "   9 LEDs along a row means use --order rows.")
    lite.clear()
    for c in range(1, COLS + 1):
        lite.send(f"B{c},{round((c - 1) * 100 / (COLS - 1))}")
    step("4. The board's own bar command: a staircase, empty column to full.")
    lite.clear()
    lite.frame(staircase())
    step("5. The same staircase drawn by this program, with your --order/--flip\n"
         "   settings. It should be low on the LEFT, high on the RIGHT, with\n"
         "   bars growing UP. If it's mirrored, add --flip-x and/or --flip-y.")
    lite.clear()
    print("Done.")


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.test and args.sim:
        sys.exit("--test needs the real Pi-Lite")

    display = TextDisplay() if args.sim else PiLite(
        args.port, args.order, args.flip_x, args.flip_y, args.settle)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # systemd stop -> clean exit

    source = None
    try:
        if args.test:
            test_pattern(display)
            return 0

        if args.wav:
            source = WavSource(args.wav, N_FFT)
            rate = source.rate
        else:
            device = args.device or find_usb_mic()
            print(f"Listening on {device}", flush=True)
            rate = args.rate
            source = MicSource(device, rate, N_FFT)

        fmax = min(args.fmax, rate * 0.45)
        analyzer = Analyzer(rate, N_FFT, COLS, args.fmin, fmax)
        meter = Meter(COLS, ROWS, args.range_db, args.gate_db)

        display.clear()
        last_grid = None
        last = time.monotonic()
        while not (args.wav and source.finished):
            now = time.monotonic()
            dt, last = now - last, now
            heights, peaks = meter.update(analyzer.band_db(source.latest()), dt)
            grid = bars_grid(heights, None if args.no_peaks else peaks)
            if grid != last_grid:
                display.frame(grid)  # blocks while the frame goes out (~0.14 s)
                last_grid = grid
            else:
                time.sleep(0.02)
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        if source:
            source.close()
        display.close()


if __name__ == "__main__":
    sys.exit(main())
