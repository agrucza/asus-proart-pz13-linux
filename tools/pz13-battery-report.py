#!/usr/bin/env python3
# Summarise /var/log/pz13-battery.csv (written by install/pz13-battery-log):
# charge/discharge sessions with duration, energy and average power, the drain
# over every suspend, full discharge/charge cycles (calibrations), and the
# health history (energy_full against the design value, cycle count).
import argparse
import csv
import sys
from datetime import datetime, timedelta

def wh(uwh):
    return uwh / 1e6

def hours(td):
    return td.total_seconds() / 3600

def fmt_td(td):
    m = int(td.total_seconds() // 60)
    return f"{m // 60}:{m % 60:02d}"

def load(path, since):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            try:
                r["t"] = datetime.strptime(r["time"], "%Y-%m-%dT%H:%M:%S")
                r["e"] = int(r["energy_now"])
                # the percentage column is empty where the battery driver has none
                r["cap"] = int(r["capacity"]) if r["capacity"] else \
                    round(100 * r["e"] / int(r["energy_full"]))
            except (KeyError, ValueError):
                continue
            if since and r["t"] < since:
                continue
            rows.append(r)
    return rows

def sessions(rows):
    """Runs of consecutive rows with the same status (no gap over 30 min)."""
    out = []
    cur = []
    for r in rows:
        if cur and (r["status"] != cur[-1]["status"] or
                    r["t"] - cur[-1]["t"] > timedelta(minutes=30)):
            out.append(cur)
            cur = []
        cur.append(r)
    if cur:
        out.append(cur)
    return [s for s in out if len(s) > 1]

def report_sessions(rows):
    print("Sessions (status, start, duration, charge, energy, average power)")
    for s in sessions(rows):
        a, b = s[0], s[-1]
        if a["status"] not in ("Charging", "Discharging"):
            continue
        dt = b["t"] - a["t"]
        de = wh(b["e"] - a["e"])
        h = hours(dt)
        power = f"{abs(de) / h:5.1f} W" if h >= 0.25 else "   -  "
        print(f"  {a['status']:<11} {a['t']:%Y-%m-%d %H:%M}  {fmt_td(dt):>6} h "
              f"{a['cap']:3d}% -> {b['cap']:3d}%  {de:+6.2f} Wh  {power}")
    print()

def report_suspends(rows):
    pairs = []
    pre = None
    for r in rows:
        if r.get("note") == "pre":
            pre = r
        elif r.get("note") == "post" and pre and r["t"] > pre["t"]:
            pairs.append((pre, r))
            pre = None
    if not pairs:
        return
    print("Suspend (start, duration, drain)")
    for a, b in pairs:
        dt = b["t"] - a["t"]
        de = wh(a["e"] - b["e"])
        h = hours(dt)
        rate = f"{de / h:5.2f} W" if h >= 0.5 else "   -  "
        charger = " (charger)" if b.get("charger") == "1" else ""
        print(f"  {a['t']:%Y-%m-%d %H:%M}  {fmt_td(dt):>6} h  {de:+6.2f} Wh  {rate}{charger}")
    print()

def report_cycles(rows):
    """A discharge down to 5 % or less followed by a charge up to 100 %."""
    ss = [s for s in sessions(rows) if s[0]["status"] in ("Charging", "Discharging")]
    found = False
    for i in range(len(ss) - 1):
        d, c = ss[i], ss[i + 1]
        if d[0]["status"] != "Discharging" or d[-1]["cap"] > 5:
            continue
        if c[0]["status"] != "Charging" or c[-1]["cap"] < 100:
            continue
        if not found:
            print("Full cycles (discharge to <= 5 %, then charged to 100 %)")
            found = True
        before = int(d[0]["energy_full"] or 0)
        after = int(c[-1]["energy_full"] or 0)
        print(f"  {d[0]['t']:%Y-%m-%d %H:%M}  discharge {fmt_td(d[-1]['t'] - d[0]['t'])} h, "
              f"charge {fmt_td(c[-1]['t'] - c[0]['t'])} h, "
              f"energy_full {wh(before):.2f} -> {wh(after):.2f} Wh")
    if found:
        print()

def report_health(rows):
    print("Health (last value of each day: energy_full, of design, cycles)")
    by_day = {}
    for r in rows:
        if r.get("energy_full") and r.get("energy_full_design"):
            by_day[r["t"].date()] = r
    for day, r in sorted(by_day.items()):
        full, design = int(r["energy_full"]), int(r["energy_full_design"])
        print(f"  {day}  {wh(full):6.2f} Wh  {100 * full / design:5.1f} %  "
              f"cycles {r.get('cycle_count') or '-'}  limit {r.get('charge_end') or '-'} %")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("log", nargs="?", default="/var/log/pz13-battery.csv")
    ap.add_argument("--days", type=int, help="only the last N days")
    args = ap.parse_args()
    since = datetime.now() - timedelta(days=args.days) if args.days else None
    rows = load(args.log, since)
    if not rows:
        sys.exit(f"{args.log}: no data")
    report_sessions(rows)
    report_suspends(rows)
    report_cycles(rows)
    report_health(rows)

if __name__ == "__main__":
    main()
