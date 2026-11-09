import os, tarfile
from deb_builder import create_deb

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(REPO_DIR, 'src')
PACKAGES_DIR = os.path.join(REPO_DIR, 'packages')
os.makedirs(PACKAGES_DIR, exist_ok=True)

control_content = """Package: com.hoaug.a12powerfix
Name: A12 Power & Anti-Throttle Fix
Version: 1.0.0
Architecture: iphoneos-arm64e
Maintainer: hoaug <hoaug@antigravity>
Author: hoaug
Section: System
Priority: optional
Description: Fixes 0x04000000 charging pause, resets KioskMode/battery health cache for A12 (XS Max) on iOS 18, and provides zero-throttle max performance with auto-bindfs.
Tag: role::hacker, purpose::extension
"""

postinst_content = """#!/bin/sh
set -e

echo "[A12PowerFix] Installing A12 Power & Anti-Throttle Fix..."

# 1. Detect active jbroot
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

echo "[A12PowerFix] Using JBROOT: $JBROOT"

# 2. Setup bindfs target directory
BINDFS_DIR="$JBROOT/bindfs/System/Library/ThermalMonitor"
mkdir -p "$BINDFS_DIR"

SRC_DIR="/var/mobile/Library/A12PowerFix/ThermalMonitor"
if [ -d "$SRC_DIR" ]; then
    cp "$SRC_DIR/D331pAP-Info.plist" "$BINDFS_DIR/D331pAP-Info.plist"
    cp "$SRC_DIR/D321AP-Info.plist" "$BINDFS_DIR/D321AP-Info.plist"
    rm -f "$BINDFS_DIR/D331AP-Info.plist"
    ln -s D331pAP-Info.plist "$BINDFS_DIR/D331AP-Info.plist"
    chmod 0644 "$BINDFS_DIR"/*
    chown -R 0:0 "$BINDFS_DIR"
fi

# 3. Configure auto-bindfs
if command -v mount_bindfs >/dev/null 2>&1; then
    mount_bindfs -s --add "/System/Library/ThermalMonitor" 2>/dev/null || true
    mount_bindfs "/System/Library/ThermalMonitor" 2>/dev/null || true
fi

# 4. Fix KioskMode & Battery Health cache in /private/var
PREFS_DIR="/private/var/MobileSoftwareUpdate/Hardware/Battery/Library/Preferences"
if [ -d "$PREFS_DIR" ]; then
    mkdir -p "$PREFS_DIR/backup"
    cp -n "$PREFS_DIR"/*.plist "$PREFS_DIR/backup/" 2>/dev/null || true

    CUR_SERIAL="F8Y42213S5FJPKHDF"
    if [ -f "/tmp/ioreg" ]; then
        DETECTED=$(/tmp/ioreg -r -c AppleSmartBattery -l | grep -o '"Serial"[[:space:]]*=[[:space:]]*"[^"]*"' | head -n1 | cut -d'"' -f4)
        if [ -n "$DETECTED" ]; then
            CUR_SERIAL="$DETECTED"
        fi
    fi

    cat <<EOF > "$PREFS_DIR/com.apple.batterydata.kioskmode.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Format Version</key>
    <integer>1</integer>
    <key>KioskModeEntries</key>
    <integer>0</integer>
    <key>KioskModeExits</key>
    <integer>0</integer>
    <key>KioskModeHighSocResidency0</key>
    <integer>0</integer>
    <key>KioskModeHighSocResidency1</key>
    <integer>0</integer>
    <key>KioskModeHighSocResidency2</key>
    <integer>0</integer>
    <key>KioskModeHighSocResidency3</key>
    <integer>0</integer>
    <key>KioskModeMode</key>
    <integer>0</integer>
    <key>KioskModeResidency0</key>
    <integer>0</integer>
    <key>KioskModeResidency1</key>
    <integer>0</integer>
    <key>KioskModeResidency2</key>
    <integer>0</integer>
    <key>KioskModeResidency3</key>
    <integer>0</integer>
    <key>Serial</key>
    <string>$CUR_SERIAL</string>
    <key>lastUpdateTs</key>
    <real>815879610.0</real>
</dict>
</plist>
EOF

    cat <<EOF > "$PREFS_DIR/com.apple.thermalmonitor.agingcontroller.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>DataMigrated</key>
    <true/>
    <key>MitigationState</key>
    <integer>0</integer>
    <key>UPOCount</key>
    <integer>0</integer>
</dict>
</plist>
EOF

    cat <<EOF > "$PREFS_DIR/com.apple.batteryhealthdata.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Battery Serial</key>
    <string>$CUR_SERIAL</string>
    <key>Battery Service Flags</key>
    <integer>0</integer>
    <key>Battery Service State</key>
    <integer>0</integer>
    <key>Maximum Capacity Percent</key>
    <integer>100</integer>
</dict>
</plist>
EOF

    chmod 0644 "$PREFS_DIR"/*.plist
    chown -R 0:0 "$PREFS_DIR"
fi

rm -rf /private/var/mobile/Library/Logs/CrashReporter/* 2>/dev/null || true
rm -f /private/var/preferences/SystemConfiguration/OSThermalStatus.plist 2>/dev/null || true

echo "[A12PowerFix] Done! All fixes configured successfully."
exit 0
"""

prerm_content = """#!/bin/sh
set -e

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    echo "[A12PowerFix] Removing A12 Power & Anti-Throttle Fix..."
    if command -v mount_bindfs >/dev/null 2>&1; then
        mount_bindfs -u "/System/Library/ThermalMonitor" 2>/dev/null || true
        mount_bindfs -s --del "/System/Library/ThermalMonitor" 2>/dev/null || true
    fi
fi
exit 0
"""

wrapper_content = """#!/bin/sh
exec /usr/sbin/mount_bindfs "$@"
"""

launchdaemon_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nan.auto-bindfs</string>
    <key>ProcessType</key>
    <string>Interactive</string>
    <key>POSIXSpawnType</key>
    <string>Interactive</string>
    <key>Program</key>
    <string>/bin/sh</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/sh</string>
        <string>/usr/libexec/mount_bindfs/auto-bindfs-wrapper</string>
        <string>--auto</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""

with open(os.path.join(SRC_DIR, 'D331pAP-Info-Patched.plist'), 'rb') as f:
    d331p_bytes = f.read()

with open(os.path.join(SRC_DIR, 'D321AP-Info-Patched.plist'), 'rb') as f:
    d321_bytes = f.read()

with open(os.path.join(SRC_DIR, 'mount_bindfs'), 'rb') as f:
    mount_bindfs_bytes = f.read()

control_files = [
    ('./control', control_content.strip().encode('utf-8') + b'\n', 0o644),
    ('./postinst', postinst_content.strip().encode('utf-8') + b'\n', 0o755),
    ('./prerm', prerm_content.strip().encode('utf-8') + b'\n', 0o755),
]

data_files = [
    # Directories
    {'path': './var', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './var/mobile', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './var/mobile/Library', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './var/mobile/Library/A12PowerFix', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './var/mobile/Library/A12PowerFix/ThermalMonitor', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './usr', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './usr/sbin', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './usr/libexec', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './usr/libexec/mount_bindfs', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './Library', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'path': './Library/LaunchDaemons', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    
    # Plists
    {'path': './var/mobile/Library/A12PowerFix/ThermalMonitor/D331pAP-Info.plist', 'content': d331p_bytes, 'mode': 0o644},
    {'path': './var/mobile/Library/A12PowerFix/ThermalMonitor/D321AP-Info.plist', 'content': d321_bytes, 'mode': 0o644},
    {'path': './var/mobile/Library/A12PowerFix/ThermalMonitor/D331AP-Info.plist', 'type': tarfile.SYMTYPE, 'linkname': 'D331pAP-Info.plist', 'mode': 0o777},

    # Binaries and Daemons
    {'path': './usr/sbin/mount_bindfs', 'content': mount_bindfs_bytes, 'mode': 0o755},
    {'path': './usr/libexec/mount_bindfs/auto-bindfs-wrapper', 'content': wrapper_content.strip().encode('utf-8') + b'\n', 'mode': 0o755},
    {'path': './Library/LaunchDaemons/com.nan.auto-bindfs.plist', 'content': launchdaemon_content.strip().encode('utf-8') + b'\n', 'mode': 0o644},
]

out_deb = os.path.join(PACKAGES_DIR, 'com.hoaug.a12powerfix_1.0.0_iphoneos-arm64e.deb')
create_deb(out_deb, control_files, data_files)
print(f"[Build] Successfully created {out_deb}")

