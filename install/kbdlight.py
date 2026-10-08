#!/usr/bin/env python3
# Setzt die Tastaturbeleuchtung des PZ13-Covers ueber die ASUS-ROG-Feature-Reports (0x5a).
# Aufruf: sudo ./kbdlight.py <0..3>
import fcntl, array, glob, sys

def hidraw_of(hid_match, usb_interface=":1.1/"):
    # instance numbers change on every enumeration; match USB interface 1
    import os
    nodes = []
    for hid in sorted(glob.glob(f"/sys/bus/hid/devices/{hid_match}")):
        if usb_interface in os.path.realpath(hid):
            nodes = glob.glob(f"{hid}/hidraw/hidraw*")
            if nodes: break
    if not nodes: sys.exit(f"kein hidraw fuer {hid_match} auf USB-Interface 1")
    return "/dev/" + nodes[0].rsplit("/", 1)[1]

def set_feature(fd, data, size=64):
    buf = array.array("B", data + [0] * (size - len(data)))
    fcntl.ioctl(fd, 0xC0004806 | (size << 16), buf, True)   # HIDIOCSFEATURE(size)

level = int(sys.argv[1]) if len(sys.argv) > 1 else 3
dev = hidraw_of("0003:0B05:1B6E.*")
with open(dev, "rb+", buffering=0) as fd:
    # Handshake wie asus_kbd_init(): "ASUS Tech.Inc."
    set_feature(fd, [0x5a, 0x41, 0x53, 0x55, 0x53, 0x20, 0x54, 0x65, 0x63, 0x68, 0x2e, 0x49, 0x6e, 0x63, 0x2e, 0x00])
    # Helligkeit wie asus_kbd_backlight_work(): 0..3
    set_feature(fd, [0x5a, 0xba, 0xc5, 0xc4, level])
print(f"{dev}: Stufe {level} gesendet")
