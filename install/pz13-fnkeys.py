#!/usr/bin/env python3
# ASUS ProArt PZ13 keyboard cover: turn the Fn-layer vendor reports (ASUS usage
# page 0xFF31 on the cover's USB interface 1, the touchpad + vendor interface)
# into regular input events via uinput, and expose the keyboard backlight as a
# LED class device.
#
# Report format (3 bytes): 0x5a <code> 0x01 on press, 0x5a 0x00 0x00 on release.
# Consumer-control keys (mute/volume, report id 0x0a) are handled by hid-generic
# already and are ignored here.
#
# Backlight: the LED is created through the kernel's userspace LED driver
# (uleds). UPower takes any LED whose name contains "kbd_backlight", and
# gnome-settings-daemon then owns the level: the idle handling dims it and
# switches it off together with the screen and restores it on activity, the
# quick-settings slider sets the level. Every change arrives here as a read on
# the uleds descriptor and goes to the cover as the ASUS feature report. Fn+F4
# cycles the four levels as on Windows (the ThinkPad model: the key is handled
# where the hardware is): the new level goes to the cover and is reported back
# through the uleds descriptor as a hardware change (patches/0015), which UPower
# passes on as "internal" so that GNOME shows the indicator and follows.
# hid-asus itself cannot do this on the PZ13: the vendor page shares the
# interface with the touchpad, and in current kernels the LED lives in
# asus-wmi, which does not exist on arm64.
import array, fcntl, glob, os, select, struct, subprocess, time
from evdev import UInput, ecodes as e

# older python3-evdev may lack this keycode
KEY_EMOJI_PICKER = getattr(e, "KEY_EMOJI_PICKER", 0x249)

# The cover's HID instance numbers (0003:0B05:1B6E.000N) change on every
# enumeration (detach/reattach, controller re-initialisation after resume);
# the vendor page sits on USB interface 1 of the cover, which is stable.
HID_MATCH = "0003:0B05:1B6E.*"
USB_INTERFACE = ":1.1/"

ULEDS = "/dev/uleds"
LED_NAME = "asus::kbd_backlight"    # the name hid-asus/asus-wmi use on x86
LED_MAX = 3                         # the cover has four levels, 0..3
LED_BRIGHTNESS = f"/sys/class/leds/{LED_NAME}/brightness"
BOOT_LEVEL = 1                      # until a desktop session sets the level
POLL_INTERVAL = 2.0                 # how often to look for a (re)attached cover

FEATURE_REPORT = 0x5a
HANDSHAKE = [FEATURE_REPORT, 0x41, 0x53, 0x55, 0x53, 0x20, 0x54, 0x65, 0x63,
             0x68, 0x2e, 0x49, 0x6e, 0x63, 0x2e, 0x00]   # "ASUS Tech.Inc."

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
KBD_CYCLE = 0xc7                  # Fn+F4  keyboard backlight: 0 -> 1 -> 2 -> 3 -> 0

def hidraw_path():
    for hid in sorted(glob.glob(f"/sys/bus/hid/devices/{HID_MATCH}")):
        if USB_INTERFACE not in os.path.realpath(hid):
            continue
        nodes = glob.glob(f"{hid}/hidraw/hidraw*")
        if nodes:
            return "/dev/" + nodes[0].rsplit("/", 1)[1]
    return None

def set_feature(f, data, size=64):
    buf = array.array("B", data + [0] * (size - len(data)))
    fcntl.ioctl(f, 0xC0004806 | (size << 16), buf, True)   # HIDIOCSFEATURE(size)

def send_backlight(cover, level):
    # same sequence as asus_kbd_init() / asus_kbd_backlight_work() in hid-asus
    try:
        set_feature(cover, HANDSHAKE)
        set_feature(cover, [FEATURE_REPORT, 0xba, 0xc5, 0xc4, level])
    except OSError as err:
        print(f"backlight {level}: {err}", flush=True)

def report_level(led, level):
    # tell the LED class what the cover shows now (brightness_hw_changed);
    # a kernel without patches/0015 answers EBUSY and GNOME does not follow
    try:
        os.write(led, struct.pack("i", level))
    except OSError as err:
        print(f"report {level}: {err}", flush=True)

def open_led():
    subprocess.run(["modprobe", "uleds"], check=False)
    fd = os.open(ULEDS, os.O_RDWR)
    os.write(fd, struct.pack("64sI", LED_NAME.encode(), LED_MAX))   # struct uleds_user_dev
    # the sysfs node appears right after that write; start at BOOT_LEVEL so the
    # cover is lit before any desktop session takes over (the write comes back
    # as the first read on fd)
    for _ in range(50):
        try:
            with open(LED_BRIGHTNESS, "w") as f:
                f.write(str(BOOT_LEVEL))
            break
        except OSError:
            time.sleep(0.1)
    return fd

def main():
    ui = UInput({e.EV_KEY: list(KEYMAP.values())}, name="PZ13 cover Fn keys")
    led = open_led()
    print(f"{LED_NAME}: registered", flush=True)
    level = BOOT_LEVEL
    cover = dev = pressed = None
    while True:
        fds = [led] + ([cover] if cover else [])
        ready, _, _ = select.select(fds, [], [], POLL_INTERVAL)
        if led in ready:
            level = struct.unpack("I", os.read(led, 4))[0]
            print(f"backlight {level}", flush=True)
            if cover:
                send_backlight(cover, level)
        if cover is None:
            dev = hidraw_path()
            if dev is None:
                continue
            try:
                cover = open(dev, "rb+", buffering=0)
            except OSError as err:
                print(f"{dev}: {err}", flush=True)
                continue
            print(f"{dev}: opened", flush=True)
            pressed = None
            # The cover only emits its Fn-layer reports after a backlight feature
            # report; send the current level now, which also covers every
            # re-enumeration (attach, the keyboard's firmware reset).
            send_backlight(cover, level)
            continue
        if cover not in ready:
            continue
        try:
            r = cover.read(64)
        except OSError as err:
            print(f"{dev}: {err}", flush=True)
            r = None
        if not r:
            cover.close()
            cover = None
            print(f"{dev}: closed", flush=True)
            continue
        if r[0] != FEATURE_REPORT:
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
                level = (level + 1) % (LED_MAX + 1)
                send_backlight(cover, level)
                report_level(led, level)
                print(f"Fn+F4: backlight {level}", flush=True)
            elif code in KEYMAP:
                ui.write(e.EV_KEY, KEYMAP[code], 1); ui.syn()
            else:
                print(f"unmapped vendor code 0x{code:02x}", flush=True)

if __name__ == "__main__":
    main()
