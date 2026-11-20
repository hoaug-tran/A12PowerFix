# A12PowerFix

**Unified Power, Charging & Thermal Suite for Apple A12 Devices (iPhone XS, XS Max, XR)**  
Optimized for **iOS 18.x** on **RootHide Dopamine** (`iphoneos-arm64e`).

---

## Overview of Solved Problems

| Issue | Root Cause | Fix in v2.0.0 |
| :--- | :--- | :--- |
| **Charging Stalled at ~77% (4.088V)** | Apple Kiosk Mode asserted `NotChargingReason = 0x04000000` (Bit 26 `INHIBIT_INFLOW`) at 4.10V ceiling. | Daemon forces `CHTU = 4350 mV`, `CC0S = 100%`, `KioskModeMode = 0`, and clears inhibit latches. |
| **Intermittent / Refusing to Charge When Hot** | Hardware PMU triggers `NotChargingReason = 16` (`0x10` = JEITA thermal cutoff) when battery temp $\ge$ 41.0°C. | Daemon dynamically clears `CHNC = 0`, unlatches `AppleSmartBatteryManager`, and sets `CC0T = 55°C`. |
| **1% Battery Lock on Cable Disconnect** | Store Demo / Kiosk mode keys (`CHKR = 2`, `CH0I = 2`) remained asserted while on battery power, forcing `powerd` to clamp UI to 1%. | Added real-time `ExternalConnected` detection. When unplugged, daemon sleeps and enforces `CHKR = 0`, restoring real battery percentage. |
| **Emergency Overheat Lock Screen ("iPhone needs to cool down")** | SpringBoard's `SBThermalController` triggers `SBThermalEmergencyAlertItem` at Level 3/4. | Objective-C runtime tweak (`KillThermalAlert.dylib`) hooks SpringBoard to permanently suppress all overheat lock screens. |
| **Thermal Throttling & Screen Dimming** | Stock `thermalmonitord` mitigations (`dtCPU`, `dtGPU`, `dtBacklight`) throttle down to 50% or less. | Overlaid thermal profiles (`D331pAP`, `D321AP`) pinning all mitigation limits to `101` (Zero Throttling) and trap targets to 99°C. |

---

## Architecture & Components

```
A12PowerFix
├── src/
│   ├── a12chargingd.c             # Continuous charging watchdog & hardware unlatch daemon
│   ├── a12chargingd               # Compiled ARM64e daemon binary
│   ├── com.hoaug.a12chargingd.plist # LaunchDaemon descriptor (/Library/LaunchDaemons)
│   ├── KillThermalAlert.c         # SpringBoard Objective-C runtime hook
│   ├── KillThermalAlert.dylib     # Compiled ARM64e MobileSubstrate tweak
│   ├── KillThermalAlert.plist     # Filter: com.apple.springboard
│   ├── D331pAP-Info.plist         # iPhone XS Max thermal profile (101 limit, 99°C trap)
│   ├── D321AP-Info.plist          # iPhone XS thermal profile (101 limit, 99°C trap)
│   └── ent.plist                  # Entitlements for AppleSMC, ASBM & power management
├── packages/
│   └── com.hoaug.a12powerfix_2.0.0_iphoneos-arm64e.deb
├── build.py                       # Automated Debian package builder
└── deb_builder.py                 # Pure-Python ar & tar.gz package generator
```

### 1. `a12chargingd` (Hardware Charging Daemon)
Runs in the background every 2 seconds via `launchd`:
* Reads `ExternalConnected` from `AppleSmartBattery`.
  * **When Unplugged (`ExternalConnected == NO`):** Completely idle. Enforces `CHKR = 0` and `CHKS = 0` so `powerd` never enters Kiosk failsafe (1% bug).
  * **When Plugged In (`ExternalConnected == YES`):**
    * Maintains `CHTU = 4350` mV (4.35V maximum charge capacity).
    * Maintains `CC0S = 100`% (State of Charge target).
    * Maintains `CC0T = 55`°C (Charge cutoff temperature threshold).
    * Maintains `CHCE = 1` (Charge Enable).
    * Clears `CHNC` (NotChargingReason) and calls `AppleSmartBatteryManagerUserClient` selector 0 to unlatch hardware charging current.
    * Keeps `KioskModeMode = 0` in `AppleSmartBattery`.

### 2. `KillThermalAlert` (SpringBoard Tweak)
Injected into SpringBoard via Ellekit / MobileSubstrate (`/usr/lib/TweakInject/`):
* Hooks `SBThermalController`:
  * `- (BOOL)isInThermalTrap` $\rightarrow$ returns `NO`.
  * `- (BOOL)isThermalBlocked` $\rightarrow$ returns `NO`.
  * `- (int)level` $\rightarrow$ returns `0`.
  * `- (void)_setThermalEmergencyAlertItem:(id)arg` $\rightarrow$ no-op.
  * `- (void)showThermalAlertIfNecessary` $\rightarrow$ no-op.
* Hooks `SBThermalEmergencyAlertItem` & `SBTemperatureWarningViewController`:
  * Suppresses alert presentation and auto-dismisses if ever instantiated.

### 3. Thermal Overlays (`D331pAP`, `D321AP`)
* Overlaid onto `/System/Library/ThermalMonitor` via persistent mount.
* `thermalMitigationLimits` (light, moderate, heavy):
  * `dtCPU = 101`
  * `dtGPU = 101`
  * `dtBacklight = 101`
  * `dtCharger = 101`
* Hotspot `THERMAL_TRAP_LOAD` & `THERMAL_TRAP_SLEEP` raised to 99°C.
* `ForcedThermalLevelTarget0` raised to 95°C, `ForcedThermalLevelTarget1` to 97°C.

### 4. Background Daemon Pruning
Disables 10 non-essential background daemons saving ~300MB - 500MB physical RAM and reducing ambient thermal generation:
`modelcatalogd`, `intelligenceplatformd`, `homed`, `ThreadCommissionerService`, `triald`, `momentsd`, `inputanalyticsd`, `wifianalyticsd`, `audioanalyticsd`, `ReportCrash`.

---

## Supported Devices

| Model | Board ID | Identifier |
| :--- | :--- | :--- |
| iPhone XS Max | D331pAP | `iPhone11,6` |
| iPhone XS | D321AP | `iPhone11,2` |
| iPhone XR | D331AP | `iPhone11,8` |

* **iOS Version:** iOS 18.0 - 18.7.1+
* **Jailbreak:** RootHide Dopamine (`iphoneos-arm64e`)

---

## Installation

### Method A: Via Sileo / Zebra / Filza
1. Download `com.hoaug.a12powerfix_2.0.0_iphoneos-arm64e.deb` from the [packages](./packages/) folder or Releases.
2. Open with Filza and tap **Install** (or import into Sileo/Zebra).
3. The post-installation script will automatically sign binaries with `ldid`, start `a12chargingd`, inject `KillThermalAlert`, and trigger `sbreload`.

### Method B: Via SSH
```bash
# Transfer package to device
scp packages/com.hoaug.a12powerfix_2.0.0_iphoneos-arm64e.deb mobile@<DEVICE_IP>:/var/mobile/

# SSH into device and install
ssh mobile@<DEVICE_IP>
echo <PASSWORD> | sudo -S dpkg -i /var/mobile/com.hoaug.a12powerfix_2.0.0_iphoneos-arm64e.deb
```

---

## Building from Source

Requirements on host: Python 3.8+, LLVM `clang` with `arm64-apple-ios14.0` target support.

```bash
# 1. Compile binaries (if modifying C sources)
clang -target arm64-apple-ios14.0 -fuse-ld=lld -L./sdk src/a12chargingd.c -o src/a12chargingd
clang -target arm64-apple-ios14.0 -fuse-ld=lld -dynamiclib -L./sdk src/KillThermalAlert.c -o src/KillThermalAlert.dylib

# 2. Package into Debian package
python build.py
```

---

## License

MIT License. Designed and maintained by **hoaug**.
