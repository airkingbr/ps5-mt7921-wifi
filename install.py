import argparse
import os
from pathlib import Path
import platform
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def vermagic(module):
    output = subprocess.check_output(["modinfo", "-F", "vermagic", str(module)], text=True).split()
    return output[0] if output else ""


def main():
    parser = argparse.ArgumentParser(description="Build and install the PS5 MediaTek MT7921 PCIe module.")
    parser.add_argument("--build", action="store_true", help="always build the module instead of using the bundled one")
    args = parser.parse_args()
    if os.geteuid() != 0:
        print("error: Installation requires root; run sudo python3 install.py.", file=sys.stderr)
        return 1
    release = platform.release()
    bundled = ROOT / "mt7921e.ko"
    destination = Path("/lib/modules") / release / "updates/ps5-mt7921/mt7921e.ko"
    configuration = Path("/etc/modprobe.d/ps5-mt7921e.conf")
    try:
        # The bundled module only fits the 7.1.7 kernel; anything else is built
        # from the running kernel's mt76 sources so the ABI matches.
        if not args.build and bundled.is_file() and vermagic(bundled) == release:
            module = bundled
            print(f"Using the bundled module for {release}.")
        else:
            print(f"Building the module for {release}.", flush=True)
            subprocess.run(["bash", str(ROOT / "build.sh")], check=True)
            module = ROOT / "build/mt7921e.ko"
        if vermagic(module) != release:
            print(f"error: {module} does not match the running kernel {release}.", file=sys.stderr)
            return 1
        subprocess.run(["install", "-Dm644", str(module), str(destination)], check=True)
        configuration.parent.mkdir(parents=True, exist_ok=True)
        configuration.write_text("options mt7921e disable_aspm=1\n")
        configuration.chmod(0o644)
        subprocess.run(["depmod", "-a", release], check=True)
        if Path("/sys/module/mt7921e").exists():
            print("Installed. mt7921e is already loaded; reboot to use the new module.")
            return 0
        subprocess.run(["modprobe", "mt7921e"], check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print("Installed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
