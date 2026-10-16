# ASUS ProArt PZ13 Linux port – working notes for Claude Code

Project: bring up Linux on the ASUS ProArt PZ13 (HT5306QA, Snapdragon X Plus X1P-42-100
"Purwa"). The device tree, UCM profile and install helpers live in this repo; README.md is
the authoritative status document. Read it first. This file covers the working setup and
the things that are easy to get wrong.

## Machines

| Host | Role | Notes |
|------|------|-------|
| `debian` (this machine) | build host, x86_64 | kernel tree, DTS edits, cross builds, topology builds, this repo |
| `ProArtPZ13` (the tablet) | target, arm64 | SSH alias `pz13wifi` (user's ssh config); the WLAN address changes with DHCP |

The tablet runs the installed system from NVMe (`nvme0n1p17`, label `pz13root`), boots via
systemd-boot from the Windows ESP (`nvme0n1p12`, mounted at `/boot/efi`, mode 0077 → always
`sudo` for `ls`/`cat` there). A fallback USB stick exists (`/dev/sda`, GRUB on sda2, tools and
logs on sda4 "PZ13") but is normally not plugged in.

## Paths on the build host

- Kernel tree: `~/src/linux-pz13` (jglathe `jg/ubuntu-qcom-x1e-7.2.y`, 7.2.5). Our DTS files are
  copied into `arch/arm64/boot/dts/qcom/`; `Makefile` and `Documentation/devicetree/bindings/arm/qcom.yaml`
  already carry the entry/compatible. The tree has local changes: PHY_INIT_COMPLETE_TIMEOUT
  100 ms in the three QMP PHY drivers (`phy-qcom-qmp-{pcie,usb,combo}.c`, harmless, can
  stay), and sixteen commits on top of jglathe's branch (exported to `patches/` in this repo): the HM1092
  IR sensor driver + binding (v6 from linux-media, `b4 am
  20260801-hm1092-driver-v6-0-5979f223748a@gmail.com`), our CSIPHY combo-mode support
  (camss + phy-qcom-mipi-csi2), X1P42100 CAMSS support (Wenmeng Liu v3,
  `b4 am 20260511-purwa_camss-v2-0-22608ab9126c@oss.qualcomm.com` picks v3; driver patch
  applied with `patch --fuzz=3`), our ov13858 device-tree support (`patches/0006`), the
  QSEECOM allow-list entry (`patches/0007`) the ELAN stylus-battery quirk (`patches/0008`) and the
  ATNA33AA08 panel binding entry (`patches/0009`), three msm DP changes (`patches/0010`-`0012`:
  audio startup while the display is off, no forced retrain from the hot-plug handler, the
  connector probe leaves the plugged flag alone) and the upstream q6apm start-count fix
  (`patches/0013`, applied with `git am`, original author kept) and our EC driver for the fan
  (`patches/0014`, `drivers/platform/arm64/asus-proart-pz13-ec.c` + binding) and the uleds
  hardware-change reporting for the keyboard backlight (`patches/0015`, `drivers/leds/uleds.c`
  + `Documentation/leds/uleds.rst`; `CONFIG_LEDS_USER=m` was already set) and the upstream
  one-shot handover IRQ for qcom_q6v5 (`patches/0016`, Abel Vesa, `git am` + a hand-ported
  hunk because this tree shares one init between prepare and attach; it stops the
  "Handover signaled, but it already happened" flood, three lines a second from the ADSP's
  sensor core);
  `CONFIG_VIDEO_HM1092=m` and `CONFIG_EC_ASUS_PROART_PZ13=m` in `.config`. Nothing else (no
  nocsr patch: it only masks the status check).
- Single out-of-package module build (e.g. for hm1092): `make ARCH=arm64
  CROSS_COMPILE=aarch64-linux-gnu- LOCALVERSION=-pz13 prepare`, then the same with
  `M=drivers/media/i2c modules`, then `scripts/sign-file sha512 certs/signing_key.pem
  certs/signing_key.x509 drivers/media/i2c/hm1092.ko`. Without `LOCALVERSION=-pz13` the
  vermagic becomes `7.2.5+` and the installed kernel refuses the module. Module goes to
  `/lib/modules/7.2.5-pz13/kernel/drivers/media/i2c/` on the tablet + `depmod -a`.
- Kernel packages: `~/src/linux-image-7.2.5-pz13_7.2.5-N_arm64.deb`; `-21` (patches through 0016) is the current one, `-20` has patches through 0015 with the fan's full-speed switch in 0014, `-19` the same without the switch; -12 was a lockdep test build, -15 is deleted. Bump `N` on every build. Diagnostic DTS variants left in
  the tree break `bindeb-pkg` once the dtsi moves on; remove probe variants right after use. When running a build in the background, do not wrap it in a subshell with
  a trailing `echo`: the task's exit code is then the echo's, not make's. Judge a package build
  by the log and the presence of the `.deb`.
- This repo: `~/src/asus-proart-pz13-linux` (dts/, install/, ucm2/, audio/, notes/, tools/, README.md).
- Git identity: commits in the kernel tree use its configured identity (`agrucza <a.grucza@gmx.net>`);
  never pass `-c user.*` or write a Signed-off-by with another address. The user commits and
  pushes this repo.
- Windows DriverStore dump: `~/pz13-dump/firmware/` (189 driver folders; audio in
  `qcaudminiport*`, `qcacsp_crd8380`, cameras in `qccamplatform*`, ADSP in `qcsubsys_ext_adsp8380`);
  ACPI tables in `~/pz13-dump/acpi/` (`dsdt.dsl` is the decompiled DSDT).
- Device firmware for the tablet: `~/pz13-firmware/qcom/x1p42100/ASUSTeK/proart-pz13/`.
- Audio topology source: `~/src/audioreach-topology`; `X1P42100-ASUS-ProArt-PZ13.m4` there is a
  copy of this repo's `audio/*.m4`, and one extra CMakeLists.txt line builds it (in-source
  cmake build: `make` in that directory, output `qcom/x1e80100/X1P42100-ASUS-ProArt-PZ13-tplg.bin`).
  Backups of files replaced on the tablet go to `~` there, never `/tmp` (cleared at boot).
- Debian arm64 chroot for initrd experiments: `~/arm64root` (rarely needed now).

## Paths on the tablet

- Loader entry: `/boot/efi/loader/entries/pz13.conf`; kernel/initrd/DTB under `/boot/efi/pz13/`.
- DTB also under `/boot/dtb/`; the hook `/etc/initramfs/post-update.d/zz-pz13-esp` copies
  kernel, initrd and the DTB from `/boot/dtb/` to the ESP on every initramfs update (the
  package DTB only seeds `/boot/dtb/` when it is empty).
- Firmware: `/lib/firmware/qcom/x1p42100/ASUSTeK/proart-pz13/`, GPU microcode in
  `/lib/firmware/qcom/`, audio topology `/lib/firmware/qcom/x1e80100/X1P42100-ASUS-ProArt-PZ13-tplg.bin`.
- UCM: `/usr/share/alsa/ucm2/Qualcomm/x1e80100/` (+ our block appended to `x1e80100.conf`).
- Cover helpers: `/usr/local/bin/kbdlight`, `/usr/local/bin/pz13-fnkeys` (systemd unit
  `pz13-fnkeys.service`, ordered `Before=upower.service`); the daemon provides the LED
  `/sys/class/leds/asus::kbd_backlight` (uleds, needs `patches/0015` for Fn+F4).
- Journal is persistent (`/etc/systemd/journald.conf.d/ProArtPZ13.conf`).

## Standard workflows

DTB only (most changes):
```
cd ~/src/linux-pz13
cp ~/src/asus-proart-pz13-linux/dts/x1*.dts* arch/arm64/boot/dts/qcom/
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- qcom/x1p42100-asus-proart-pz13.dtb
scp arch/arm64/boot/dts/qcom/x1p42100-asus-proart-pz13.dtb agrucza@pz13wifi:/tmp/
# on the tablet:
sudo cp /tmp/x1p42100-asus-proart-pz13.dtb /boot/dtb/ && sudo cp /tmp/x1p42100-asus-proart-pz13.dtb /boot/efi/pz13/ && sync && sudo reboot
```

Full kernel package:
```
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j$(nproc) LOCALVERSION=-pz13 \
  KDEB_PKGVERSION=$(make kernelversion)-N DPKG_FLAGS=-d bindeb-pkg
# tablet: sudo dpkg -i /tmp/linux-image-7.2.5-pz13_7.2.5-N_arm64.deb  (hook updates the ESP)
```

Diagnostic DTB variants: include the board .dts from a `-probe.dts`, build it by name, give it
its own loader entry (`pz13-probe.conf`) so the default entry stays untouched; remove both
afterwards.

Quick health check after a boot (battery reboot series used 11 boots per variant):
```
lsblk | grep -c nvme; nmcli device | grep -c wl; sudo dmesg | grep -ciE "timed-out|not active"
```
Expected `18 / 2 / 0`.

## Things that bite

- `sudo` on the tablet does not know `~/.local/bin` (pipx tools like `hid-decode`): use the
  full path.
- Audio/GPU tests over SSH hit the wrong session: PipeWire/ALSA devices belong to the seat
  session (logind ACL). Run `wpctl`, `glxinfo`, `eglinfo`, `arecord` from a terminal inside
  the GNOME session, or use `sudo` for raw ALSA (`hw:0,…`).
- `od` on hidraw buffers 16 bytes; use `sudo stdbuf -o0 od -An -tx1 -w3 -v /dev/hidrawN`.
- The cover's vendor interface is the HID device on the cover's USB interface 1 (`1-2:1.1`);
  both its HID instance number (`.000N`, `.0004` on a fresh boot) and the hidraw number change
  on every enumeration, so the python helpers match `0003:0B05:1B6E.*` + interface 1.
- `i2cdetect` `UU` means "a driver is bound", not "device answers".
- ACPI GpioInt numbers in this DSDT are mostly PEP handles, not TLMM numbers (0x400 → tlmm 51,
  0x180 → tlmm 67); GpioIo pins in `CAMP` (0x63/0x6E) do look like TLMM numbers.
- Windows INF files are UTF-16: `strings -el file.inf`.
- Removing a DTS node that another node references breaks the dtc build; grep before
  deleting.
- Kernel params on the tablet: `consoleblank=0 clk_ignore_unused pd_ignore_unused arm64.nopauth`
  (no `regulator_ignore_unused`).
- The generic ZAP shader does not work on this device; keep the ASUS `qcdxkmsucpurwa.mbn`.
- Kernel modules on the tablet are zstd-compressed (`*.ko.zst`). A hand-built `.ko` placed
  next to the stock `.ko.zst` loses: move the `.zst` away (keep it as `.orig`), then `depmod -a`.
- `update-initramfs` / `dpkg -i` run the ESP hook `install/zz-pz13-esp`, which copies the DTB
  from `/boot/dtb/` and only seeds `/boot/dtb/` from the kernel package when it is empty (a
  hook that copies the package DTB unconditionally clobbers a hand-installed one). After any
  DTB build, copy the DTB to both `/boot/dtb/` and
  `/boot/efi/pz13/` as before. This also holds for a DTS change shipped in a kernel
  package: `dpkg -i` leaves the old DTB in place (2026-10-16: -20 ran with the old zone
  list until the package's DTB from `/usr/lib/linux-image-7.2.5-pz13/qcom/` was copied);
  `cmp` the installed DTB against the package's to check.

## Where things stand

Working: boot, display (dedicated OLED panel driver, factory ICC profile in colord), GPU,
NVMe, WLAN, BT (ASUS Pen paired, battery over BLE), USB-C incl. DP alt mode, touch+pen,
cover (all keys incl. Fn layer via daemon, backlight as a LED class device that GNOME owns, survives suspend), volume buttons, fan (EC
driver, `notes/ec.md`),
lid switch, battery/UCSI (charge limit via UPower), RTC + UEFI variables, suspend, audio
(speakers + mics), all three cameras, fan, accelerometer/screen rotation. See README "What works".

Open, in the order we intended to tackle them:
1. Push repo, put the URL into `notes/report-qmp-pcie-phy-purwa.md`, send it to
   linux-arm-msm@vger.kernel.org (CC Konrad Dybcio, Stephan Gerhold, Johan Hovold, Qiang Yu)
   with a good and a failing dmesg.
2. `make dtbs_check` is clean for our files (dt-schema 2026.9 via pipx, `~/.local/bin` must be
   in PATH for make); the UFS/ADC warnings come from the SoC/PMIC includes. Command: `make ARCH=arm64
   CROSS_COMPILE=aarch64-linux-gnu- CHECK_DTBS=y W=1 qcom/x1p42100-asus-proart-pz13.dtb`.
3. Mail to Luke Jones (hid-asus) with the cover inventory from README; ask how kernel-side
   support for a vendor collection on the multitouch interface should look, and where the
   `asus::kbd_backlight` LED should live on a non-x86 device (it is created by asus-wmi,
   hid-asus only forwards to it).
4. DisplayPort alt mode works on both ports (passive adapter). DP audio works, opt-in
   (`install/ucm-dp-audio.conf`, `install/wireplumber-20-dp-audio.conf`, topology in
   `audio/`). Open quirk: the DSP refuses the first `APM_CMD_GRAPH_START` of
   `DISPLAY_PORT_RX_0` after a boot (error 1); the next session works. Rebuilding the graph
   inside the failed trigger wedges the DSP (tested, kernel -15, removed). Needs ADSP firmware
   knowledge; upstream contact is the user's decision. All four DP fixes (0010-0013) are
   verified by tests on kernel -14. Every capture with a
   monitor attached costs the user a USB-C cable swap: one combined block per cycle at most.
5. Cameras: front OV5675, IR HM1092 and rear OV13858 work, see `notes/cameras.md` (PZ13 = CRD/QRD layout,
   Zenbook = MTP layout; decoder `tools/aeob-parse.py` on
   `~/pz13-dump/firmware/qccam*_extension8380*/*.bin`; PM8010 rails confirmed via
   `/sys/kernel/debug/cmd-db`; colour via libcamera 0.7.1 from trixie-backports +
   `install/libcamera-ov5675.yaml` / `libcamera-ov13858.yaml`, Qualcomm CC13 matrices from
   the tuning bins; rear VCM via V4L2 `focus_absolute`, no AF in libcamera's soft ISP).
   Open: IR illuminator, mono path in libcamera, `cma=256M` for full-res capture (untested).
6. Cover after suspend: `usb_mp` without `wakeup-source` (the cover cannot wake the tablet;
   its firmware reset on a held key wedges the port with wakeup on),
   helpers match the cover by USB interface 1 instead of the HID instance number, the Fn
   daemon sends the backlight feature report when it opens the cover, and the sleep hook
   `install/pz13-cover-usb-resume` re-sends it (level read from the LED) after every resume.
   Keep it at that; re-binding the controller, a udev helper or polling in the daemon do not
   help.
7. DTS: `VREG_MISC_3P3` purpose, `RPMH_LN_BB_CLK2` for WCN7850, tlmm 149/150, then upstream
   patches (dt-bindings + dts) via b4/git send-email. Upstream correspondence (this, the
   QREF report, the mutter report in `notes/mutter-powersave-stall.md`, hid-asus) is
   deferred by the user.
8. The fan: the EC runs it from a temperature the OS pushes through its command interface
   (`notes/ec.md`); the driver polls the CPU/GPU zones (top, btm, gpuss) once a second and
   sets the EC's full-speed bit from a reported 85 °C until below 75 °C (verified
   2026-10-16; the EC's own curve only gave 4600 rpm at 93 °C). Kernel-tree commits are
   local only and exist to generate `patches/`; the user has accepted that (asked why, then
   "fold it into the commit and regenerate 0014"); folding is done with
   `git commit --fixup=amend:<commit>` and `GIT_SEQUENCE_EDITOR=true git rebase -i
   --autosquash --autostash <base>` (works non-interactively, base 4a0b49df1c46 for 0014).
9. Sensors: the IMU is on the ADSP's sensor core (QMI service 400). The core needs the
   Windows `qcsensorsconfigcrd8380` tree served over FastRPC (sl7-sensors deb's adsprpcd,
   tree from `tools/pz13-sns-config.sh`, at `/var/lib/sl7-sensors/sns-config`);
   `install/pz13-sensor-proxy` owns net.hadess.SensorProxy (`notes/sensors.md`). Axes: x and
   y inverted vs. iio-sensor-proxy's convention. Debug: `sudo pz13-sensor-proxy --debug`.
10. Testing a DTB safely: install it under another name on the ESP with its own loader
   entry and `sudo bootctl set-oneshot <entry>` (UEFI variables work since kernel -9).
11. Keyboard backlight (verified 2026-10-12, kernel -19): the daemon creates
   `asus::kbd_backlight` via `/dev/uleds` (max 3, level 1 at start), UPower takes the first
   LED whose name contains `kbd_backlight` (scanned once at UPower's start, hence the unit
   ordering; the tests used a reboot after installing), gnome-settings-daemon owns it from
   then on (slider, dim at idle, off with the screen, restore on activity). Fn+F4 cycles
   0-3 in the daemon and reports the level by writing an int to the uleds descriptor
   (`patches/0015`: `brightness_hw_changed`), UPower passes it on as "internal" and GNOME
   shows the indicator. Dead ends, do not retry: `KEY_KBDILLUMTOGGLE` (GNOME's toggle is
   off/on only, tested on -18), UPower `SetBrightness` from the daemon (gsd ignores
   "external" changes, no indicator), `KEY_KBDILLUMUP` (gsd clamps at max, no wrap). A
   screen-state poll in the daemon (`bl_power`) worked but is unnecessary with the LED.
12. Battery log (2026-10-16): `install/pz13-battery-log` + timer + udev rule + sleep hook
   write `/var/log/pz13-battery.csv` on the tablet; `tools/pz13-battery-report.py` reads it.
   qcom_battmgr exposes no `capacity`/`health`, the percentage is derived from the energy
   values. First reading: energy_full 59.8 of 70.0 Wh design after 6 cycles.
13. ADSP "Handover signaled, but it already happened" flood (2026-10-16): the ADSP's
   sensor core toggles the SMP2P handover bit on every sensor sample (same finding as
   aaronsb/sm-x800-linux#46 for the SLPI); upstream fix is `patches/0016`. Harmless apart
   from the journal (13957 lines in 75 minutes before the patch).

## Conventions

- README.md is the single status document; update it when something is verified or changed,
  and only claim what was observed (logs, tests). Keep it in English.
- DTS comments in English; remaining open points carry a `PZ13-TODO` marker.
- Usernames: `agrucza` on both machines.
- Never copy Windows firmware into the repo (redistribution); the README tells users where
  to get it.
