# Pi-Lite EQ meter

A 14-band EQ meter (spectrum analyser) on a Ciseco **Pi-Lite** 9×14 LED board,
listening through a USB microphone on a **Raspberry Pi 3 Model B** running
**Ubuntu**.

The music plays on an Echo (through the Music Assistant Alexa skill), so the Pi
never has the audio itself. A USB mic next to the Echo lets the Pi hear exactly
what you hear, in time with it, whatever is playing.

```
USB mic ─► arecord ─► FFT (numpy) ─► 14 log-spaced bands, 60 Hz–10 kHz
        ─► auto-gain, fast rise / slow fall, peak dots ─► Pi-Lite over serial
```

- Bars rise instantly and fall smoothly. A dot hangs at each peak for 0.6 s.
- Auto-gain: the loudest band reaches the top, and quiet music still fills the
  display. Below the gate (silence), the display goes dark.
- The Pi-Lite's serial link runs at 9600 baud. A full-display update is 131
  bytes, so the meter runs at about **7 frames a second**.

## Hardware

- Pi-Lite on GPIO pins 1–26 (the Pi 3's 40-pin header takes it at the pin-1
  end). It is powered from the Pi's 5 V and talks on the UART (GPIO 14/15).
- Any USB microphone or USB sound card with a mic. The Pi has no audio input of
  its own. Check that it still fits in a USB port with the Pi-Lite fitted.

## 1. Free up the serial port (Pi 3, Ubuntu)

On a Pi 3, Bluetooth uses the good UART, and the header pins get the "mini
UART", whose speed drifts with the CPU clock. Ubuntu also puts a login console
on the port. Both need changing. Take a copy of the two boot files first, in
case the Pi doesn't come back up:

```sh
sudo cp /boot/firmware/config.txt  /boot/firmware/config.txt.bak
sudo cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.bak
```

1. **Give the header the good UART** by turning off Bluetooth. Add these lines
   at the end of `/boot/firmware/config.txt`:
   ```
   [all]
   enable_uart=1
   dtoverlay=disable-bt
   ```
   If the top of `config.txt` says not to edit it and to use `usercfg.txt`
   instead (older Ubuntu releases), put the lines in
   `/boot/firmware/usercfg.txt`.
   (Use `dtoverlay=miniuart-bt` instead if something on the Pi needs Bluetooth.)
2. **Remove the serial console.** `/boot/firmware/cmdline.txt` is one long
   line. Delete just the `console=serial0,115200` part (leave `console=tty1`
   and the rest alone):
   ```sh
   sudo sed -i 's/console=serial0,[0-9]* //' /boot/firmware/cmdline.txt
   cat /boot/firmware/cmdline.txt    # check: still one line, no serial0
   ```
3. Stop Bluetooth trying to use the port (these may say "not found", which is
   fine):
   ```sh
   sudo systemctl disable hciuart
   sudo systemctl disable serial-getty@ttyAMA0 serial-getty@ttyS0
   ```
4. Reboot, then check:
   ```sh
   ls -l /dev/ttyAMA0 /dev/serial0     # serial0 may not exist on Ubuntu; that's OK
   systemctl status serial-getty@ttyAMA0  # should be inactive
   ```

The meter uses `/dev/serial0` if it exists, otherwise `/dev/ttyAMA0`.

If the Pi won't boot after this, put the SD card in another computer and copy
the `.bak` files back over the originals (they're on the `system-boot`
partition).

Your user needs to be in the `dialout` (serial) and `audio` groups. Ubuntu's
default `ubuntu` user already is: `groups` shows them. Otherwise:
`sudo usermod -aG dialout,audio $USER`, then log out and back in.

## 2. Check the mic

```sh
sudo apt-get install -y alsa-utils
arecord -l                                     # the USB mic should be listed
arecord -D plughw:CARD=Device,DEV=0 -d 5 -f S16_LE -r 22050 test.wav
alsamixer -c Device                            # F4 = capture level
```

Use the card name `arecord -l` shows in place of `Device`. The meter picks the
first USB capture card on its own, or use `--device`.

If `arecord -l` lists nothing with the mic plugged in, Ubuntu may be missing
the USB audio driver, which on some releases is in a separate package:

```sh
sudo apt-get install -y linux-modules-extra-raspi
sudo reboot
```

## 3. Get the code onto the Pi and try it

Copy this folder to the Pi (e.g. `git clone`, or `scp -r`), then:

```sh
sudo apt-get install -y python3-numpy python3-serial alsa-utils
python3 -m pilite_eq --test      # orientation test pattern, ~30 s
python3 -m pilite_eq             # the meter (Ctrl+C to stop)
python3 -m pilite_eq --sim       # the meter in the terminal, no Pi-Lite needed
```

### The orientation test

The Pi-Lite's documentation is no longer online, so two details are guessed and
`--test` checks them:

- **Step 3:** if the first 9 frame-buffer characters light **a full column**,
  the default `--order cols` is right. If they light **9 LEDs along a row**,
  add `--order rows`.
- **Step 5:** the staircase should be low on the **left**, high on the
  **right**, with bars growing **up**. If not, add `--flip-x` and/or `--flip-y`.

## 4. Run it at boot

```sh
./install.sh
```

This installs the packages and a `pilite-eq` service that starts at boot and
restarts if the mic isn't ready yet. Options go in `/etc/default/pilite-eq`:

```sh
echo 'PILITE_EQ_ARGS="--flip-x --range 35"' | sudo tee /etc/default/pilite-eq
sudo systemctl restart pilite-eq
```

Stop the service (`sudo systemctl stop pilite-eq`) before running `--test` by
hand, since only one program can use the serial port.

## Options

| Option | Default | |
|---|---|---|
| `--range` | 40 | dB from an empty to a full bar. Lower = jumpier. |
| `--gate` | -65 | Below this level (dBFS) the display goes dark. Raise it if room noise shows. |
| `--fmin` / `--fmax` | 60 / 10000 | Frequency span of the 14 bands, Hz. |
| `--no-peaks` | | Hide the peak dots. |
| `--order`, `--flip-x`, `--flip-y` | cols | Board orientation (see the test). |
| `--settle` | 0 | Extra pause after each frame, if the board garbles updates. |
| `--device` | first USB mic | ALSA capture device. |
| `--port` | /dev/serial0, else /dev/ttyAMA0 | Serial port. |
| `--sim`, `--wav FILE` | | Terminal display / analyse a WAV file instead of the mic. |

## Pi-Lite command reference

From Ciseco's `PiLiteLib.py` and the `node-pilite` library. 9600 baud, each
command is `$$$` + command + `\r`.

| Command | |
|---|---|
| `$$$ALL,ON` / `$$$ALL,OFF` | all LEDs on / off |
| `$$$P<col>,<row>,ON\|OFF\|TOGGLE` | one LED, col 1–14, row 1–9 |
| `$$$B<col>,<pct>` | column as a bar, 0–100 % |
| `$$$V<1\|2>,<pct>` | two horizontal bars (stereo VU) |
| `$$$F<126 × 0/1>` | whole display |
| `$$$SCROLL<n>` | scroll n columns, −14…14 |
| `$$$T<col>,<row>,<char>` | character at a position |
| `$$$SPEED<ms>` | scroll speed of plain text, default 80 |

Any text without `$$$` scrolls across the display.

## Development

```sh
nix develop
python -m pytest
python -m pilite_eq --sim --wav some.wav
```
