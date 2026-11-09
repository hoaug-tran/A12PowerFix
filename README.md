# A12PowerFix

Fixes the iOS 18 charging pause (`NotChargingReason = 0x04000000`) and removes thermal throttling on Apple A12 devices.

Compatible with iPhone XS, XS Max, and XR running iOS 18.x on RootHide Dopamine (`iphoneos-arm64e`).

---

## Technical Context

### The 0x04000000 Charging Pause

#### Symptom
When connected to a USB-PD charger, the device negotiates power and indicates charging, but battery current remains at `0 mA` (`ChargingCurrent = 0`). The device charges for roughly 60 seconds after a cold boot before inflow is cut. Userspace reboots (`launchctl reboot userspace`) do not restore charging.

#### Cause
Reading SMC key `CHNC` reveals `NotChargingReason = 67108864` (`0x04000000`). Bit 26 maps to `INHIBIT_INFLOW`, which instructs the power management unit (PMU) to drop AC charging current to zero.

On iOS 18, persistent battery state is stored at:
`/private/var/MobileSoftwareUpdate/Hardware/Battery/Library/Preferences/`

When a battery degrades past Apple's service threshold, iOS sets:
- `Battery Service State = 5` in `com.apple.batteryhealthdata.plist`
- `KioskModeMode = 1` in `com.apple.batterydata.kioskmode.plist`
- `MitigationState = 2` in `com.apple.thermalmonitor.agingcontroller.plist`

Replacing the physical battery with a third-party or high-capacity cell does not automatically clear this persistent cache. Roughly 60 seconds after system boot, `powerd` reads these files and commits `KioskModeMode = 1` to the SMC, tripping `INHIBIT_INFLOW`.

### Thermal Throttling

Under stock thermal management (`thermalmonitord`), temperature thresholds trigger Closed Loop Thermal Management (CLTM) mitigation tables:
- `dtCharger` reduced to `0`
- `dtCPU` throttled to minimum load index
- `dtGPU` throttled, causing frame drops
- `dtBacklight` reduced to 50% or below

Terminating or disabling `thermalmonitord` causes SMC watchdog heartbeats to fail, triggering hardware failsafes that also disable charging.

---

## Changes Applied

1. **Persistent Battery Cache Reset**
   - Sets `KioskModeMode = 0` in `com.apple.batterydata.kioskmode.plist`.
   - Reads the active battery serial from IOKit dynamically.
   - Sets `Battery Service State = 0` and `Maximum Capacity Percent = 100` in `com.apple.batteryhealthdata.plist`.
   - Resets `MitigationState = 0` in `com.apple.thermalmonitor.agingcontroller.plist`.
   - *Because `/private/var` is persistent across reboots, this charging fix remains active even in non-jailbroken state.*

2. **Zero-Throttle Thermal Overlay**
   - Retains `thermalmonitord` to preserve SMC/PMU watchdog heartbeats.
   - Uses `mount_bindfs` with `com.apple.private.bindfs-allow` to mount patched plists (`D331pAP`, `D331AP`, `D321AP`) over `/System/Library/ThermalMonitor/`.
   - Pins all thermal load indexes (`dtCharger`, `dtCPU`, `dtGPU`, `dtBacklight`) to `101` across all states and DecisionTreeTable entries.
   - Registers `/Library/LaunchDaemons/com.nan.auto-bindfs.plist` to remount on every boot.

3. **System Maintenance**
   - Clears accumulated crash logs from `/var/mobile/Library/Logs/CrashReporter/`.

---

## Supported Devices

| Model | Board ID | Identifier |
| :--- | :--- | :--- |
| iPhone XS Max | D331pAP | `iPhone11,6` |
| iPhone XS | D321AP | `iPhone11,2` |
| iPhone XR | D331AP | `iPhone11,8` |

- **Firmware:** iOS 18.0 - 18.7.1+
- **Architecture:** `iphoneos-arm64e` (RootHide Dopamine)

---

## Installation

### Via Package Manager (Filza / Sileo / Zebra)
1. Download `com.hoaug.a12powerfix_1.0.0_iphoneos-arm64e.deb` from [Releases](https://github.com/hoaug-tran/A12PowerFix/releases).
2. Open in Filza and tap **Install** (or import into Sileo/Zebra).
3. Perform a full device reboot (power off and on).
4. Re-run jailbreak in Dopamine/RootHide.

### Via SSH / Terminal
```sh
# Copy deb to device
scp com.hoaug.a12powerfix_1.0.0_iphoneos-arm64e.deb mobile@<DEVICE_IP>:/var/mobile/

# Install and reboot
ssh mobile@<DEVICE_IP>
sudo dpkg -i /var/mobile/com.hoaug.a12powerfix_1.0.0_iphoneos-arm64e.deb
sudo reboot
```

---

## Verification

### Charging Status
Query `AppleSmartBattery` via IORegistry:
```sh
ioreg -r -c AppleSmartBattery -l | grep -E 'NotChargingReason|ChargingCurrent|Voltage|CurrentCapacity'
```

Normal fast-charging values on USB-PD:
```text
"NotChargingReason" = 0
"ChargingCurrent" = 3076
"Voltage" = 3975
```
- `NotChargingReason = 0` indicates inflow is active (bit 26 cleared).
- `ChargingCurrent > 2000` indicates fast charging (>10-15W).

### Thermal Mount
Verify the bindfs mount is active:
```sh
mount | grep -i thermal
```

Expected output:
```text
/var/containers/Bundle/Application/.../bindfs/System/Library/ThermalMonitor on /System/Library/ThermalMonitor (bindfs, local, nosuid, read-only, nobrowse)
```

---

## Uninstallation

```sh
sudo dpkg -r com.hoaug.a12powerfix
```

The uninstaller removes the launch daemon and unmounts `/System/Library/ThermalMonitor`.

---

## Building

```sh
python build.py
```

Outputs package to `packages/com.hoaug.a12powerfix_1.0.0_iphoneos-arm64e.deb`.

---

## License

MIT. See `LICENSE`.
