#!/bin/bash
# DisplayPort alt-mode diagnostics for the PZ13. Run as root on the tablet:
#   sudo ./pz13-dpdiag.sh snapshot          # state now
#   sudo ./pz13-dpdiag.sh watch             # enable debug, then plug the adapter; Ctrl-C to stop
set -u
dyndbg() {
  echo "module pmic_glink_altmode +p" > /sys/kernel/debug/dynamic_debug/control 2>/dev/null
  echo "module ps883x +p"            > /sys/kernel/debug/dynamic_debug/control 2>/dev/null
  echo "module ucsi_glink +p"        > /sys/kernel/debug/dynamic_debug/control 2>/dev/null
  echo "module typec_ucsi +p"        > /sys/kernel/debug/dynamic_debug/control 2>/dev/null
  echo "module pmic_glink +p"        > /sys/kernel/debug/dynamic_debug/control 2>/dev/null
  echo "file drivers/gpu/drm/msm/dp/* +p" > /sys/kernel/debug/dynamic_debug/control 2>/dev/null
}
snapshot() {
  echo "### $(date -Is) kernel $(uname -r)"
  echo "## typec ports"
  for p in /sys/class/typec/port[0-9]; do
    [ -d "$p" ] || continue
    echo "-- $p: role=$(cat $p/data_role 2>/dev/null | tr -d '\n') power=$(cat $p/power_role 2>/dev/null | tr -d '\n') orient=$(cat $p/orientation 2>/dev/null) pwr_op=$(cat $p/power_operation_mode 2>/dev/null) usb_pd=$(cat $p/usb_power_delivery_revision 2>/dev/null)"
    for m in $p/port*.[0-9]*; do [ -d "$m" ] && echo "   mode $m: svid=$(cat $m/svid 2>/dev/null) active=$(cat $m/active 2>/dev/null) desc=$(cat $m/description 2>/dev/null)"; done
    for pa in $p/port*-partner; do
      [ -d "$pa" ] || continue
      echo "   partner: $(cat $pa/accessory_mode 2>/dev/null) n_altmodes=$(cat $pa/number_of_alternate_modes 2>/dev/null) supports_pd=$(cat $pa/supports_usb_power_delivery 2>/dev/null)"
      for m in $pa/port*-partner.[0-9]*; do [ -d "$m" ] && echo "     partner mode $m: svid=$(cat $m/svid 2>/dev/null) vdo=$(cat $m/vdo 2>/dev/null) active=$(cat $m/active 2>/dev/null)"; done
      [ -d $pa/identity ] && echo "     identity: id_header=$(cat $pa/identity/id_header 2>/dev/null) product=$(cat $pa/identity/product 2>/dev/null) product_type_vdo1=$(cat $pa/identity/product_type_vdo1 2>/dev/null)"
    done
    for c in $p/port*-cable; do [ -d "$c" ] && echo "   cable: type=$(cat $c/type 2>/dev/null) plug=$(cat $c/plug_type 2>/dev/null)"; done
  done
  echo "## retimers / muxes"
  ls -l /sys/class/retimer/ /sys/class/typec_mux/ 2>/dev/null
  echo "## DRM connectors"
  for c in /sys/class/drm/card*-*; do echo "   $(basename $c): $(cat $c/status 2>/dev/null) enabled=$(cat $c/enabled 2>/dev/null)"; done
  echo "## ucsi debugfs"
  ls /sys/kernel/debug/usb/ucsi/ 2>/dev/null
  echo "## recent kernel messages (typec/altmode/dp/ucsi)"
  dmesg -T | grep -iE "altmode|typec|ucsi|ps883|retimer|msm-dp|dp_display|\bdp[0-9]?\b|hpd|glink" | tail -60
}
case "${1:-snapshot}" in
  snapshot) snapshot ;;
  watch) dyndbg; snapshot; echo "### now plug the adapter/monitor; watching dmesg"; dmesg -wT | grep --line-buffered -iE "altmode|typec|ucsi|ps883|retimer|msm-dp|dp_display|hpd|glink|drm" ;;
esac
