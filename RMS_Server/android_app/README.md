# TBC1000B Android port

This directory contains the Galaxy S25 (`arm64-v8a`) port of
`TBC1000B_감시프로그램_V3.0.11.py`.

The original desktop source remains unchanged. Android-specific differences:

- application data is written to Android's private persistent app directory;
- the unavailable `psutil` system-resource panel is disabled;
- the external `ping` command is skipped and reachability is decided by SNMP;
- the main window opens maximized;
- SNMP, SNMP Trap, alarm sound, profiles, logs, and Excel recording remain in
  the application.

The GitHub Actions workflow `build-tbc1000b-android.yml` produces a debug APK
artifact named `TBC1000B-GalaxyS25-APK`.

## Network notes

The phone and monitored equipment must be mutually reachable. Mobile carrier
networks normally cannot reach private equipment IP addresses, so use the same
Wi-Fi/VPN. Android may suspend network work after the app is put in the
background; keep the app visible during continuous monitoring.
