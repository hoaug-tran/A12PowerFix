# A12PowerFix (A12 Power & Anti-Throttle Fix)

**Comprehensive fix for the iOS 18 charging pause (`NotChargingReason = 0x04000000`), battery health/service caching, and thermal performance throttling on Apple A12 devices (iPhone XS Max, XS, XR).**

---

## 📌 Background & Problems

On Apple A12 devices (specifically iPhone XS Max `iPhone11,6`, iPhone XS `iPhone11,2`, and iPhone XR `iPhone11,8`) running iOS 18 (e.g., iOS 18.7.1):

### 1. The Charging Pause Issue (`NotChargingReason = 0x04000000`)
- **Symptoms:** When plugged into a USB-PD fast charger (e.g., Apple 20W USB-C adapter), the iPhone detects the charger, shows the charging icon, and draws ~90mA @ 9V to power the system logic board, but **fails to charge the battery cell** (`ChargingCurrent = 0 mA`).
- **Cold Boot Anomaly:** The device charges normally for the first ~60 seconds after a full cold reboot, but then suddenly stops charging. A userspace reboot (`launchctl reboot userspace`) does not restore charging.
- **Root Cause Discovered via Reverse Engineering:**
  - `NotChargingReason = 67108864` (`0x04000000` / bit 26) corresponds to **`INHIBIT_INFLOW`** (cutting off AC inflow current to the battery charging circuit).
  - In iOS 18, Apple introduced persistent battery data caching in `/private/var/MobileSoftwareUpdate/Hardware/Battery/Library/Preferences/`.
  - When an original battery degrades (e.g., health drops to 76%), iOS writes `Battery Service State = 5` into `com.apple.batteryhealthdata.plist`, and flags `KioskModeMode = 1` in `com.apple.batterydata.kioskmode.plist`.
  - Even after replacing the battery with a high-capacity replacement (e.g., Deji 3806 mAh), **iOS 18 does not flush this persistent cache**.
  - ~60 seconds after startup, `powerd` reads this cache, synchronizes `KioskModeMode = 1` to the SMC/PMU, and commands the hardware to engage `INHIBIT_INFLOW` (`0x04000000`), forcing `ChargingCurrent = 0`.

### 2. Thermal Mitigation & Extreme Throttling
- When Closed Loop Thermal Management (CLTM) or internal hotspot decision tables trip:
  - `thermalMitigationLimits` sets `dtCharger: 0` (kills charging current).
  - `dtCPU: 1` (CPU throttled to 1% Load Index).
  - `dtGPU: 0` (GPU throttled to lowest state, severe frame drops in games).
  - `backlightComponentControl` dims the screen brightness down to 50% or lower.
- **Why killing `thermalmonitord` fails:** Disabling `thermalmonitord` stops watchdog heartbeats to the hardware SMC/PMU, which causes the SMC watchdog failsafe to cut charging as well.

---

## 🚀 How A12PowerFix Solves It

`A12PowerFix` implements a clean, robust, and permanent fix:

1. **Persistent KioskMode & Battery Cache Reset:**
   - Clears `KioskModeMode = 1` ➔ resets to `0` (enabling inflow).
   - Detects the current active battery serial dynamically from IOKit.
   - Clears `Battery Service State = 5` ➔ resets to `0` (Normal, No Service).
   - Updates `Maximum Capacity Percent` to `100%`.
   - Clears `com.apple.thermalmonitor.agingcontroller.plist` mitigation state.
   - *Note: Because these settings are saved in `/private/var`, the charging fix persists even when unjailbroken (Stock iOS)!*

2. **Zero-Throttle Thermal Overlay (Max Performance):**
   - Keeps `thermalmonitord` alive so SMC/PMU watchdog heartbeats remain healthy.
   - Overlays patched thermal profiles (`D331pAP-Info.plist`, `D331AP-Info.plist`, `D321AP-Info.plist`) over `/System/Library/ThermalMonitor/` using RootHide-compatible `mount_bindfs`.
   - Sets all Load Indexes (`dtCharger`, `dtCPU`, `dtGPU`, `dtBacklight`, `dtThermalLevel`) to **`101`** (unrestricted 100% capacity) across `light`, `moderate`, `heavy`, and all 16 `DecisionTreeTable` hotspot tables.
   - Eliminates screen dimming and low-battery contextual clamps.
   - Automatically remounts on every boot via `com.nan.auto-bindfs` launchdaemon.

3. **System Cleanup:**
   - Clears accumulated `.ips` crash reports from `/var/mobile/Library/Logs/CrashReporter/`.

---

## 📦 Tested Environment
- **Device:** iPhone XS Max (`iPhone11,6` / `D331pAP`), iPhone XS (`iPhone11,2` / `D321AP`), iPhone XR (`iPhone11,8` / `D331AP`).
- **OS Version:** iOS 18.0 - 18.7.1+.
- **Jailbreak:** RootHide Dopamine 2.x / 3.x (`iphoneos-arm64e`).
- **Chargers Verified:** Apple 20W USB-C PD Adapter, 30W/65W GaN USB-PD chargers.

---

## 📥 Installation

Download the latest `.deb` package from the [Releases](https://github.com/hoaug-tran/A12PowerFix/releases) tab.

### Option 1: Sileo / Zebra / Filza
1. Download `com.hoaug.a12powerfix_1.0.0_iphoneos-arm64e.deb` onto your iPhone.
2. Open the `.deb` file in **Filza**, tap **Install** (or share to **Sileo** / **Zebra**).
3. Tap **Respring / Done** when installation finishes.
4. Reboot the iPhone once (Full Reboot: Power off and turn back on).
5. Open your jailbreak app (Dopamine / RootHide) and tap **Jailbreak**.

### Option 2: Terminal / SSH
```bash
# Transfer the deb to the device
scp com.hoaug.a12powerfix_1.0.0_iphoneos-arm64e.deb mobile@<IP>:/var/mobile/

# SSH into the device and install
ssh mobile@<IP>
sudo dpkg -i /var/mobile/com.hoaug.a12powerfix_1.0.0_iphoneos-arm64e.deb

# Reboot device once
sudo reboot
```

---

## 🔍 Verification

After installation and rebooting, you can verify charging status via SSH:
```bash
ioreg -r -c AppleSmartBattery -l | grep -E 'NotChargingReason|ChargingCurrent|Voltage|CurrentCapacity'
```

Expected output while connected to a PD fast charger:
```text
"NotChargingReason" = 0
"ChargingCurrent" = 3076
"Voltage" = 3975
```
- `NotChargingReason` should be **`0`** (charging normally).
- `ChargingCurrent` should be **`> 2000 - 3000 mA`** (Fast charging active at ~12-15W).

To verify the Anti-Throttle mount:
```bash
mount | grep -i thermal
```
Expected output:
```text
/var/containers/Bundle/Application/.jbroot-.../bindfs/System/Library/ThermalMonitor on /System/Library/ThermalMonitor (bindfs, local, nosuid, read-only, nobrowse)
```

---

## 🗑️ Uninstallation

If you ever wish to remove the tweak:
```bash
sudo dpkg -r com.hoaug.a12powerfix
```
The uninstallation script will cleanly unmount `/System/Library/ThermalMonitor` and remove the launchdaemon.

---

## 📄 License & Credits
- Authored by **hoaug** (2026).
- Built with reverse-engineering insights from `morluto/rea` and `Battman` (Torrekie).
- License: MIT.
