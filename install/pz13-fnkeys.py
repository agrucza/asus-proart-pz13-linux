#!/usr/bin/env python3
# ASUS ProArt PZ13 keyboard cover: turn the Fn-layer vendor reports (ASUS usage
# page 0xFF31 on the cover's USB interface 1, the touchpad + vendor interface)
# into regular input events via uinput, and drive the keyboard backlight from
# Fn+F4.
#
# Report format (3 bytes): 0x5a <code> 0x01 on press, 0x5a 0x00 0x00 on release.
# Consumer-control keys (mute/volume, report id 0x0a) are handled by hid-generic
# already and are ignored here.
import glob, os, time, subprocess
from evdev import UInput, ecodes as e

# older python3-evdev may lack this keycode
KEY_EMOJI_PICKER = getattr(e, "KEY_EMOJI_PICKER", 0x249)

# The cover's HID instance numbers (0003:0B05:1B6E.000N) change on every
# enumeration (detach/reattach, controller re-initialisation after resume);
# the vendor page sits on USB interface 1 of the cover, which is stable.
HID_MATCH = "0003:0B05:1B6E.*"
USB_INTERFACE = ":1.1/"
KBDLIGHT = "/usr/local/bin/kbdlight"
STATE = "/run/pz13-kbdlight.level"

KEYMAP = {
    0x10: e.KEY_BRIGHTNESSDOWN,   # Fn+F5
    0x20: e.KEY_BRIGHTNESSUP,     # Fn+F6
    # Fn+F7 (display) is sent by the cover as Super+P on the keyboard interface
    0x7e: KEY_EMOJI_PICKER,       # Fn+F8  emoji
    0x7c: e.KEY_MICMUTE,          # Fn+F9  mic mute
    0xcb: e.KEY_PROG1,            # Fn+F10 ASUS AI noise cancelling (free to bind)
    0x8b: e.KEY_PROG2,            # Fn+F12 (free to bind)
    0x4e: e.KEY_FN_ESC,           # Fn+Esc Fn lock (handled in the cover firmware)
}
KBD_CYCLE = 0xc7                  # Fn+F4  keyboard backlight

def hidraw_path():
    for hid in sorted(glob.glob(f"/sys/bus/hid/devices/{HID_MATCH}")):
        if USB_INTERFACE not in os.path.realpath(hid):
            continue
        nodes = glob.glob(f"{hid}/hidraw/hidraw*")
        if nodes:
            return "/dev/" + nodes[0].rsplit("/", 1)[1]
    return None

def cycle_backlight():
    try:
        level = int(open(STATE).read().strip())
    except Exception:
        level = 1
    level = (level + 1) % 4
    subprocess.run([KBDLIGHT, str(level)], check=False)
    with open(STATE, "w") as f:
        f.write(str(level))

def current_level():
    try:
        return int(open(STATE).read().strip())
    except Exception:
        return 1

def run(dev, ui):
    pressed = None
    with open(dev, "rb", buffering=0) as f:
        print(f"{dev}: opened", flush=True)
        # The cover only emits its Fn-layer reports after a backlight feature
        # report; send it (again) now that this node is being read, which also
        # covers every re-enumeration (attach, the keyboard's firmware reset).
        subprocess.run([KBDLIGHT, str(current_level())], check=False)
        while True:
            r = f.read(64)
            if not r:
                return
            if r[0] != 0x5a:
                continue
            code = r[1]
            if code == 0 and pressed is not None:
                if pressed in KEYMAP:
                    ui.write(e.EV_KEY, KEYMAP[pressed], 0); ui.syn()
                pressed = None
            elif code == pressed:
                # key held: the cover repeats the code; forward as auto-repeat
                if code in KEYMAP:
                    ui.write(e.EV_KEY, KEYMAP[code], 2); ui.syn()
            elif code:
                pressed = code
                if code == KBD_CYCLE:
                    cycle_backlight()
                elif code in KEYMAP:
                    ui.write(e.EV_KEY, KEYMAP[code], 1); ui.syn()
                else:
                    print(f"unmapped vendor code 0x{code:02x}", flush=True)

def main():
    ui = UInput({e.EV_KEY: list(KEYMAP.values())}, name="PZ13 cover Fn keys")
    while True:
        dev = hidraw_path()
        if dev is None:
            time.sleep(2)
            continue
        try:
            run(dev, ui)
        except OSError as err:
            print(f"{dev}: {err}", flush=True)
        time.sleep(1)   # cover detached; wait for it to come back

if __name__ == "__main__":
    main()
