# ASUS ProArt PZ13 (HT5306QA) – Linux device tree

Snapdragon X Plus X1P-42-100 ("Purwa"), 16 GB, 1 TB NVMe, 13" 3K OLED (2880×1800,
Samsung SDC 41B0, eDP), WCN7850 (Wi-Fi 7), detachable keyboard cover (USB), MPP 2.0 pen.

Device tree derived from the upstream ASUS Zenbook A14 DTS (same SoC) and the PZ13's
Windows ACPI dump (DSDT). Kernel: `jg/ubuntu-qcom-x1e-7.2.y` from
[jglathe/linux_ms_dev_kit](https://github.com/jglathe/linux_ms_dev_kit) (7.2.5).
## Files

| File | Contents |
|------|----------|
| `dts/x1p42100-asus-proart-pz13.dts` | Board file: model, firmware paths, GPU, WLAN PMU, panel |
| `dts/x1-asus-proart-pz13.dtsi` | Regulators (incl. PM8010 camera rails), USB, PCIe, I2C devices, pinctrl, display, audio, front and IR camera |
| `ucm2/Qualcomm/x1e80100/` | UCM profile (alsa-ucm-conf) for the sound card: two `.conf` files plus `x1e80100.conf.patch` for the DMI dispatcher |
| `install/` | systemd-boot entry, initramfs hook, keyboard backlight script, Fn-key daemon + unit, gnome-shell extension for locking on suspend, WirePlumber override that enables the libcamera monitor, libcamera tuning files for the OV5675 and OV13858, sleep hook that re-initialises the cover after resume |
| `notes/cameras.md` | Camera sensors and their wiring, decoded from the Windows driver package |
| `tools/` | `aeob-parse.py` (decoder for the Windows camera resource binaries), `pz13-dpdiag.sh` (USB-C/DisplayPort alt-mode state dump) |
| `patches/` | Kernel patches on top of jglathe's `jg/ubuntu-qcom-x1e-7.2.y`: the HM1092 sensor driver + binding (v6 from linux-media), CSIPHY combo-mode support in camss/phy-qcom-mipi-csi2 (ours, needed for the IR camera), X1P42100 CAMSS support (Wenmeng Liu v3 from linux-media, needed because Purwa has no IFE1: with the X1E description every suspend/resume toggled a non-existent power domain), device-tree support for the OV13858 rear-camera driver (ours: supplies, reset line, OF match, binding), the PZ13 entry in the SCM driver's QSEECOM allow-list (ours; RTC and UEFI variables), and a HID battery quirk for the ELAN touch controller's bogus stylus battery (ours), and the panel's entry in the samsung,atna33xc20 binding (ours) |

Kernel integration: copy both DTS files to `arch/arm64/boot/dts/qcom/`, add
`dtb-$(CONFIG_ARCH_QCOM) += x1p42100-asus-proart-pz13.dtb` to the `Makefile`, and the
compatible `asus,proart-pz13-ht5306qa` to `Documentation/devicetree/bindings/arm/qcom.yaml`.
For the cameras apply `patches/*.patch` (`git am`) and set `CONFIG_VIDEO_HM1092=m`.

Schema check (dt-schema 2026.9, jglathe 7.2.5 tree): `make CHECK_DTBS=y W=1
qcom/x1p42100-asus-proart-pz13.dtb` reports nothing from our two files and no dtc warnings;
`dt_binding_check DT_SCHEMA_FILES=arm/qcom.yaml` accepts the compatible. The three remaining
warnings (`ufshc@1d84000` compatible, `pm8550` `adc@9000`) come from the SoC/PMIC includes and
appear identically on `x1e80100-crd.dtb`.

## What works

| Area | Status |
|------|--------|
| Boot, SCM, SMMU, SPMI/PMICs, RPMh regulators | works |
| Display (msm/DPU, eDP, Samsung ATNA33AA08-0 OLED, native 2880×1800) | works with the `samsung,atna33xc20` panel driver and the PMIC enable line (`patches/0009` adds the panel to the binding); brightness via `dp_aux_backlight` (adjustable in GNOME) |
| GPU (Adreno X1-45) | hardware accelerated with Mesa ≥ 25.2 (trixie-backports 26.1); firmware `gen71500_sqe.fw`/`gen71500_gmu.bin` from linux-firmware git (trixie's package is too old); the ZAP shader must be the ASUS-signed `qcdxkmsucpurwa.mbn` from the Windows driver, the generic `qcom/x1p42100/gen71500_zap.mbn` is rejected by TrustZone (`error -22`, GPU stays off, Mesa falls back to llvmpipe; tested 2026-10-06) |
| NVMe (pcie6a) | works |
| WLAN WCN7850 (pcie4, ath12k) | works (NetworkManager); ath12k uses the generic board file, the ASUS variant is missing from linux-firmware |
| Bluetooth (uart14) | works: the ASUS Pen pairs and connects (BLE), its battery service shows up in BlueZ and UPower |
| USB-C ×2 (usb_1_ss0/ss1) incl. ps883x retimers | works (stick, LAN adapter, charger, SuperSpeed on both ports); DisplayPort alt mode works on both ports (passive USB-C→DP adapter, picture on the monitor; `tools/pz13-dpdiag.sh` shows the ADSP reporting the mode, the PHY switching to DP and `msm_dp_ctrl_setup_tr_unit` after link training); DP audio untested |
| Keyboard cover (usb_mp, 0b05:1b6e) | keyboard, Caps LED, touchpad, mute/volume, display switch work natively; Fn+F4–F12 and the backlight via the userspace daemon `install/pz13-fnkeys.py`; Fn lock not available (see below) |
| Touchscreen + pen (ELAN 04F3:430A, i2c8 @0x10, IRQ tlmm 51) | works, incl. stylus collection. The controller's stylus battery report is bogus (constant 1 % with the pen in range, also after hours of charging), so `patches/0008` ignores it like the Surface Pro 12's ELAN controller. The pen's real charge level comes over Bluetooth once the pen is paired (BLE battery service, shown by UPower and GNOME) |
| EC HID (0B05:4543, i2c0 @0x17, IRQ tlmm 67) | bound (hidraw), hotkey events not decoded yet |
| Lid sensor (tlmm 92) | works: closing the cover over the screen gives logind "Lid closed"/"Lid opened" and suspends the tablet per GNOME's lid policy |
| Volume buttons (pm8550 GPIO 6 up, GPIO 8 down) | work via gpio-keys (GNOME volume popup) |
| RTC (PMK8550) and UEFI variables | work with `patches/0007` (PZ13 on the SCM driver's QSEECOM allow-list): the TrustZone UEFI variable service comes up, `/sys/firmware/efi/efivars` is populated, the RTC registers as `rtc0` and sets the system clock at boot; its offset is kept in a UEFI variable (`qcom,uefi-rtc-info`), the alarm belongs to the ADSP |
| ADSP/CDSP, UCSI (PD controller), battery/charging (qcom_battmgr) | works. Battery: state, energy now/full/design (health from the ratio), voltage, power while charging and discharging, temperature, cycle count, manufacture date, model and serial. Charge limit: `charge_control_{start,end}_threshold` (start = end − 5, e.g. 75/80) is applied by the firmware within a session, but not kept across a reboot: the firmware mirrors the limit into PMK8550 SDAM 15 (the cells the Vivobook S15 DTS wires to `pmic-glink`) only when the OS sets one and zeroes those bytes at every boot, so wiring the cells gains nothing here, and no UEFI variable holds it either. UPower re-applies the limit at startup, so GNOME Settings' "Preserve Battery Health" switch (75/80) survives a reboot from the user's point of view; but between power-off and the next boot the firmware charges without the limit. Charger: USB-C PD/PPS flagged and the operating current (3.25 A) reported per port; the negotiated voltage and wattage are not available on this firmware: UCSI advertises features 0x0004 (no PDO details) and rejects a forced GET_PDOS (-70), and the battery manager answers every per-property charger request with value 0 |
| Suspend/resume (PSCI "deep") | works, also on battery and with the camera drivers loaded (kernel -7 with the X1P42100 CAMSS description; the X1E description toggles the non-existent `cam_cc_ife_1_gdsc` on every suspend/resume). The cover cannot wake the tablet: a short key press during suspend only powers the cover briefly (backlight blinks), holding a key for 3–5 s triggers the keyboard's firmware reset. Waking is by power button. `usb_mp` has no `wakeup-source`: with USB wakeup the port stays stuck in link state Resume after the keyboard's firmware reset (`xhci-hcd.1.auto: Port resume timed out, port 1-2`, "Cannot enable") until the controller is re-bound; without it the controller is shut down at suspend and rebuilt at resume and the cover comes back. The keyboard's firmware reset also wipes the cover's state while the kernel reset-resumes it as the same device, so `install/pz13-cover-usb-resume` (systemd-sleep hook) re-sends the backlight feature report after every resume; the cover only emits Fn-layer reports after that (verified sequence: suspend, keyboard reset by holding a key, key press, power button: keyboard, backlight and Fn+F keys working) |
| Audio | works: speakers (2× WSA8845 on swr0, `sdw:1:0:0217:0204:00:{0,1}`) and microphones (DMICs on the VA macro, `l1b` enabled through `audio-routing` to `vdd-micb`) in GNOME; no headset jack, no WCD codec. Needs topology + UCM (see Installation) |
| Front camera (OV5675, cci1_i2c1 @0x36, csiphy4, MCLK4, PM8010 rails) | works: libcamera lists "Internal front camera", `cam` streams 640×480 at 30 fps, GNOME Snapshot shows the live preview, and with libcamera 0.7.1 from trixie-backports plus `install/libcamera-ov5675.yaml` (Qualcomm's own colour matrices) the picture has correct exposure and plausible colours. Full-resolution `cam` output fails to allocate its buffers from the default 128 MB CMA pool (`cma=256M` on the command line should fix it, untested). Needs the WirePlumber override from `install/` (see Installation). Wiring derived from the Windows package, see `notes/cameras.md` |
| IR camera (HM1092, cci0_i2c1 @0x24, MCLK1, reset tlmm 111, csiphy4 lane 2 in combo mode with the RGB sensor) | streams: `cam -s role=raw` delivers 560×360 10-bit mono at 29.7 fps and the frame shows the room in near-infrared. Needs the kernel patches in `patches/` (HM1092 driver from linux-media + CSIPHY combo-mode support). Image is only ambient IR: the PM8550 illuminator is not wired up yet |
| Rear camera (OV13858, cci0_i2c0 @0x36, csiphy0 4 lanes, MCLK0, reset tlmm 109) | works: libcamera lists "Internal back camera", `cam` streams 640×480 at 30 fps and the frames show the room (exposure settles within a few dozen frames; colours flat without a tuning file); GNOME Snapshot switches between front and rear camera (WirePlumber rule names it "PZ13 rear camera", the front camera stays the default). Needs `patches/0006` (device-tree support for the ov13858 driver: supplies, reset, OF match). Sensor rails PM8550 LDO7 (AVDD), PM8010 LDO2 (DVDD) and LDO6 (DOVDD); the sensor only answers while PM8010 LDO4 (the IR camera's I/O rail) is on as well, so that rail is always-on. Focus motor DW9714 @0x0c (PM8010 LDO5, `lens-focus` of the sensor, ancillary link present in the media graph) and the module EEPROM 24c64 @0x50 (PM8010 LDO6, reads as empty apart from a 4-byte header) are described; the motor works (`v4l2-ctl -d <lens subdev> --set-ctrl=focus_absolute=0..1023`, verified by sharpness at 0 vs 1000) but libcamera's software-ISP pipeline has no autofocus and does not expose the lens, so focus is manual via V4L2 for now (the lens keeps its last position across streams; 0 = infinity). `install/libcamera-ov13858.yaml` (Qualcomm's CC13 matrices from `com.qti.tuned.ov13858.bin`, same decoding as for the front camera) gives stronger, more plausible colours; with the software ISP's lack of highlight handling, clipped highlights turn magenta under artificial light |
| Rear camera (OV13858) | not started; wiring known (`notes/cameras.md`), the mainline driver has no regulator support |
| Sensor DSP, fan control | not implemented |

Kernel parameters: `consoleblank=0 clk_ignore_unused pd_ignore_unused arm64.nopauth`.
The `*_unused`/`nopauth` parameters are the usual bring-up parameters on this platform (as in
jglathe's Ubuntu kernel command line). `regulator_ignore_unused` is not needed: without
it the regulator core only disables the `VREG_RTMR0_*` rails of the unused USB-C retimer 0
after 30 s, and the retimer re-enables them on plug; everything else has a
consumer or is `always-on`.

## Hardware mapping (from the DSDT)

| Linux | Windows ACPI | Address | Device |
|-------|--------------|---------|--------|
| i2c8 | I2C9 / QUP_1_SE_0 | 0x00a80000 | ELAN9008 touchscreen @0x10 (HID descriptor 0x0001) |
| i2c0 | I2C1 / QUP_0_SE_0 | 0x00b80000 | ASUS EC HID (QTEC0001) @0x17 |
| i2c5 | I2C6 / QUP_0_SE_5 | 0x00b94000 | ASUS EC @0x5B (confirmed with i2cdetect), second device @0x76 |
| i2c3 / i2c7 | I2C4 / I2C8 | 0x00b8c000 / 0x00b9c000 | USB-C retimers ps8833 @0x08 (as on the Zenbook) |
| uart21 | \_SB.UARD | 0x00894000 | debug UART per DSDT; unused (no access) |
| tlmm 18 | – | – | enable for `VREG_NVME_3P3` (DSDT: TLMMGPIO 0x12 in the PCIe 6a power-up) |
| tlmm 51 / 67 | PEP handles 0x0400 / 0x0180 | – | IRQ touchscreen / EC HID (empirical) |
| tlmm 65 | – | – | EC reset (active high), reserved |
| tlmm 92 | GIO0 0x5C | – | lid / hall sensor |
| tlmm 149/150 | GIO0 0x95/0x96 | – | EC GPIOs (GFNA/GFN9), function unknown |
| tlmm 170/171 | GPU0 0xAA/0xAB | – | DP HPD / mux of the USB-C ports |

Rule of thumb: Windows `QUP_0_SE_n` = Linux `i2c<n>` (0xb80000+), `QUP_1_SE_n` = `i2c<8+n>`
(0xa80000+). Not swapped.

PCIe supplies per the Windows PEP tables (match the DTS): pcie6a `LDO2_J` 1.256 V,
`LDO1_D` 0.88 V, `LDO3_J` 0.88 V, GPIO 18; pcie4 `LDO3_E` 1.2 V, `LDO3_I` 0.88 V, `LDO3_J`,
`CLK7_A` (= `RPMH_LN_BB_CLK2`, WCN7850 reference clock; not referenced in the DTS yet).

EC protocol (for a future driver): i2c5 @0x5B, 6-byte command to reg 0x10, 3-byte reply from
reg 0x11; bank 0xC9 reg 0x6E/0x6F = mailbox, bank 0xC4 reg 0x4F = hotkey event. Battery and
charging go through pmic_glink (ADSP) as on the Zenbook, not through the EC. The EC firmware
identifies itself as `F01740D4.HT5306QA.312` (UEFI variable `AsusEcVersion`).

## Differences from the Zenbook A14 (and why)

- **HDMI bridge, `mdss_dp2`, `usb_1_ss2`** removed: the PZ13 has no third port. With those
  nodes present the msm component bind stalled (`aux_bridge: failed to acquire drm_bridge`).
- **`usb_mp` with HS PHYs only** (`usb_mp_qmpphy0/1` disabled): the cover's pogo connector
  (USB 2.0) is on the second port (xhci 1-2, hsphy1), port 0 is unconnected; the SS PHYs sporadically failed to initialise and
  took the controller down with them. Probably the same cause as PCIe (l3j/QREF); the cover
  does not need them anyway.
- **Audio without a codec**: the PZ13 has no headset jack and therefore no WCD9385; the Windows
  INF (`qcaudminiportCRD_Extension8380.inf`) disables `TopologySpeakerHeadset` and only has
  Speaker (smart amp, stereo) and a 4-microphone array. `swr1`/`swr2` stay disabled; `swr2`
  (6d30000) produced an interrupt storm with the ADSP running ("SWR CMD error", ~8600/5 s)
  that killed input and console and looked like an ADSP hang. The speakers are two WSA8845 on
  `swr0` as on the Zenbook (confirmed by SoundWire enumeration), the microphones are DMICs on
  the VA macro.
- **Camera LED, `spi10`** removed: Zenbook hardware absent from the PZ13 DSDT. The PZ13 has two
  PTN3222 eUSB2 repeaters (I2C 0x43/0x4f, resets TLMM 6/184), listed in `\_SB.USB3._CRS` as a
  raw buffer, which grepping the DSDT for the part name misses.
- **`vreg_l3j_0p8` always-on/boot-on**: see next section.
- **`gpio-reserved-ranges` + `<65 1>`**: EC reset, following Abel Vesa's Hamoa/Purwa series.
- Bus assignment of touchscreen and EC HID (i2c8/i2c0, see table).

## Solved: sporadic QMP PHY failures

Symptom: roughly every 4th–5th boot on battery came up without NVMe and/or WLAN,
`phy initialization timed-out` on `1bfc000`/`1c0e000` (and `88e3000`); almost never with the
charger connected.

Cause: `vreg_l3j_0p8` feeds the QREF block that generates the reference clocks of the QMP
PHYs. Windows votes `LDO3_J` for every PCIe port. In the Zenbook DTS l3j is only enabled as a
side effect of the USB/eDP PHY probes; whether it was already on when the PCIe PHYs
initialised depended on probe order and on the firmware state (on battery: off).

Fix: `regulator-always-on; regulator-boot-on;` on `vreg_l3j_0p8`. Result: 22/22 warm reboots
on battery clean. Not toggling the `phy_nocsr` reset in the retention path (a possible driver-side change)
only masks the status check: the link then fails with "Device found, but not active".
Upstream counterpart: Qiang Yu's series "Migrate x1e80100 TCSR to clk_ref helper" /
"hamoa/purwa: Add QREF regulator supplies" (linux-next). The x1p42100 gen4x4 PHY (pcie6a) has
no init tables in the driver; it runs purely on retention of the firmware configuration.

Side findings: ramoops is useless on this device (the firmware clears DRAM even on a warm
reset), the node is not in the DTS. A failed full init leaves a state that survives
`poweroff` and is only cleared by plugging in the charger.

## Keyboard cover (USB 0b05:1b6e "Z13 Soft Keyboard")

Full inventory from the HID report descriptors (`hid-decode`) and a key-by-key
capture of the vendor feature reports:

- **Interface .0003** (HID instance numbers as on a fresh boot; they change on every re-enumeration) = boot keyboard (6-key rollover) with Num/Caps/Scroll LED outputs;
  the Caps Lock LED works. Bound to hid-generic.
- **Interface .0004** = precision touchpad (report 0x54, 5 contacts, 124×76 mm, bound to
  hid-multitouch) plus a mouse-compat collection, a consumer-control collection (report 0x0a:
  mute/volume, works natively) and ASUS vendor collections: usage page 0xff31 report 0x5a
  (ROG keyboard: 15-byte feature commands, 2-byte hotkey input), 0xff30/0xb0 and 0xff36/0xb1
  (device/firmware IDs, 0xb1 carries a BCD build date 2024-07-24 10:56), 0xff32/0xbc (ID).
- ROG function mask (`5a 05 20 31 00 08` → byte 6 = `0x01`): backlight only. No Fn lock,
  no RGB/profiles, no backlight timeout command.
- Backlight: handshake "ASUS Tech.Inc." then `5a ba c5 c4 <0..3>` on report 0x5a, four
  levels. `install/kbdlight.py` → `/usr/local/bin/kbdlight`; the Fn daemon sends the last
  level set with Fn+F4 (kept in `/run`, so 1 after a boot) whenever it opens the cover
  (boot, reattach, resume).
- Fn layer (press `5a <code> 01`, release `5a 00 00`, repeats while held):

  | Key | Code | Function | Linux |
  |-----|------|----------|-------|
  | Fn+F1/F2/F3 | consumer 0xe2/0xea/0xe9 | mute / vol − / vol + | native |
  | Fn+F4 | 0xc7 | keyboard backlight cycle | daemon → `kbdlight` |
  | Fn+F5 / F6 | 0x10 / 0x20 | brightness − / + | `KEY_BRIGHTNESSDOWN/UP` |
  | Fn+F7 | – | display switch, sent as Super+P on the keyboard interface | native |
  | Fn+F8 | 0x7e | emoji | `KEY_EMOJI_PICKER` |
  | Fn+F9 | 0x7c | mic mute | `KEY_MICMUTE` |
  | Fn+F10 | 0xcb | ASUS AI noise cancelling | `KEY_PROG1` (free to bind) |
  | Fn+F11 | – | F11 | native |
  | Fn+F12 | 0x8b | (icon not identified) | `KEY_PROG2` (free to bind) |
  | Fn+Esc | 0x4e | Fn lock request | `KEY_FN_ESC`; the cover does not switch the layer itself, Windows' driver does, so Fn lock is not available |
  | Fn+arrows, Ins, Del, PrtSc, Backspace, Space | – | PgUp/PgDn/Home/End and the plain keys | native |

  The vendor codes are hid-asus's; hid-asus cannot take interface .0004 without losing the
  touchpad (the vendor part sits on the multitouch interface, unlike the ROG Flow Z13 folio),
  so `install/pz13-fnkeys.py` → `/usr/local/bin/pz13-fnkeys` (python3-evdev, hidraw → uinput,
  unit `install/pz13-fnkeys.service`) maps them in userspace until the kernel side exists.

## Installation (as set up here)

- Debian trixie via debootstrap on `nvme0n1p17` (ext4, label `pz13root`), GNOME, Mesa from
  trixie-backports, `firmware-atheros` (WCN7850), device firmware under
  `/lib/firmware/qcom/x1p42100/ASUSTeK/proart-pz13/` (`qcadsp8380.mbn`, `adsp_dtbs.elf`,
  `qccdsp8380.mbn`, `cdsp_dtbs.elf`, `qcdxkmsucpurwa.mbn`; copied from the Windows DriverStore).
- Boot chain: firmware → NVRAM entry `{bootmgr}`, whose path was redirected from Windows with
  `bcdedit /set "{bootmgr}" path \EFI\Boot\bootaa64.efi` to systemd-boot (Linux cannot write
  UEFI variables here; the firmware offers no fallback loaders; GRUB's chainloader fails on the
  Windows loader with 0xc00000bb) → systemd-boot → Debian (`loader/entries/pz13.conf` with a
  `devicetree` line, files under `ESP:/pz13/`, see `install/`) or Windows.
- `kernel-install` set to `layout=other`; `install/zz-pz13-esp` in
  `/etc/initramfs/post-update.d/` copies kernel, initrd and the DTB from `/boot/dtb/` to
  `ESP:/pz13/` (the kernel package's DTB only seeds `/boot/dtb/` when it is empty, so a
  hand-installed DTB survives `update-initramfs`).
- Kernel modules are zstd-compressed; a hand-built module must replace the `.ko.zst`, not sit
  next to it.
- Audio: AudioReach topology from
  [linux-msm/audioreach-topology](https://github.com/linux-msm/audioreach-topology) (the
  Surface Pro 12in description built additionally under the name `X1P42100-ASUS-ProArt-PZ13`,
  one extra line in its `CMakeLists.txt`) to
  `/lib/firmware/qcom/x1e80100/X1P42100-ASUS-ProArt-PZ13-tplg.bin`; UCM profile from `ucm2/`
  to `/usr/share/alsa/ucm2/Qualcomm/x1e80100/` plus the DMI entry in `x1e80100.conf`
  (trixie's alsa-ucm-conf does not know the device). `alsa-utils` for testing.
- Keyboard cover: `install/kbdlight.py` → `/usr/local/bin/kbdlight`, `install/pz13-fnkeys.py` → `/usr/local/bin/pz13-fnkeys` plus
  `install/pz13-fnkeys.service` → `/etc/systemd/system/` (needs `python3-evdev`;
  `systemctl enable --now pz13-fnkeys`).
- Lock screen and suspend (GNOME 48): without `install/pz13-sleep-lock@asus-proart-pz13`,
  suspend starts only 5 s after the request and after resume the screen goes dark again
  about 1.3 s after it came on, until touched. Cause (gnome-settings-daemon debug logs,
  mutter and gnome-shell sources): on "about to suspend", gnome-settings-daemon switches
  the display off immediately while gnome-shell is still animating the lock screen; with
  the display off, mutter 48's frame clock does not advance on this device (a pending
  frame is only completed when a newer frame supersedes it, and a second frame is only
  dispatched when rendering is slow), so the lock never completes (verified without
  suspend: display off via `PowerSaveMode`, then `org.gnome.ScreenSaver.SetActive true`
  never reports active until the display is on again). gnome-shell therefore keeps its
  delay inhibitor until logind's 5 s timeout, and the lock completes after resume and
  blanks the screen. The kernel side is clean (`drm_vblank_event_*` tracepoints show both
  commits completing). The extension makes the lock non-animated when the login manager
  reports "preparing for sleep", so the shield becomes active synchronously before the
  display goes off: suspend starts 0.2 s after the request and the lock screen stays on
  after the wake. The mutter stall itself remains (anything that has to animate while the
  display is off). Install: copy the directory to
  `~/.local/share/gnome-shell/extensions/`, log out and in, then
  `gnome-extensions enable pz13-sleep-lock@asus-proart-pz13`. A sleep hook must not sleep
  in the foreground: logind reports the resume to the desktop only after all hooks
  returned (`install/pz13-cover-usb-resume` defers its wait into a transient unit).
- Cover after the keyboard's firmware reset: `install/pz13-cover-usb-resume` to
  `/usr/lib/systemd/system-sleep/` (mode 755); it sends the backlight feature report after
  every resume, without which the cover emits no Fn-layer reports after its reset.
- Camera in desktop apps: Debian's WirePlumber 0.5.8 does not create a PipeWire node for
  libcamera cameras by default (only the raw CAMSS V4L2 nodes show up in `wpctl status`).
  Copy `install/wireplumber-10-libcamera.conf` to
  `~/.config/wireplumber/wireplumber.conf.d/10-libcamera.conf` (needs
  `libspa-0.2-libcamera`), `systemctl --user restart wireplumber`; the Sources list then
  shows the cameras and GNOME Snapshot can use the front one. The same file names the colour
  camera "PZ13 front camera" by its device path (both sensors report themselves as "front")
  and hides the IR camera from PipeWire: apps such as Snapshot take the first camera in their
  list, the enumeration order varies per boot, and the IR sensor's only format (10-bit mono)
  cannot be displayed, which otherwise shows up as "not-negotiated" / "no camera" on some
  boots. Face-unlock tools read the IR sensor via V4L2/libcamera directly. After a reboot and
  GNOME login, Snapshot shows the front camera without any command.
  Add the user to the `video`
  group (`usermod -aG video <user>`, re-login): WirePlumber enumerates the cameras at session
  start, before logind has granted the seat ACL on `/dev/media0`, and never retries, so
  without the group the cameras are missing after every login until
  `systemctl --user restart wireplumber`. WirePlumber also
  logs "Could not open any dma-buf provider": `/dev/dma_heap/*` is root-only for the user
  (no seat ACL on it). That is harmless, libcamera's software ISP then uses plain memory.
  Do **not** make the heaps accessible: with access, libcamera allocates from the 128 MB
  CMA pool and 1080p streams fail with "error set output format: -22". The OV5675 is the one whose object path ends in `camera@36`.
- Display colour profile: ASUS ships a per-unit factory calibration of the OLED on the
  Windows partition, `ProgramData/ASUS/ASUS System Control Interface/AsusOptimization/Splendid/HT5306QA_QCOM_834C41B0.icm`
  (ICC v2, measured primaries, white point and per-channel tone curves, no VCGT; the
  `_CMDEF` variant and the `PQConfig*.dv` files add Microsoft HDR and Dolby Vision blocks
  that Linux does not use). Mount the Windows partition read-only, copy the file somewhere outside
  `~/.local/share/icc` (the import copies it there itself and refuses an existing copy), then
  `colormgr import-profile <file>`, `colormgr device-add-profile <display> <profile>` and
  `colormgr device-make-profile-default <display> <profile>` (device and profile paths from
  `colormgr get-devices` / `colormgr find-profile-by-filename`); GNOME's Colour settings then
  show it as the display's profile. The profile is not redistributed here.
- Camera colour: libcamera 0.4 (trixie) has no colour matrix in its software ISP, the
  picture stays greenish. Install libcamera and PipeWire from trixie-backports (0.7.1 /
  1.6.9: `apt install -t trixie-backports libcamera-tools libcamera-ipa
  gstreamer1.0-libcamera pipewire pipewire-bin wireplumber libspa-0.2-libcamera`, then
  `systemctl --user daemon-reload && systemctl --user restart pipewire wireplumber`) and
  copy `install/libcamera-ov5675.yaml` to `/usr/share/libcamera/ipa/simple/ov5675.yaml`
  and `install/libcamera-ov13858.yaml` to `/usr/share/libcamera/ipa/simple/ov13858.yaml`.
  The matrices in it are Qualcomm's own CC13 tuning for this module, decoded from
  `com.qti.tuned.ov5675.bin` in the Windows camera package.

## Open

1. **Audio polish**: submit the topology line to audioreach-topology and the UCM profile to
   alsa-ucm-conf; 4-channel capture (the topology currently allows 2); DP audio over USB-C
   untested.
2. **Keyboard backlight / hotkeys in the kernel**: hid-asus has to coexist with the
   multitouch interface; the vendor code table above is what such support needs. Userspace
   daemon until then.
3. **DTS**: clarify `VREG_MISC_3P3` (Zenbook, purpose on the PZ13 unknown); add
   `RPMH_LN_BB_CLK2` for the WCN7850; map tlmm 149/150 (EC GPIOs).
4. **Cameras**: front, IR and rear work (see "What works"). Open: the IR illuminator (PM8550 flash
   LED, Zenbook A14 uses channel 4 at 700 mA, PZ13 channel unknown), a libcamera tuning file
   for the HM1092 and the OV13858, the rear camera's focus motor and EEPROM nodes, the
   ov13858 driver's missing selection ioctls (libcamera warns about them), and
   upstreaming the combo-mode PHY support properly (a binding for it is under review on
   linux-media, ours is a submode hack). Sensor DSP and fan are separate topics.
5. **DisplayPort alt mode**: works on both ports (see "What works"). Still open: DP audio, and the harmless
   boot-time `msm_dp_display_probe: init sub module failed` from one controller that binds a
   second later.
6. **Upstream**: QREF/l3j report to linux-arm-msm; DTS to jglathe and upstream.
7. **Cover USB port after the keyboard's firmware reset** (see "What works"): solved by not using USB wakeup
   on `usb_mp`; the kernel-side weakness (xhci/dwc3-qcom not recovering a port whose device
   disconnects during a wakeup-enabled resume) remains and would be worth reporting with the
   log. The two eUSB2 repeaters of `usb_mp` are described
   (PTN3222 at 0x43 and 0x4f on the EC's I2C bus, resets TLMM 6 and 184, taken from the
   `\_SB.USB3` resources); they probe but did not change this behaviour. Which repeater
   serves which port is unverified (Zenbook mapping assumed).
8. **Suspend/resume leftovers**: the mutter 48 stall (no frame progress while the display is
   off, see "What works") is worked around by the gnome-shell extension and should be
   reported upstream with the evidence. No alarm wake: the PMIC RTC's alarm is owned by
   the ADSP (`qcom,no-alarm`).
9. **Panel**: described with the dedicated `samsung,atna33xc20` driver and the PMIC enable
   line like the sibling ASUS boards (`patches/0009` adds `samsung,atna33aa08` to the
   binding). Measured with the DisplayPort driver's debug log, a power-save off/on cycle
   brings the link up 0.24 s after the request with either description: the DP driver keeps
   the panel powered across power-save, so the generic driver's conservative timings were
   never hit here. Adopted for correctness, not speed. The factory colour profile is on the Windows
   partition (see Installation).

## Upstream references (linux-arm-msm)

- "Migrate x1e80100 TCSR to clk_ref helper" / "hamoa/purwa: Add QREF regulator supplies"
  (Qiang Yu, v4, linux-next) – the proper solution for the l3j/QREF issue.
- "purwa: Fix swapped USB QMP PHY vdda-phy/vdda-pll supplies" (Manivannan) – check
  when re-enabling the `usb_mp` SS PHYs.
- "Mark the EC reset gpio as reserved" (Abel Vesa) – TLMM 65.
- `x1p42100-microsoft-sp12in` (Surface Pro 12in) – Purwa detachable as reference.
- Zenbook A14 camera support (ov02c10 RGB on cci1/csiphy4 in jglathe's tree; "HM1092 IR camera
  and ASUS Zenbook A14 camera support", Ramshouriesh R, driver v6 on
  linux-media, applied here as `patches/0001-0002`; DTS held back behind six prerequisite series) + x1p42100 CAMSS – template for
  the cameras, but the Zenbook follows the Qualcomm MTP wiring and the PZ13 the CRD/QRD one
  (`notes/cameras.md`).
