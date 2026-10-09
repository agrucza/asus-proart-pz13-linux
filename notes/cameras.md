# Cameras on the ProArt PZ13 – what the Windows driver package says

All three cameras **work**: the front OV5675 (GNOME Snapshot with colour), the IR HM1092
(raw 560×360 mono stream) and the rear OV13858 (640×480 processed stream via libcamera).
The wiring below is decoded from the Windows DriverStore dump (`qccam*8380` packages) and
the DSDT and confirmed on the tablet.

Front camera: regulators accepted by RPMh, `ov5675 N-0036` (the CCI bus
number varies per boot) linked to `msm_csiphy4` (2592×1944 SGRBG10), libcamera lists
"Internal front camera", and `sudo cam -c1 -C3 -s width=640,height=480 -F/tmp/f-#.raw`
delivers ABGR8888 frames at 30 fps that show the user.
All nine camera rails exist in cmd-db (`ldob5`, `ldob7`, `ldom1`–`ldom7`). Full-resolution
processed output fails to allocate its fourth 20 MB buffer from the 128 MB CMA pool
(libcamera prefers the CMA heap); `cma=256M` on the kernel command line should avoid it
(untested), a smaller stream does. The role=raw request falls back to processed output in
libcamera 0.4.0. TLMM 6, which the Windows front-camera sequence also toggles, is the reset
of the first eUSB2 repeater of usb_mp (`\_SB.USB3._CRS`), not a camera supply; the OV5675
streams without it.

Colour: libcamera 0.4's software ISP has no CCM, the picture is green. With libcamera 0.7.1
and PipeWire 1.6.9 from trixie-backports plus `install/libcamera-ov5675.yaml` the colours are
right. The matrices come from `com.qti.tuned.ov5675.bin` (QTI Chromatix, same entry-table
format as the sensor module binary: 56-byte entries from 0xd0, data section at 0x7be74 per
the header at 0x90): module `cc13_ipe_v2` → `mod_cc13_trigger_data` → CCT trigger regions
2300–2600 / 2750–3300 / 3700–4300 / 4700–5300 / 6200–6800 K, each `region` = 9 floats
(row-major, rows sum to 1) + 3 offsets. Black level 4096/65535 (OV5675 BLC target 64/1023).
Channel means of a test frame went from R43/G49/B39 (0.4, uncalibrated) to R127/G135/B134.

## Sensors

| Position | Sensor | Windows package | Linux driver | Notes |
|----------|--------|-----------------|--------------|-------|
| Front (user-facing, RGB) | OmniVision **OV5675**, 5 MP, 2 CSI lanes | `qccamfrontsensor_extension8380` (`com.qti.sensormodule.ov5675.bin`) | `ov5675` (mainline, `CONFIG_VIDEO_OV5675=m` in the pz13 kernel) | driver insists on 19.2 MHz xvclk; default I2C address 0x36 |
| Front IR (Windows Hello) | Himax **HM1092**, 1 MP mono NIR, 1 CSI lane | `qccamauxsensor_extension8380` (`com.qti.sensormodule.hm1092.bin`, module vendor "azurewave") | `hm1092` from linux-media (Ramshouriesh R, v6, applied as `patches/0001-0002`; `himax,hm1092`, supplies `dovdd`/`avdd`/`dvdd`, 24 MHz, `reset-gpios`, 180 MHz link, 1 lane) | Zenbook A14 uses it at I2C 0x24 |
| Rear (world-facing) | OmniVision **OV13858**, 13 MP, 4 CSI lanes, with DW9714P VCM and M24C64 EEPROM | `qccamrearsensor_extension8380` (`com.qti.sensormodule.ov13858.bin`) | `ov13858` (mainline, no regulator handling, needs 19.2 MHz) | default I2C address 0x10 |

The sensor module binaries are Qualcomm "QTI Chromatix" parameter blobs; stream
configurations confirm the resolutions (2592×1944, 560×360, 4224×3136) and lane assignments
(`laneAssign` 0x0010 / 0x0002 / 0x3210).

## Which variant Windows uses on this board

The sensor devices in the DSDT (`CAMF` = QCOM0C06 front, `CAMI` = QCOM0C99 IR, `CAMS` =
QCOM0C26 rear) carry no `_CRS`; the wiring lives in Windows "PEP resource" binaries that the
INF selects by hardware ID. Our DSDT reports `_SUB` = `PSUB` = **"CRD08380"** and `_HRV` = 1
(`SDFE` == 0x9A), so Windows matches

- front: `ACPI\VEN_QCOM&DEV_0C06&SUBSYS_CRD08380&REV_0001` → section `CameraFrontSensor_Device_QRD_Pw` → `SCFG_FRONT_D2L_QRD.bin` + `CAMF_RES_QRD.bin`
- IR: `…DEV_0C99&SUBSYS_CRD08380&REV_0001` → `CameraAuxSensor_Device_QRD_Pw` → `SCFG_AUX_8340_QRD.bin` + `CAMI_RES_QRD.bin`
- rear: `…DEV_0C26&SUBSYS_CRD08380` → `CameraRearSensor_Device_QRD` → `SCFG_REAR_QRD.bin` + `CAMS_RES_QRD.bin`

i.e. the ASUS board follows the Qualcomm CRD/QRD reference layout. Caveat: the DriverStore
holds staged packages, the registry (which says what is actually bound) is not dumped. The
upstream Zenbook A14 camera patches match the *MTP* files of the same package instead
(front: LDO7_B + LDO3_M, 19.2 MHz; IR: reset 109, MCLK0, LDO4_M + LDO7_M), so the two ASUS
machines are **not** wired the same and the Zenbook DTS cannot be copied blindly.

`tools/aeob-parse.py` decodes these binaries (TLV: u16 type, u16 len; 0 = u32, 1 = string,
3 = container).

## Decoded power-on sequences (QRD files)

Tuple fields after a TLMM pin are `(func/value, ?, dir, drive, ?)` as far as can be told:
`{235 1 1 1 3 0}` is the CCI I2C function, `{237 0 0 1 0 0}` then `{237 1 0 1 0 0}` is a
GPIO driven low and then high. Regulator votes are `(enable, µV, mode?, 7, 0)`.

Platform (`CAMP_RES_QRD.bin`, device `\_SB.CAMP`, identical in the MTP file): rail `mmcx`,
`gcc_camera_*`, `cam_cc_titan_top_gdsc`, CCI0/CCI1 clocks, ICP 400 MHz; TLMM 101–106 as
`cci_i2c` (cci0_i2c0 = 101/102, cci0_i2c1 = 103/104, cci1_i2c0 = 105/106), TLMM 96/97/98/100
as `cam_mclk`/`cam_aon` (MCLK0/1/2/4), TLMM 99 (MCLK3) left as GPIO. The DSDT `CAMP._CRS`
lists CCI registers 0x0ac13000/15000/16000/19000, IRQs 491/492/303 and GpioIo 99/110.

### Front OV5675 (`CAMF_RES_QRD.bin`)

```
cpas_ahb 80 MHz; TLMM 235,236 = aon_cci (cci1_i2c1); TLMM 237 out low (reset)
LDO3_M 1.8 V on (DOVDD); LDO5_B 3.0 V on (AVDD)
TLMM 6 out high (eUSB2 repeater reset of usb_mp, unrelated to the camera); 1 ms
TLMM 237 high (release reset); 1 ms; MCLK4 = 24 MHz
off: 237 low, 236/235 to GPIO, MCLK4 off, LDO3_M off, LDO5_B off, TLMM 6 low
```
→ Linux: `&cci1_i2c1 { camera@36 { compatible = "ovti,ov5675"; reset-gpios = <&tlmm 237
GPIO_ACTIVE_LOW>; clocks = <&camcc CAM_CC_MCLK4_CLK>; assigned-clock-rates = <19200000>;
avdd-supply = LDO5_B 3.0 V; dovdd-supply = LDO3_M 1.8 V; dvdd-supply = dummy (no external DVDD rail); data-lanes = <1 2>;
} }` on `csiphy4` (same PHY/CCI/MCLK/reset as the CRD, Zenbook A14, XPS 13 9345, T14s and
Yoga Slim 7x front cameras, which all sit on cci1_i2c1 / MCLK4 / tlmm 237 / csiphy4). The
OV5675 driver only accepts 19.2 MHz; the sensor supports it. TLMM 6 (`qup0_se1`, unused on
the PZ13) is the eUSB2 repeater reset of usb_mp; the camera does not need it.

### Front IR HM1092 (`CAMI_RES_QRD.bin`)

```
TLMM 103,104 = cci_i2c (cci0_i2c1)
LDO4_M 1.808 V (DOVDD); LDO7_M 2.8 V (AVDD); LDO5_B 3.0 V; LDO1_M 1.2 V (DVDD)
TLMM 111 out low (reset); MCLK1 = 24 MHz; TLMM 111 high; 1 ms
```
→ `&cci0_i2c1 { camera@24 { compatible = "himax,hm1092"; reset-gpios = <&tlmm 111 …>;
MCLK1 (tlmm 97) 24 MHz; dovdd = LDO4_M, avdd = LDO7_M, dvdd = LDO1_M; 1 lane } }`. The CSIPHY
is not in these files; it is csiphy4 lane 2 in combo mode with the RGB sensor
(see "IR camera: combo mode" below; the Zenbook puts its IR sensor on csiphy0 with
MCLK0/tlmm 109). IR illuminator: the Zenbook
drives it from `pm8550_flash` channel 4; `CAMP_RES_QRD.bin` lists a `\_SB.FLSH` device
(QCOM0C27) here too, contents empty (flash handled by the PMIC driver).

### Rear OV13858 (`CAMS_RES_QRD.bin`)

```
TLMM 109 out low (reset)
LDO7_B 2.8 V (AVDD); 1 ms; LDO6_M 1.8 V; LDO2_M 1.2 V (DVDD); LDO4_M 1.8 V (DOVDD);
LDO5_M 2.8 V (VCM); LDO5_B 3.0 V; MCLK0 = 24 MHz; 5 ms; TLMM 109 high; 1 ms
```
→ The sequence names no CCI pins; the platform file configures cci0_i2c0 (101/102) and
cci1_i2c0 (105/106), and an I2C scan with the sensor powered found the module's VCM
(0x0c) on cci0_i2c0. The sensor's address is in `com.qti.sensormodule.ov13858.bin`
(`sensorDriverData` blob: slave 0x6c 8-bit = **0x36**, 16-bit register addresses, chip-ID
register 0x300b = 0xd855), not the driver's default 0x10; the actuator blob says 0x18 (=
0x0c) and the EEPROM blob 0xa0 (= 0x50). Node: `camera@36` `ovti,ov13858` on `cci0_i2c0`,
4 lanes on csiphy0, MCLK0 (tlmm 96, `cam_mclk`) at 19.2 MHz for the Linux driver, reset
tlmm 109. The mainline `ov13858` driver is ACPI-only; `patches/0006` adds supplies, reset,
OF match and runtime-PM power sequencing. Rails by elimination: AVDD LDO7_B, DVDD LDO2_M,
DOVDD LDO6_M, and the sensor only answers while LDO4_M (the IR camera's I/O rail, same CCI
controller) is on as well (LDO5_B and LDO5_M are not needed for the sensor; LDO5_M powers
the VCM). VCM `dongwoon,dw9714` @0x0c (vcc = LDO5_M) and EEPROM `atmel,24c64` @0x50 (vcc = LDO6_M,
read-only; content `01 18 03 26` then 0xff) probe; the sensor's `lens-focus` yields the
ancillary link (visible via MEDIA_IOC_G_TOPOLOGY, not in `media-ctl -p`). Focus moves:
Laplacian-variance sharpness 100 at `focus_absolute=0` vs 25 at 1000 on the same scene.
Tuning: `com.qti.tuned.ov13858.bin` has the CC13 block at the same place as the front
file (five 24-byte CCT triggers 2300–2600 … 6200–6800 K at 0x9d602, then five 48-byte
regions); `install/libcamera-ov13858.yaml` carries those matrices.
Also in both tuning files, right after the CC13 block: the gamma15 tone curves (six
257-entry float tables 0→1023 per file, three channels × two regions, at 0x9da92 front /
0x9db12 rear). Front and rear use identical curves; region 0 fits a plain power law with
exponent 0.43 (rms 0.04), region 1 0.54. libcamera 0.7.1's software ISP takes the gamma
only as a runtime control (`Gamma`, default 0.5 in its `Adjust` algorithm), not from the
tuning file, so this is recorded here but not applied. The bls12 black-level record could
not be identified by value; the tuning files use the OmniVision default (64/1023).

## Rails

The sequences vote on PM8010 ("M") LDOs 1–7 and on PM8550 ("B") LDO5/LDO7; all exist in
cmd-db. The dtsi defines `regulators-8` (`qcom,pm8010-rpmh-regulators`, `qcom,pmic-id =
"m"`, supply parents as on the X1E CRD, l6 fed from `vreg_s4c_1p8` like l3/l4) with
`vreg_l1m_1p2`, `vreg_l2m_1p2`, `vreg_l3m_1p8`, `vreg_l4m_1p8` (always-on, see the rear
camera), `vreg_l6m_1p8`, `vreg_l7m_2p8`, and `vreg_l5b_3p0` / `vreg_l7b_2p8` in the B-rail
node. Not defined: LDO5_M 2.8 V (the rear VCM; parent presumably `vreg_bob1`). The PM8010 SPMI node
(`pm8010: pmic@c` in `hamoa-pmics.dtsi`) stays disabled; RPMh rails do not need it.

## Kernel pieces available in the pz13 tree (jglathe 7.2.5)

`qcom-camss` with `qcom,x1e80100-camss` (ports 0–3 = csiphy0/1/2/4), `phy-qcom-mipi-csi2`
(`qcom,x1e80100-mipi-csi2-combo-phy`), `camcc-x1p42100` (`CONFIG_CLK_X1P42100_CAMCC=m`),
`i2c-qcom-cci`, `ov5675`, `ov13858`, `ov02c10` – all modules. Added by `patches/`: the
`hm1092` driver, CSIPHY combo mode, and `qcom,x1p42100-camss` (see "Purwa CAMSS" below). The
Zenbook A14 ov02c10 node in this tree is the reference for the csiphy4 path.

## Verification

1. PM8010 presence: `ls /sys/bus/spmi/devices` cannot tell (the SPMI node is disabled in
   `hamoa-pmics.dtsi`); `grep ldom /sys/kernel/debug/cmd-db` shows all seven M rails.
2. CAMSS, CCI and CSIPHY4 probe together with the front sensor.
3. Front camera: OV5675 on cci1_i2c1 / csiphy4 with LDO3_M and LDO5_B, TLMM 6 not needed;
   probes and streams, libcamera capture and GNOME Snapshot work.
4. IR: needs the hm1092 driver and the combo-mode patches (next section); streams.
5. Rear: with `patches/0006` the OV13858 probes at 0x36 on cci0_i2c0 and streams 640×480
   at 30 fps through csiphy0 (4 lanes). Diagnosis path: a diagnostic module build that
   leaves the sensor powered after a failed chip-ID read, `i2cdetect` on all CCI buses
   (VCM found on bus cci0_i2c0 once LDO5_M was on), the address from the sensor-module
   binary, then rail elimination with `regulator-always-on` test DTBs.

## IR camera: combo mode

Configurations that give no frames: HM1092 on csiphy1 (hardware version reads 0 on this
SoC, PHY not present on Purwa), on csiphy0 (lane 0 and lane 2), on csiphy4 lane 2 with the
stock drivers. The sensor answers regardless: with runtime PM forced on
(`echo on > /sys/bus/i2c/devices/*-0024/power/control`) `i2ctransfer -f -y 1 w2@0x24 0x00
0x00 r2` returns `0x10 …`, the first byte of the HM1092 ID.

Why: the module descriptions say `isComboMode = 1` for both front sensors and `laneAssign`
`0x10` (OV5675) / `0x2` (HM1092): both share **csiphy4** in Qualcomm "combo mode", RGB on
DL0/DL1 with the dedicated clock lane, IR on DL2 with **DL3 as its clock lane** (downstream
`cam_csiphy_core.c`: lane_assign 2 + combo => `DPHY_LANE_2 | DPHY_LANE_3`). The stock
drivers cannot do that: `phy-qcom-mipi-csi2` ignores the DT lane positions (always lanes
0..n-1 plus the dedicated clock, a TODO in the source), `camss` binds one lane configuration
per CSIPHY and creates immutable links, so two sensors on one PHY both end up in every
pipeline. Upstream has a combo-mode *binding* under review (Bryan O'Donoghue, x1e80100-camss
"combo-mode endpoints") but no PHY implementation yet.

What the patch in `patches/0003-*` does: mutable sensor links on a shared CSIPHY, lane
configuration taken from the enabled link, lane assignment + combo flag passed to the PHY via
`phy_set_mode_ext()` submode (nibbles = physical lane per logical lane, bit 16 combo, bit 31
valid), PHY enables DL2+DL3 without the clock bit for the second port (`lanes enable 0x50`)
and programs the lanes from a combo table in which the DL3 block (0x0C00) is configured like
the clock lane (0x0E00) plus `0x0C28 = 0x0E` and `0x0828 = 0x0A`, following the pattern of
Qualcomm's `csiphy_2ph_v2_1_0_combo_mode_reg`. PHY register layout on x1e80100: DL0 0x000,
DL1 0x400, DL2 0x800, DL3 0xC00, CLK 0xE00, common block 0x1000.

Result: `sudo cam -c /base/soc@0/cci@ac15000/i2c-bus@1/camera@24 -C3 -s role=raw
-F/tmp/ir-#.raw` → 560×360 Y10P at 29.7 fps, recognisable room in ambient NIR, sensor
mounted upside down (`rotation = <180>` in the DTS). libcamera's software ISP cannot process
the mono format, so apps only get the raw stream; a mono path or a tuning file is the next
userspace step. The front camera keeps working through the same PHY (links are switched by
libcamera). Not done: the IR illuminator (`\_SB.FLSH`, PM8550 flash; Zenbook A14 uses
`led-sources = <4>`, 700 mA, via the hm1092 `leds` property).

Module handling on the tablet: modules are `.ko.zst` and the PHY module also lives in the
initramfs (`update-initramfs -u` after replacing it); `install/zz-pz13-esp` keeps the
maintained DTB on the ESP across `update-initramfs`.

## Purwa CAMSS

With the X1E80100 CAMSS description from hamoa.dtsi every suspend logs `cam_cc_ife_1_gdsc
status stuck at 'off'` and every resume `'on'`, with a WARN each. X1P42100
has no IFE1/SFE and only CSIPHY0 and CSIPHY4 (`camcc-x1p42100.c` has no `ife_1` GDSC or
clocks; Wenmeng Liu's `qcom,x1p42100-camss` binding lists `ife0` + `top`, two IOMMU
streams, 12 register ranges, 14 clocks), but hamoa.dtsi's node describes the full X1E80100
CAMSS and purwa.dtsi does not override it. Fix: `patches/0004/0005` (X1P42100 CAMSS
support, applied with fuzz; plus `CAMSS_X1P42100` in this tree's `camss-csiphy-3ph-1-0.c`
switches; `phys`/`phy-names` added to the in-tree binding because this tree's camss still
takes the PHYs that way) and in the dtsi `/delete-node/ &camss` + a new `isp@acb7000` node
from the binding example, `&camcc` switched to `qcom,x1p42100-camcc` (driver already in the
tree). Ports: port@0 = csiphy0, port@1 = csiphy4 (RGB endpoint@4 lanes 0-1, IR endpoint@5
lane 2). With this description the GDSC warnings are gone (kernel -7).
