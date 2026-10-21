import argparse
import os
from pathlib import Path
import platform
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
BLUETOOTH_ID = ("0e8d", "3603")
# Files left by earlier manual Bluetooth workarounds; this installer replaces them.
OLD_BLUETOOTH_FILES = (
    Path("/etc/udev/rules.d/80-disable-internal-bt.rules"),
    Path("/etc/udev/rules.d/99-ps5-bt-fantasma.rules"),
)


def vermagic(module):
    output = subprocess.check_output(["modinfo", "-F", "vermagic", str(module)], text=True).split()
    return output[0] if output else ""


def has_mediatek_bluetooth():
    for device in Path("/sys/bus/usb/devices").glob("*"):
        try:
            ids = ((device / "idVendor").read_text().strip(), (device / "idProduct").read_text().strip())
        except OSError:
            continue
        if ids == BLUETOOTH_ID:
            return True
    return False


def install_wifi(release, force_build):
    bundled = ROOT / "mt7921e.ko"
    # The bundled module only fits the 7.1.7 kernel; anything else is built
    # from the running kernel's mt76 sources so the ABI matches.
    if not force_build and bundled.is_file() and vermagic(bundled) == release:
        module = bundled
        print(f"Using the bundled Wi-Fi module for {release}.")
    else:
        print(f"Building the Wi-Fi module for {release}.", flush=True)
        subprocess.run(["bash", str(ROOT / "build.sh")], check=True)
        module = ROOT / "build/mt7921e.ko"
    if vermagic(module) != release:
        raise ValueError(f"{module} does not match the running kernel {release}")
    destination = Path("/lib/modules") / release / "updates/ps5-mt7921/mt7921e.ko"
    subprocess.run(["install", "-Dm644", str(module), str(destination)], check=True)
    configuration = Path("/etc/modprobe.d/ps5-mt7921e.conf")
    configuration.parent.mkdir(parents=True, exist_ok=True)
    configuration.write_text("options mt7921e disable_aspm=1\n")
    configuration.chmod(0o644)


def install_bluetooth(release):
    print(f"Building the Bluetooth modules for {release}.", flush=True)
    if subprocess.run(["bash", str(ROOT / "bluetooth.sh")]).returncode:
        raise ValueError("building the Bluetooth modules failed; use --no-bluetooth to install only Wi-Fi")
    modules = [ROOT / "build/bluetooth" / name for name in ("btusb.ko", "bluetooth.ko")]
    for module in modules:
        if vermagic(module) != release:
            raise ValueError(f"{module} does not match the running kernel {release}")
    destination = Path("/lib/modules") / release / "updates/ps5-bt"
    subprocess.run(["install", "-Dm644", "-t", str(destination)] + [str(m) for m in modules], check=True)
    subprocess.run(["install", "-Dm644", str(ROOT / "system/99-ps5-bt-phantom.rules"),
                    "/etc/udev/rules.d/99-ps5-bt-phantom.rules"], check=True)
    subprocess.run(["install", "-Dm644", str(ROOT / "system/btusb-ps5.conf"),
                    "/etc/modprobe.d/btusb-ps5.conf"], check=True)
    for old in OLD_BLUETOOTH_FILES:
        old.unlink(missing_ok=True)
    subprocess.run(["udevadm", "control", "--reload"], check=True)


def main():
    parser = argparse.ArgumentParser(description="Build and install PS5 MediaTek MT7921 Wi-Fi and Bluetooth fixes.")
    parser.add_argument("--build", action="store_true", help="always build the Wi-Fi module instead of using the bundled one")
    parser.add_argument("--no-bluetooth", action="store_true", help="install only the Wi-Fi module")
    args = parser.parse_args()
    if os.geteuid() != 0:
        print("error: Installation requires root; run sudo python3 install.py.", file=sys.stderr)
        return 1
    release = platform.release()
    reboot = False
    try:
        install_wifi(release, args.build)
        if args.no_bluetooth:
            pass
        elif has_mediatek_bluetooth():
            install_bluetooth(release)
            # bluetooth.ko is always in use, so the new one loads on the next boot.
            reboot = True
        else:
            print("MediaTek Bluetooth 0e8d:3603 not found; skipping the Bluetooth fixes.")
        subprocess.run(["depmod", "-a", release], check=True)
        if Path("/sys/module/mt7921e").exists():
            reboot = True
        else:
            subprocess.run(["modprobe", "mt7921e"], check=True)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print("Installed. Reboot to load the new modules." if reboot else "Installed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
