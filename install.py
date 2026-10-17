import argparse
import os
from pathlib import Path
import platform
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Install the bundled PS5 MediaTek MT7921 PCIe module.")
    parser.parse_args()
    print("Only tested on PS5 Slim, firmware 13.60, Ubuntu 26.04.1, kernel 7.1.7.")
    if os.geteuid() != 0:
        print("error: Installation requires root; run sudo python3 install.py.", file=sys.stderr)
        return 1
    release = platform.release()
    module = Path(__file__).resolve().parent / "mt7921e.ko"
    destination = Path("/lib/modules") / release / "updates/ps5-mt7921/mt7921e.ko"
    configuration = Path("/etc/modprobe.d/ps5-mt7921e.conf")
    try:
        subprocess.run(["install", "-Dm644", str(module), str(destination)], check=True)
        configuration.parent.mkdir(parents=True, exist_ok=True)
        configuration.write_text("options mt7921e disable_aspm=1\n")
        configuration.chmod(0o644)
        subprocess.run(["depmod", "-a", release], check=True)
        subprocess.run(["modprobe", "mt7921e"], check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print("Installed. An already loaded module was not reloaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
