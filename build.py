import os, tarfile
from deb_builder import create_deb

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(REPO_DIR, 'src')
PACKAGES_DIR = os.path.join(REPO_DIR, 'packages')
os.makedirs(PACKAGES_DIR, exist_ok=True)

control_content = """Package: com.hoaug.a12powerfix
Name: A12 Power & Charging Clean Fix
Version: 2.0.0
Architecture: iphoneos-arm64e
Maintainer: hoaug <hoaug@duck.com>
Author: hoaug
Section: System
Priority: optional
Description: Unified power & thermal fix for Apple A12 (XS/XS Max/XR) on iOS 18 RootHide Dopamine. Completely eliminates 77% charging stall (0x04000000), bypasses JEITA 41C thermal charge cutoff (NotChargingReason = 16), removes Kiosk 1% battery lock, permanently suppresses the yellow overheat lock screen (SBThermalEmergencyAlertItem), and unlocks 101 load index zero-throttling.
Tag: role::hacker, purpose::extension
"""

postinst_content = """#!/bin/sh
set -e

echo "[A12PowerFix] Installing v2.0.0 Unified Power & Thermal Fix..."

JBROOT=""
if command -v jbctl >/dev/null 2>&1; then
    JBROOT=$(jbctl | grep -o '/.*' | head -n1)
fi
if [ -z "$JBROOT" ] && [ -d "/var/jb" ]; then
    JBROOT="/var/jb"
fi
if [ -z "$JBROOT" ]; then
    JBROOT=$(find /var/containers/Bundle/Application/ -name '.jbroot*' -type d 2>/dev/null | head -n1)
fi

echo "[A12PowerFix] Active JBROOT: $JBROOT"

ENT="$JBROOT/etc/a12powerfix/ent.plist"
if [ ! -f "$ENT" ]; then
    ENT="/tmp/ent.plist"
fi

# 1. Sign binaries with ldid
if command -v ldid >/dev/null 2>&1; then
    ldid -S"$ENT" "$JBROOT/usr/bin/a12chargingd" 2>/dev/null || true
    ldid -S"$ENT" "$JBROOT/usr/lib/TweakInject/KillThermalAlert.dylib" 2>/dev/null || true
fi
chmod 755 "$JBROOT/usr/bin/a12chargingd" 2>/dev/null || true
chmod 755 "$JBROOT/usr/lib/TweakInject/KillThermalAlert.dylib" 2>/dev/null || true
chmod 644 "$JBROOT/usr/lib/TweakInject/KillThermalAlert.plist" 2>/dev/null || true

# 2. Deploy ThermalMonitor plist to mnt
mkdir -p /mnt/System/Library/ThermalMonitor 2>/dev/null || true
cp -f "$JBROOT/mnt/System/Library/ThermalMonitor/D331pAP-Info.plist" /mnt/System/Library/ThermalMonitor/ 2>/dev/null || true
cp -f "$JBROOT/mnt/System/Library/ThermalMonitor/D321AP-Info.plist" /mnt/System/Library/ThermalMonitor/ 2>/dev/null || true
cd /mnt/System/Library/ThermalMonitor/ && ln -sf D331pAP-Info.plist D331AP-Info.plist 2>/dev/null || true

# 3. Reload a12chargingd daemon
killall -9 a12chargingd 2>/dev/null || true
launchctl unload "$JBROOT/Library/LaunchDaemons/com.hoaug.a12chargingd.plist" 2>/dev/null || true
launchctl load -w "$JBROOT/Library/LaunchDaemons/com.hoaug.a12chargingd.plist" 2>/dev/null || "$JBROOT/usr/bin/a12chargingd" >/dev/null 2>&1 &

# 4. Disable heavy background telemetry and intelligence daemons
DAEMONS="
com.apple.modelcatalogd
com.apple.intelligenceplatformd
com.apple.homed
com.apple.ThreadCommissionerService
com.apple.triald
com.apple.momentsd
com.apple.inputanalyticsd
com.apple.wifianalyticsd
com.apple.audioanalyticsd
com.apple.ReportCrash
"
for d in $DAEMONS; do
    launchctl disable "system/$d" 2>/dev/null || true
done

# 5. Clean logs and reset powerd & SpringBoard
rm -rf /private/var/mobile/Library/Logs/CrashReporter/* 2>/dev/null || true
killall -9 powerd 2>/dev/null || true
if command -v sbreload >/dev/null 2>&1; then
    sbreload 2>/dev/null || true
fi

echo "[A12PowerFix] v2.0.0 installed successfully! No overheat alert, full 100% charging unlocked."
exit 0
"""

prerm_content = """#!/bin/sh
set -e

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    echo "[A12PowerFix] Removing A12 Power & Charging Clean Fix..."
    killall -9 a12chargingd 2>/dev/null || true
    launchctl unload /Library/LaunchDaemons/com.hoaug.a12chargingd.plist 2>/dev/null || true
    rm -f /usr/lib/TweakInject/KillThermalAlert.dylib 2>/dev/null || true
    rm -f /usr/lib/TweakInject/KillThermalAlert.plist 2>/dev/null || true
    if command -v sbreload >/dev/null 2>&1; then
        sbreload 2>/dev/null || true
    fi
fi
exit 0
"""

with open(os.path.join(SRC_DIR, 'a12chargingd'), 'rb') as f:
    a12chargingd_bin = f.read()

with open(os.path.join(SRC_DIR, 'com.hoaug.a12chargingd.plist'), 'rb') as f:
    a12chargingd_plist = f.read()

with open(os.path.join(SRC_DIR, 'KillThermalAlert.dylib'), 'rb') as f:
    kill_alert_dylib = f.read()

with open(os.path.join(SRC_DIR, 'KillThermalAlert.plist'), 'rb') as f:
    kill_alert_plist = f.read()

with open(os.path.join(SRC_DIR, 'D331pAP-Info.plist'), 'rb') as f:
    d331p_bytes = f.read()

with open(os.path.join(SRC_DIR, 'D321AP-Info.plist'), 'rb') as f:
    d321_bytes = f.read()

with open(os.path.join(SRC_DIR, 'ent.plist'), 'rb') as f:
    ent_bytes = f.read()

control_files = [
    ('./control', control_content.strip().encode('utf-8') + b'\n', 0o644),
    ('./postinst', postinst_content.strip().encode('utf-8') + b'\n', 0o755),
    ('./prerm', prerm_content.strip().encode('utf-8') + b'\n', 0o755)
]

data_files = [
    # Directories
    {'path': './usr', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './usr/bin', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './usr/lib', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './usr/lib/TweakInject', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './Library', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './Library/LaunchDaemons', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './etc', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './etc/a12powerfix', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './mnt', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './mnt/System', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './mnt/System/Library', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './mnt/System/Library/ThermalMonitor', 'type': tarfile.DIRTYPE, 'mode': 0o755},

    # Daemon
    {'path': './usr/bin/a12chargingd', 'content': a12chargingd_bin, 'mode': 0o755},
    {'path': './Library/LaunchDaemons/com.hoaug.a12chargingd.plist', 'content': a12chargingd_plist, 'mode': 0o644},

    # SpringBoard Tweak (Kill Yellow Alert)
    {'path': './usr/lib/TweakInject/KillThermalAlert.dylib', 'content': kill_alert_dylib, 'mode': 0o755},
    {'path': './usr/lib/TweakInject/KillThermalAlert.plist', 'content': kill_alert_plist, 'mode': 0o644},

    # Thermal Profiles (101 Zero Throttling, 99C Trap)
    {'path': './mnt/System/Library/ThermalMonitor/D331pAP-Info.plist', 'content': d331p_bytes, 'mode': 0o644},
    {'path': './mnt/System/Library/ThermalMonitor/D321AP-Info.plist', 'content': d321_bytes, 'mode': 0o644},
    {'path': './mnt/System/Library/ThermalMonitor/D331AP-Info.plist', 'type': tarfile.SYMTYPE, 'linkname': 'D331pAP-Info.plist', 'mode': 0o777},

    # Entitlements
    {'path': './etc/a12powerfix/ent.plist', 'content': ent_bytes, 'mode': 0o644},
]

out_deb = os.path.join(PACKAGES_DIR, 'com.hoaug.a12powerfix_2.0.0_iphoneos-arm64e.deb')
create_deb(out_deb, control_files, data_files)
print(f"[Build] Successfully created {out_deb}")
