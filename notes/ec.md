# The ASUS embedded controller

ACPI `\_SB.I2C6` (QUP_0_SE_5, Linux `i2c5`), slave 0x5b, 400 kHz; the firmware's EC code is
`Asus_plat_ec.asl`. Everything below was read from the DSDT and confirmed on the device with
`i2c-tools`. The Linux driver is `patches/0014` (`drivers/platform/arm64/asus-proart-pz13-ec.c`,
compatible `asus,proart-pz13-ec`), the device-tree node sits on `&i2c5`.

## Register protocol

A register is addressed by a page byte and an offset. Two SMBus transactions per access:

```
write block at command 0x10:  0x10, <page>, <offset>      # select
read  byte  at command 0x11                               # value
write byte  at command 0x11:  0x11, <value>               # write the selected register
```

With `i2c-tools` (bus 3 on the installed system):

```
ecrd() { sudo i2cset -y 3 0x5b 0x10 $1 $2 i && sudo i2cget -y 3 0x5b 0x11 b; }      # page offset
ecwr() { sudo i2cset -y 3 0x5b 0x10 $1 $2 i && sudo i2cset -y 3 0x5b 0x11 $3 b; }   # page offset value
```

The ACPI page bytes 0xC4, 0xC6 and 0xC9 are not I2C addresses (the EC answers only at 0x5b).

## Pages and registers

| Page | Offset | Meaning |
|------|--------|---------|
| 0xC4 | 0x30 | command register of the command interface; the EC clears it when the command is taken |
| 0xC4 | 0x31, 0x32 | command arguments 1 and 2 |
| 0xC4 | 0x4F | event (SCI) number, read and cleared by the firmware's event handler; the firmware's event table lists Fn hotkeys, lid, power events |
| 0xC4 | 0x70.. | EC version string (reads as zeros here) |
| 0xC6 | 0x00 | written by the firmware's "fan EC interface" (`QCOM0D05`, function 1) with a temperature; has no effect on the fan on this firmware |
| 0xC6 | 0x0A, 0x0B | the EC's own temperature sensors, degrees Celsius; they sit on the heat path, not on the die: 15 to 20 °C below the SoC under full load (62/65 at 88 °C, 72/74 after 7 minutes), within 1 °C of it as soon as the load stops, 30/32 at idle with the SoC at 37 |
| 0xC6 | 0x10 | fan control/status: bit 7 fan enabled, bit 6 full speed (the ASUS WMI "CPU fan control" bit; 9457 rpm when set), bits 0 and 2 set by default (0x85) |
| 0xC6 | 0x18, 0x19 | fan tachometer, low/high byte, rpm |
| 0xC6 | 0x84 | flags; bit 0 "temperature valid", set by the firmware after a temperature push |
| 0xC9 | 0x40..0x4F | mailbox data |
| 0xC9 | 0x6E | mailbox command |
| 0xC9 | 0x6F | mailbox status/control: wait until 0, write 0x80 (write) or 0x20 (read) before the command, bit 7 set when a read answer is ready |

## Command interface (page 0xC4)

```
wait until 0x30 == 0; write 0x31 = arg1, 0x32 = arg2, 0x30 = command; wait until 0x30 == 0
```

Commands seen in the firmware: 0x01 (select; `0x8C` before a temperature push), 0x02
(platform notifications: 0x81 display on/off, 0x84 lowest power state, 0x85 modern standby
enter/exit, 0x86 "OS running", sent once when the OS brings the bus up), 0x04 (write a byte
into EC RAM: arg1 offset, arg2 value), 0x05 (read EC RAM / battery pass-through; the ACPI
thermal zone `THZ0` reads offsets 1 and 2). The ASUS WMI method `0x00130001` is a generic
pass-through to this interface (`ECAT`: get version, read/write byte, command byte, battery
manufacturer access).

## Mailbox (page 0xC9)

Block transfers for the fan-curve functions of the ASUS WMI interface: `0x20` selects a
fan/profile byte (0x80/0x81/0x82 default curves of the three profiles, 0x40 the user curve,
0x20 the limit block), `0x21` reads 16 bytes (default curve), `0x22` writes 16 bytes (user
curve), `0x24` reads 8 bytes. The default curve of profile 0x80 reads

```
temperatures  50 54 58 62 66 70 73 78     (degrees Celsius)
fan levels     1  8 19 32 40 48 63 71
```

## How the fan is driven

The EC does not measure the SoC. It runs the fan from a temperature the OS writes into EC
RAM through the command interface, which is what the ASUS platform software does on Windows
(WMI method `0x00110022`):

```
cmd 0x01 arg 0x8C 0x00            # select
cmd 0x04 arg 0x83 <temperature>   # degrees Celsius
cmd 0x04 arg 0x82 0x00            # high byte
page 0xC6 offset 0x84 |= 0x01     # temperature valid
```

Measured on the device (fan speed after 15 to 45 s at the given value):

| reported °C | 25 | 30 | 33 | 36 | 40 | 45 | 70 | 85 |
|---|---|---|---|---|---|---|---|---|
| rpm | 1089 | 1392 | 1563 | 1741 | 1970 | 2236 | 3400 | 4007 |

Sampled every 5 s while cooling down after a load (the fan lags the reported value by a
few seconds, so these read slightly high):

| reported °C | 43 | 45 | 47 | 49 | 51 | 53 | 55 | 57 | 60 | 62 | 64 | 67 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rpm | 2236 | 2331 | 2467 | 2597 | 2767 | 2871 | 2933 | 3049 | 3272 | 3369 | 3517 | 3673 |

The speed follows the reported temperature continuously, the EC keeps a value until the next
one is written, and the fan stops only when 0 is reported ("no reading"). Without any report
the fan never starts: with the stock kernel the SoC reached 72 °C under load with the fan
off, the EC's own sensors reading 45 °C.

Things that do not drive the fan: fan-page register 0x00 (the firmware's `QCOM0D05` function
1 writes it, the EC ignores it, refreshed or not), the flag in 0x84 on its own, the ACPI fan
trip-point requests (the firmware's handler for them has no EC access).

Under a sustained CPU+GPU load the SoC settled at 93 °C with the EC answering a reported
90 °C with 4578 rpm (2026-10-16); the curve continues flat above that (85 → 4007, 90 →
4578 rpm), while bit 6 of register 0x10 (full speed) gives 9600 to 9800 rpm. The SoC's
thermal zones carry no passive trip point, only the critical one at 115 °C, so nothing else
limits the temperature.

The driver reports the hottest of the thermal zones listed in its `asus,thermal-zones`
property (the eight CPU core "top" sensors, the eight "btm" sensors, which read up to 4 °C
higher, and the four GPU sensors) once a second, writes only when the degree value changes,
reports 0 on suspend and the real temperature again on resume. From a reported 85 °C on it
sets the full-speed bit and clears it again once the reading is below 75 °C (measured:
4107 rpm at 84 °C, 9626 rpm in the next sample after 85 °C was reported, held through
readings between 81 and 91 °C); the bit is cleared for suspend, and a freshly probed driver
adopts the bit's state so that a reload does not leave it set. Full speed buys little at
the top end: with `stress-ng --cpu 8` plus glmark2 the SoC settles at 89 to 92 °C
(hottest `btm` sensor) at 9700 rpm against 93 °C at 4600 rpm on the curve; full speed
starts about 50 s after the load, the EC's own sensors reach 73/75 °C after 6 minutes
(2026-10-16, charger plugged, battery full: the charger does not cover this load, the
battery supplies 5.5 W on top, 12 to 18 W when half full), and the fan drops back to the
curve within 5 s of the load ending. hwmon `pz13_ec`:
`fan1_input`, `temp1_input`/`temp2_input` (EC sensors), `temp3_input` (`soc_reported`, the
last value written to the EC).

## Not done

The event register (hotkeys through the EC; the cover's keys come over USB and work without
it), the platform notifications (display off, modern standby), the battery pass-through, the
fan-curve mailbox from Linux.
