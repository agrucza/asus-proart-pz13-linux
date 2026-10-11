# USB-C DisplayPort audio: what works, the driver fixes it needs, and the open quirk

Kernel: jglathe `jg/ubuntu-qcom-x1e-7.2.y` 7.2.5 plus `patches/`, package `-11`.

## Pieces

- Topology `audio/X1P42100-ASUS-ProArt-PZ13.m4`: the Surface Pro 12in description plus
  MultiMedia3/4 playback streams routed to `DISPLAY_PORT_RX_0/1` (sub-graph IDs chosen not
  to collide with the WSA/VA ones: streams 0x4002/0x6010 and 0x4003/0x6020, devices
  0x4006/0x6060 and 0x4007/0x6070). PCMs: 0 speakers, 1 mics, 2 and 3 DisplayPort.
- UCM: `install/ucm-dp-audio.conf` (devices `HDMI0`/`HDMI1`, `JackControl "DP0 Jack"` /
  `"DP1 Jack"`; the jack controls exist as `iface=CARD` controls). The DP routes must also
  be switched on in the verb's EnableSequence: PipeWire opens every PCM of the verb when it
  builds the card profile and drops the whole verb (speakers included) if one open fails.
- Kernel `patches/0010`: `msm_dp_audio_startup()` returned -ENOTSUPP while the DP display
  was not powered, so the DP PCMs could not be opened without a monitor and PipeWire
  dropped the profile ("Profile HiFi not supported", `spa-acp-tool -v -v -v -c 0 quit`).
  Mainline has no such refusal; `msm_dp_audio_prepare()` already skips the programming
  while the display is off.
- `install/wireplumber-20-dp-audio.conf`: 1 s idle suspend for the DP sinks (the driver
  waits up to 5 s for the stream to close before it tears the link down; PipeWire's
  default idle timeout is also 5 s) and `priority.session = 2000` so a plugged monitor
  becomes the default output automatically.

## What works

Plug a monitor into either port: audio comes from the monitor, PipeWire switches to it by
itself and back to the speakers on unplug. Repeated plug/unplug cycles across both ports
are clean, with or without audio on the port. The GNOME sound-settings window should be
closed while unplugging: its level meters keep every sink open, which defeats the idle
suspend and makes the driver wait 5 s for the stream (`audio comp timeout`) on unplug.

## Driver fixes (patches/)

- `0010` msm/dp: audio startup succeeds while the display is off. PipeWire opens every PCM
  of the verb when it builds the profile; a refused open drops the whole profile, speakers
  included.
- `0011` msm/dp: no forced link retrain from the hot-plug handler. The handler set the
  connector's link status from inside the bridge hot-plug notification, which runs with the
  encoder's bridge-chain mutex held and takes the modeset lock; a compositor commit holds
  the modeset lock and walks the same chain. The resulting deadlock freezes display, USB and
  keyboard while audio and SSH keep running (stacks: `drm_connector_set_link_status_property
  <- msm_dp_hpd_plug_handle <- drm_bridge_connector_hpd_notify` against
  `drm_atomic_add_encoder_bridges <- drm_atomic_check_only` in gnome-shell). Mainline does
  not set the property there. The retrain also added a disable/enable cycle to every plug on
  a port whose HPD bounces during negotiation, which port 0 does on this machine.
- `0012` msm/dp: the connector probe (`msm_dp_bridge_detect`, this tree's AUX-reading
  version) no longer writes the hot-plug handlers' `plugged` flag. It runs on every hotplug
  event, also while the link is training, and a failed AUX read marked the port unplugged:
  the next unplug notification was then ignored (visible as an unplug handler `Before` line
  without its `After` line), leaving the jack plugged, the PHY initialised and the port in a
  stale state in which the next enable fails link training (`ret=-110`, `Unexpected DP AUX
  IRQ`) and hangs the display engine (`frame done timeout`), typically when the screen
  comes back from an idle blank with nothing attached.
- `0013` q6apm (upstream daa7ffd765ae): the graph start count is only incremented when the
  DSP accepted the start. Before, a refused `APM_CMD_GRAPH_START` left the port counted as
  running, and the retried start returned success without any command: the stream showed
  `RUNNING` with the position stuck at zero and the player waited forever.

## Open quirk: first start of port 0 after a boot

The DSP refuses the first `APM_CMD_GRAPH_START` for `DISPLAY_PORT_RX_0` after every boot:

```
qcom-apm gprsvc:service:2:1: DSP returned error[1001002] 1
q6apm-lpass-dais ...: Failed to start APM port 104
q6apm-lpass-dais ...: ASoC error (-22): at soc_dai_trigger() on DISPLAY_PORT_RX_0
pipewire: spa.alsa: hw:X1P42100ASUSPro,2p: snd_pcm_start: Invalid argument
```

The controller side is identical to a working session (same link-up, same audio engine
programming, video running). PipeWire tries the start once and then waits. The next PCM
session on the port, with a freshly opened graph, starts fine, so the recovery is to switch
the output to the speakers and back to the monitor once (or unplug and replug). Port 1 has
not shown this. Rebuilding the port's graph inside the failed trigger does not work: the
DSP does not answer the close of a graph whose stream is still running, every following
command times out and the sound card is lost until a reboot. The reason for the refusal is
in the ADSP firmware; it needs someone with firmware knowledge (the IdeaCentre Mini
topology has three DP ports, the AudioReach maintainers have the module documentation).

## State shipped

Speakers and microphones only by default. DisplayPort audio is opt-in via the files above
because of the port-0 quirk. Patches 0010 to 0013 are part of the kernel regardless.
