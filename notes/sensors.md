# Sensors: the Qualcomm Sensor Core and the accelerometer

The PZ13's motion sensors are not on any bus the application processor owns. They belong to
the Qualcomm Sensor Core (SSC) running on the ADSP: the DSP firmware contains the sensor
drivers and offers the data over a QMI service (service 400, "Snapdragon Sensor Core
service", on the ADSP's QRTR node). Windows lists the result as two "Qualcomm All-Ways Aware
Sensor Platform" devices (display and keyboard, ACPI `QCOM0693`/`QCOM0694`, depending only on
the ADSP and its IPC) and a software orientation sensor on top.

What the core offers on this machine, asked with `tools/pz13-ssc-probe.py`:

| data type | present |
|---|---|
| `accel` | yes (Bosch BMI3x0 IMU in the display, I3C on the sensor core's own bus) |
| `gyro` | yes (same IMU) |
| `motion_detect` | yes (derived) |
| `mag`, `ambient_light`, `proximity`, `pressure`, `device_orient` | no |

## The configuration the core needs from the OS

The sensor core boots with no sensors: it reads its configuration (which chips on which bus,
calibration, the registry database) from the host file system at runtime over FastRPC, the
"sensors" protection domain of the ADSP. Windows serves those files through its FastRPC
daemon; without a server the QMI service is up but every sensor lookup comes back empty.

The files are the Windows driver package `qcsensorsconfigcrd8380` (Qualcomm's reference
configuration; the PZ13 uses it unchanged, platform `CRD`, SoC id 555 which the sensor JSON
files accept next to Purwa's 635). `tools/pz13-sns-config.sh <package folder> <output>`
turns that folder (from the Windows partition's `DriverStore/FileRepository` or a copy) into
the tree the file service serves:

```
vendor/etc/sensors/sns_reg_config        # tells the core where to find the rest
vendor/etc/sensors/config/*.json         # sensor registry: chips, buses, rates, calibration
sys/devices/soc0/{hw_platform,soc_id,platform_subtype,...}
persist/sensors/registry/registry/       # the core writes its database back here
```

The files are Qualcomm's and stay on the machine; they are not in this repository.

The server is `adsprpcd` from [quic/fastrpc](https://github.com/quic/fastrpc), attached to
the sensors domain (`adsprpcd sensorspd adsp` with `ADSP_LIBRARY_PATH` pointing at the
tree). The [sl7-sensors](https://github.com/valeronm/sl7-sensors) package (made for the
Surface Laptop 7, same SoC family and mechanism) ships a built `adsprpcd`, a systemd unit
started by udev when `/dev/fastrpc-adsp` appears, and serves `/var/lib/sl7-sensors/sns-config`.
It is used for exactly that here; its own light-sensor proxy and its setup script are not
(no light sensor on the PZ13, and the setup script looks for a package name the PZ13 does
not have). Once the tree is served the core registers the sensors within a second and keeps
them even if the daemon stops; it has to run again after every boot.

## The protocol

QMI over `AF_QIPCRTR` (socket family 42). The service is found through the QRTR name
server (lookup on node 1 port 0xFFFFFFFE, service 400; node 5 port 21 here). Requests use
QMI message 0x20 with TLV 1 = payload, indications are 0x21/0x22 with TLV 1 = client id and
TLV 2 = payload; the payload TLV starts with a u16 count before the protobuf bytes. The
payloads are Qualcomm's `sns_client`/`sns_suid`/`sns_std_sensor` protobufs (published in
[qualcomm/sensinghub](https://github.com/qualcomm/sensinghub), `apis/proto/`):

- sensor lookup: request message 512 to the SUID lookup sensor
  `{0xABABABABABABABAB, 0xABABABABABABABAB}` with the data type string; event 768 returns
  the sensor ids.
- stream: message 513 (`sns_std_sensor_config`, `sample_rate` float, 12.5 and 25 Hz work)
  to the sensor's id; the samples come as event 1025 with `repeated float data`, three
  values in m/s² for the accelerometer; a rate of 0 stops the stream. An unsupported
  request is answered with event 130, not with a QMI error.

`tools/pz13-ssc-probe.py` implements this without dependencies: without arguments it lists
which data types exist, `pz13-ssc-probe.py accel 10` streams the accelerometer for 10 s.

## The daemon

`install/pz13-sensor-proxy` owns `net.hadess.SensorProxy` on the system bus, the interface
GNOME, KDE and `monitor-sensor` use, as iio-sensor-proxy would for an IIO accelerometer.
It waits for the accelerometer to appear, then reports `HasAccelerometer`, streams the sensor
at 12.5 Hz while a client has claimed it (GNOME claims it within two seconds of the daemon
starting) and publishes `AccelerometerOrientation` computed with iio-sensor-proxy's
algorithm (35° thresholds, 5° hysteresis). The sensor core's axes are mapped to the
convention that algorithm expects: upright reads y = +9.8 and right-edge-up reads x = +9.8
on the PZ13, both inverted in the daemon. Measured: normal, right-up, left-up and bottom-up
all correct, the desktop rotates with the tablet.

Installed as `/usr/local/bin/pz13-sensor-proxy` with `install/pz13-sensor-proxy.service`
(type dbus, enabled) and `install/net.hadess.SensorProxy.service` in
`/usr/local/share/dbus-1/system-services/`, which takes precedence over iio-sensor-proxy's
activation file so a D-Bus request for the name starts this daemon. iio-sensor-proxy stays
installed and inactive. The bus policy that lets root own the name comes from the
iio-sensor-proxy package (and from sl7-sensors).

GNOME rotates only with the cover detached: mutter manages the panel orientation only in
"touch mode", and without a tablet-mode switch (the GPIO keys carry only the lid switch)
touch mode means "touchscreen present and no pointer device"; the cover's touchpad is a
pointer (`meta-seat-impl.c`, `update_touch_mode`). With the cover attached
`org.gnome.Mutter.DisplayConfig PanelOrientationManaged` reads false while the daemon keeps
reporting the orientation changes (observed 2026-10-16); the auto-rotate quick-settings
toggle follows the same property. A uinput `SW_TABLET_MODE` switch would let GNOME rotate
with the cover attached, but nothing on the device reports the cover's fold angle, so it
would have to be toggled by hand (not done). `pz13-sensor-proxy --debug` prints one line
per second with the raw and mapped values and the orientation.

Side effect of the streaming: the ADSP toggles its SMP2P "handover" bit towards the
remoteproc driver on every sensor sample, about three times a second, and the stock
driver logged "qcom_q6v5_pas 6800000.remoteproc: Handover signaled, but it already
happened" for each (13957 lines in 75 minutes). The same was found for the SLPI of a
Samsung tablet (aaronsb/sm-x800-linux#46). Harmless; `patches/0016` (the upstream
one-shot handover IRQ) disables the interrupt after the first handover.

## Not done

The gyroscope and the motion-detect sensor are not exposed (nothing on the desktop consumes
them). The "keyboard" sensor platform device of the firmware has no sensor behind it on this
machine (only one accelerometer id exists). The Windows "human presence sensor" package is
untouched.
