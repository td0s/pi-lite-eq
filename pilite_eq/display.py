"""Pi-Lite (Ciseco) 9x14 LED matrix over the Pi's serial port.

Wire protocol, taken from Ciseco's PiLiteLib.py and the node-pilite library:
every command is "$$$" + command + "\\r", sent at 9600 baud.

    $$$ALL,ON / $$$ALL,OFF     all LEDs on/off
    $$$P<col>,<row>,ON|OFF|TOGGLE
    $$$B<col>,<pct>            one column as a bar, col 1-14, pct 0-100
    $$$F<126 x '0'/'1'>        whole display in one go
    $$$SPEED<ms>               scroll speed for plain text

Which corner is (1,1) and the order of the 126 frame-buffer characters are
not documented anywhere we could reach, so both are settings (see --test).
"""

from __future__ import annotations

import os
import time
from typing import Sequence

COLS = 14
ROWS = 9
BAUD = 9600

Grid = Sequence[Sequence[bool]]  # grid[row][col], row 0 = top, col 0 = left


def default_port() -> str:
    """/dev/serial0 is the header UART's alias on Raspberry Pi OS; some
    distros (e.g. Ubuntu) may not create it, so fall back to the PL011."""
    for port in ("/dev/serial0", "/dev/ttyAMA0"):
        if os.path.exists(port):
            return port
    raise SystemExit("No serial port found (/dev/serial0 or /dev/ttyAMA0). "
                     "See 'Free up the serial port' in the README, or use --port.")


def command(cmd: str) -> bytes:
    return b"$$$" + cmd.encode("ascii") + b"\r"


def frame_string(grid: Grid, order: str = "cols", flip_x: bool = False,
                 flip_y: bool = False) -> str:
    """Encode grid[row][col] (row 0 at the top) as the 126 '0'/'1' chars of $$$F.

    order "cols": column by column, each column top to bottom.
    order "rows": row by row, each row left to right.
    flip_x / flip_y mirror the picture if the board's (1,1) corner differs.
    """
    if len(grid) != ROWS or any(len(r) != COLS for r in grid):
        raise ValueError(f"grid must be {ROWS} rows x {COLS} cols")

    def px(r: int, c: int) -> str:
        if flip_y:
            r = ROWS - 1 - r
        if flip_x:
            c = COLS - 1 - c
        return "1" if grid[r][c] else "0"

    if order == "cols":
        return "".join(px(r, c) for c in range(COLS) for r in range(ROWS))
    if order == "rows":
        return "".join(px(r, c) for r in range(ROWS) for c in range(COLS))
    raise ValueError("order must be 'cols' or 'rows'")


class PiLite:
    """Sends commands to a Pi-Lite. Each send waits until the bytes have left
    the UART, so callers are paced by the 9600-baud link (~960 bytes/s) rather
    than piling up lag in the kernel buffer."""

    def __init__(self, port: str | None = None, order: str = "cols",
                 flip_x: bool = False, flip_y: bool = False, settle: float = 0.0):
        import serial  # pyserial; imported here so tests don't need it

        self.ser = serial.Serial(port or default_port(), BAUD, timeout=0)
        self.order, self.flip_x, self.flip_y = order, flip_x, flip_y
        self.settle = settle  # extra pause after each command, if the board lags

    def send(self, cmd: str) -> None:
        self.ser.write(command(cmd))
        self.ser.flush()
        self.ser.reset_input_buffer()  # ignore anything the board echoes
        if self.settle:
            time.sleep(self.settle)

    def clear(self) -> None:
        self.send("ALL,OFF")

    def frame(self, grid: Grid) -> None:
        self.send("F" + frame_string(grid, self.order, self.flip_x, self.flip_y))

    def close(self) -> None:
        try:
            self.clear()
        finally:
            self.ser.close()


class TextDisplay:
    """Stand-in for the Pi-Lite: draws frames in the terminal."""

    def __init__(self, fps: float = 7.0):
        self.period = 1.0 / fps  # mimic the serial link's frame rate

    def frame(self, grid: Grid) -> None:
        print("\x1b[H\x1b[2J" + render_text(grid), flush=True)
        time.sleep(self.period)

    def clear(self) -> None:
        pass

    def close(self) -> None:
        pass


def render_text(grid: Grid) -> str:
    return "\n".join("".join("#" if on else "." for on in row) for row in grid)
