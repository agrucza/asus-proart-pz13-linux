#!/usr/bin/env python3
"""Probe the Snapdragon Sensor Core (QMI service 400 on the ADSP) over QRTR.

Lists which sensor types the core knows and streams one of them for a few
seconds. Needs no root and no extra packages. Wire format: QMI over
AF_QIPCRTR, payloads protobuf (Qualcomm sensinghub apis/proto: sns_client,
sns_suid, sns_std_sensor).

  pz13-ssc-probe.py              # which sensors exist
  pz13-ssc-probe.py accel 10     # stream "accel" for 10 s
"""
import socket
import struct
import sys
import time

AF_QIPCRTR = 42
SNS_SERVICE = 400
QMI_REQ, QMI_IND, QMI_JUMBO_IND = 0x20, 0x21, 0x22
SUID_LOOKUP = (0xABABABABABABABAB, 0xABABABABABABABAB)
MSG_SUID_REQ, MSG_SUID_EVENT = 512, 768
MSG_STREAM_CONFIG, MSG_SENSOR_EVENT, MSG_ERROR_EVENT = 513, 1025, 130
DATA_TYPES = ["accel", "gyro", "mag", "ambient_light", "proximity", "pressure",
              "device_orient", "motion_detect", "sensor_temperature"]


def varint(n):
    out = b""
    while True:
        b, n = n & 0x7F, n >> 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def pb_bytes(f, d): return varint(f << 3 | 2) + varint(len(d)) + d
def pb_varint(f, v): return varint(f << 3) + varint(v)
def pb_fixed32(f, v): return varint(f << 3 | 5) + struct.pack("<I", v)
def pb_fixed64(f, v): return varint(f << 3 | 1) + struct.pack("<Q", v)
def pb_float(f, v): return varint(f << 3 | 5) + struct.pack("<f", v)


def read_varint(buf, i):
    val = shift = 0
    while i < len(buf):
        b = buf[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not b & 0x80:
            break
        shift += 7
    return val, i


def pb_parse(buf):
    out, i = {}, 0
    while i < len(buf):
        t, i = read_varint(buf, i)
        f, w = t >> 3, t & 7
        if w == 0:
            v, i = read_varint(buf, i)
        elif w == 1:
            v, i = buf[i:i + 8], i + 8
        elif w == 2:
            n, i = read_varint(buf, i)
            v, i = buf[i:i + n], i + n
        elif w == 5:
            v, i = buf[i:i + 4], i + 4
        else:
            break
        out.setdefault(f, []).append(v)
    return out


def qmi_encode(msg_id, txn, payload):
    tlv = struct.pack("<H", len(payload)) + payload       # u16 count + bytes
    body = b"\x01" + struct.pack("<H", len(tlv)) + tlv
    return struct.pack("<BHHH", 0, txn, msg_id, len(body)) + body


def qmi_decode(buf):
    if len(buf) < 7:
        return None, {}
    _, _, msg_id, _ = struct.unpack_from("<BHHH", buf, 0)
    tlvs, i = {}, 7
    while i + 3 <= len(buf):
        t, n = buf[i], struct.unpack_from("<H", buf, i + 1)[0]
        tlvs[t] = buf[i + 3:i + 3 + n]
        i += 3 + n
    return msg_id, tlvs


def events(tlvs):
    """(msg_id, payload) of every event in an indication (TLV 2, after the count)."""
    if 2 not in tlvs:
        return
    for e in pb_parse(tlvs[2][2:]).get(2, []):
        inner = pb_parse(e)
        if 1 in inner:
            yield struct.unpack("<I", inner[1][0])[0], (inner[3][0] if 3 in inner else b"")


def client_request(suid, msg_id, payload=b""):
    suid_msg = pb_fixed64(1, suid[0]) + pb_fixed64(2, suid[1])
    susp = pb_varint(1, 1) + pb_varint(2, 0)                 # APSS, wakeup delivery
    req = pb_bytes(2, payload) if payload else b""
    return pb_bytes(1, suid_msg) + pb_fixed32(2, msg_id) + pb_bytes(3, susp) + pb_bytes(4, req)


def find_service():
    s = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM, 0)
    s.settimeout(2.0)
    s.sendto(struct.pack("<5I", 10, 0, 0, 0, 0), (1, 0xFFFFFFFE))   # NEW_LOOKUP to the name server
    found = None
    while True:
        try:
            data, _ = s.recvfrom(4096)
        except socket.timeout:
            break
        if len(data) >= 20:
            cmd, svc, _, node, port = struct.unpack_from("<5I", data, 0)
            if cmd == 4 and svc == SNS_SERVICE:
                found = (node, port)
    s.close()
    return found


def lookup(addr, data_type, timeout=4.0):
    """All SUIDs the core has for a data type."""
    s = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM, 0)
    s.settimeout(timeout)
    req = client_request(SUID_LOOKUP, MSG_SUID_REQ, pb_bytes(1, data_type.encode()) + pb_varint(2, 0))
    s.sendto(qmi_encode(QMI_REQ, 1, req), addr)
    suids, deadline = [], time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            try:
                data, _ = s.recvfrom(65536)
            except socket.timeout:
                break
            msg_id, tlvs = qmi_decode(data)
            if msg_id not in (QMI_IND, QMI_JUMBO_IND):
                continue
            for eid, pay in events(tlvs):
                if eid == MSG_SUID_EVENT:
                    for sb in pb_parse(pay).get(2, []):
                        su = pb_parse(sb)
                        suids.append((struct.unpack("<Q", su[1][0])[0], struct.unpack("<Q", su[2][0])[0]))
                    return suids
    finally:
        s.close()
    return suids


def stream(addr, suid, rate_hz, seconds):
    s = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM, 0)
    s.settimeout(3.0)
    cfg = pb_float(1, rate_hz)                                # sns_std_sensor_config.sample_rate
    s.sendto(qmi_encode(QMI_REQ, 2, client_request(suid, MSG_STREAM_CONFIG, cfg)), addr)
    end, n = time.monotonic() + seconds, 0
    try:
        while time.monotonic() < end:
            try:
                data, _ = s.recvfrom(65536)
            except socket.timeout:
                print("no data for 3 s")
                continue
            msg_id, tlvs = qmi_decode(data)
            if msg_id not in (QMI_IND, QMI_JUMBO_IND):
                continue
            for eid, pay in events(tlvs):
                if eid == MSG_SENSOR_EVENT:
                    p = pb_parse(pay)
                    floats = []
                    for v in p.get(1, []):                   # data: repeated float (packed or not)
                        floats += [struct.unpack_from("<f", v, o)[0] for o in range(0, len(v) - 3, 4)]
                    n += 1
                    if n <= 5 or n % 25 == 0:
                        print(f"#{n:4d} " + "  ".join(f"{f:9.3f}" for f in floats), flush=True)
                elif eid == MSG_ERROR_EVENT:
                    print("error event from the core (rate not supported?)")
    finally:
        s.close()
    print(f"{n} samples in {seconds} s")


def main():
    addr = find_service()
    if not addr:
        sys.exit("sensor core service (400) not found on QRTR")
    print(f"sensor core at node {addr[0]} port {addr[1]}")
    if len(sys.argv) == 1:
        for dt in DATA_TYPES:
            su = lookup(addr, dt, timeout=2.0)
            print(f"{dt:20s} " + (", ".join(f"{a:#018x}/{b:#018x}" for a, b in su) if su else "-"))
        return
    dt = sys.argv[1]
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    su = lookup(addr, dt)
    if not su:
        sys.exit(f"no sensor of type {dt!r}")
    print(f"{dt}: {su[0][0]:#x}/{su[0][1]:#x}")
    stream(addr, su[0], 25.0, seconds)


if __name__ == "__main__":
    main()
