# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply the MIX power-button LED policy to the board RGB LED."""

from pathlib import Path
import signal
from threading import Event


LED = Path('/sys/class/leds/rgb:power')
POWER = Path('/sys/class/power_supply')
BACKLIGHT = Path('/sys/class/backlight/a081-backlight/actual_brightness')
AMBER = (50, 15, 0)
GREEN = (0, 65, 0)
WHITE = (15, 25, 25)


def read(path):
    try:
        return path.read_text().strip()
    except FileNotFoundError:
        return ''


def number(path):
    value = read(path)
    return int(value) if value else None


def power_state():
    status = read(POWER / 'pm8150b-charger/status')
    capacity = number(POWER / 'pm8150b-battery/capacity')
    if status in ('Charging', 'Full'):
        # The stock UI changes color at 90%, before charging terminates.
        green = capacity >= 90 if capacity is not None else status == 'Full'
        return 'green' if green else 'charging'

    if not number(BACKLIGHT):
        return 'off'
    return 'low' if capacity is not None and capacity <= 20 else 'white'


def write(attribute, value):
    (LED / attribute).write_text(f'{value}\n')


def show(state, maximum):
    # Writing zero also cancels the previous pattern in the LED core.
    write('brightness', 0)
    if state == 'off':
        return

    color = {'green': GREEN, 'charging': AMBER, 'low': AMBER, 'white': WHITE}[state]
    intensity = [(value * maximum + 127) // 255 for value in color]
    write('multi_intensity', ' '.join(str(value) for value in intensity))
    if state == 'low':
        # Match the stock 100 ms ramp steps and 200 ms pauses. The software
        # pattern preserves the calibrated amber ratio on the shared LPG LUT.
        write('trigger', 'pattern')
        write('repeat', -1)
        write('pattern', f'0 200 0 1000 {maximum} 200 {maximum} 1000')
    else:
        write('brightness', maximum)


def main():
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    if read(LED / 'multi_index').split() != ['red', 'green', 'blue']:
        raise RuntimeError('Unexpected MIX LED channel order')
    maximum = int(read(LED / 'max_brightness'))
    previous = None
    try:
        while not stop.is_set():
            state = power_state()
            if state != previous:
                show(state, maximum)
                previous = state
                print(f'Power indicator: {state}', flush=True)
            stop.wait(1)
    finally:
        try:
            write('brightness', 0)
        except FileNotFoundError:
            pass


if __name__ == '__main__':
    main()
