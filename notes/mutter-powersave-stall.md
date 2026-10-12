# Draft report for mutter: frame clock stalls while an output is in power-save mode

Target: https://gitlab.gnome.org/GNOME/mutter/-/issues (component: backends/native).
Observed on the ASUS ProArt PZ13 (Snapdragon X Plus X1P-42-100, msm/DPU display driver,
eDP OLED panel), Debian trixie: mutter 48.7, gnome-shell 48.x, gnome-settings-daemon 48.x,
Wayland session.

## Summary

Once the only output is switched to power-save mode OFF, no Clutter animation makes
progress until the output is switched back on. Two user-visible consequences:

1. Every suspend starts about 5 s late. On "PrepareForSleep(true)" gnome-settings-daemon
   switches the display off immediately (`handle_suspend_actions` → `backlight_disable`),
   while gnome-shell is still animating the lock screen (`ScreenShield.lock(true)`: slide-in,
   then a 300 ms pause and a 300 ms fade). The animation never completes, so gnome-shell
   never reaches `_setActive(true)` and never releases its delay inhibitor; logind proceeds
   after `InhibitDelayMaxSec` (5 s).
2. After resume the screen comes on (g-s-d `backlight_enable`), the stalled lock animation
   now finishes, gnome-shell reports `ActiveChanged(true)`, g-s-d blanks again
   (`idle_set_mode(BLANK)`), and the screen stays dark until the user touches something.

## Reproduction without suspend

```
busctl --user set-property org.gnome.Mutter.DisplayConfig /org/gnome/Mutter/DisplayConfig \
        org.gnome.Mutter.DisplayConfig PowerSaveMode i 3
sleep 2
gdbus call --session --dest org.gnome.ScreenSaver --object-path /org/gnome/ScreenSaver \
        --method org.gnome.ScreenSaver.SetActive true
journalctl --user -u org.gnome.SettingsDaemon.Power.service -f   # with G_MESSAGES_DEBUG=all
```

`Received screensaver ActiveChanged signal: 1` never appears while the display is off; it
appears about 1.1 s after `PowerSaveMode` is set back to 0.

## What was ruled out

- Kernel display driver: with the `drm_vblank_event_queued`/`drm_vblank_event_delivered`
  tracepoints enabled, the off commit and the on commit both complete and nothing is
  outstanding when the output is switched off.
- Power button, lid switch and DRM hotplug events (none during the cycle).

## Where it points in mutter 48

`meta_onscreen_native` completes a frame while in power-save mode only from
`meta_onscreen_native_dummy_power_save_page_flip()` → `clear_superseded_frame()`, i.e.
only once a *newer* frame has superseded the pending one. The frame clock dispatches a
second frame while one is pending only when `want_triple_buffering()` is true, which on a
GPU that renders quickly (max update time estimate < refresh interval) it is not. The
pending frame is therefore never completed, the clock stays in `DISPATCHED_ONE`, and
animations stop. Work item #5041 and MR !5363 ("Handle forward progress without painting
when power saving") touch the same area on main.

Workaround in use: a gnome-shell extension that calls `lock(false)` (no animation) when
`LoginManager.preparingForSleep` is set, so the shield becomes active synchronously before
the display is switched off.
