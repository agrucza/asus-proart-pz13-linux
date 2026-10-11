#!/bin/bash
# Build the sensor-core configuration tree the ASUS ProArt PZ13's ADSP expects
# from the Windows driver package qcsensorsconfigcrd8380 (a copy of the
# DriverStore folder, or the folder on a mounted Windows partition), in the
# layout the FastRPC file service (adsprpcd, sensors domain) serves:
#   vendor/etc/sensors/sns_reg_config, vendor/etc/sensors/config/*.json,
#   sys/devices/soc0/{hw_platform,soc_id,...}, persist/sensors/registry/registry
# The files are Qualcomm's and stay on your machines; nothing here is redistributed.
#
#   pz13-sns-config.sh <qcsensorsconfigcrd8380.inf_arm64_*> <output dir>
set -euo pipefail
pkg=${1:?driver package folder}; out=${2:?output directory}
[ -f "$pkg/sns_reg_config" ] || { echo "no sns_reg_config in $pkg" >&2; exit 1; }
rm -rf "$out"; mkdir -p "$out/vendor/etc/sensors/config" "$out/sys/devices/soc0" "$out/persist/sensors/registry/registry"
find "$pkg" -maxdepth 1 -type f ! -iname '*.inf' ! -iname '*.cat' ! -iname '*.pnf' -exec cp -t "$out/vendor/etc/sensors/config/" -- {} +
mv "$out/vendor/etc/sensors/config/sns_reg_config" "$out/vendor/etc/sensors/"
for f in hw_platform soc_id platform_subtype platform_subtype_id platform_version revision; do
    [ -f "$out/vendor/etc/sensors/config/$f" ] && cp "$out/vendor/etc/sensors/config/$f" "$out/sys/devices/soc0/"
done
sed -i 's/\r$//' "$out/vendor/etc/sensors/sns_reg_config" "$out"/vendor/etc/sensors/config/json.lst "$out"/vendor/etc/sensors/config/*.json "$out"/sys/devices/soc0/* 2>/dev/null || true
chmod -R a+rX "$out"
echo "$(find "$out" -type f | wc -l) files in $out (platform $(cat "$out/sys/devices/soc0/hw_platform"), soc_id $(cat "$out/sys/devices/soc0/soc_id"))"
