import argparse
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parent


def build(release, kdir, source, jobs):
    if not (kdir / "Module.symvers").is_file():
        raise ValueError(f"Matching kernel build files and Module.symvers required: {kdir}")
    query = ["make", "-s", "--no-print-directory", "-C", str(kdir)]
    built_release = subprocess.check_output(query + ["kernelrelease"], text=True).strip()
    if built_release != release:
        raise ValueError(f"Kernel headers are for {built_release}, not {release}")
    version = subprocess.check_output(query + ["kernelversion"], text=True).strip()
    version = re.sub(r"^(\d+\.\d+)\.0(?=-|$)", r"\1", version)
    output = ROOT / "build" / release
    output.mkdir(parents=True, exist_ok=True)
    archive = source or ROOT / "build" / f"linux-{version}.tar.xz"
    with tempfile.TemporaryDirectory(dir=output) as temporary:
        work = Path(temporary)
        if not archive.is_file():
            if source:
                raise FileNotFoundError(source)
            testing = "testing/" if "-rc" in version else ""
            url = f"https://cdn.kernel.org/pub/linux/kernel/v{version.split('.')[0]}.x/{testing}linux-{version}.tar.xz"
            print(f"Downloading {url}", flush=True)
            download = work / archive.name
            with urllib.request.urlopen(url, timeout=60) as response, download.open("wb") as destination:
                shutil.copyfileobj(response, destination)
            download.replace(archive)
        mt76 = work / "mt76"
        with tarfile.open(archive) as kernel:
            for member in kernel:
                parts = PurePosixPath(member.name).parts
                if parts[1:6] != ("drivers", "net", "wireless", "mediatek", "mt76"):
                    continue
                relative = parts[6:]
                if not relative or not member.isfile():
                    continue
                if ".." in relative:
                    raise ValueError("Invalid source archive path")
                destination = mt76.joinpath(*relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with kernel.extractfile(member) as contents, destination.open("wb") as target:
                    shutil.copyfileobj(contents, target)
        driver = mt76 / "mt7921"
        if not (driver / "Makefile").is_file():
            raise ValueError("Source archive does not contain the MT7921 driver")
        subprocess.run([
            "make", "-C", str(kdir), f"M={driver}", "MO=", "KBUILD_OUTPUT=",
            "ARCH=x86", f"CC={os.environ.get('CC', 'cc')}", f"-j{jobs}",
            "CONFIG_MT7921E=m", "CONFIG_MT7921_COMMON=", "CONFIG_MT7921U=",
            "CONFIG_MT7921S=", "modules",
        ], check=True)
        module = driver / "mt7921e.ko"
        vermagic = subprocess.check_output(["modinfo", "-F", "vermagic", str(module)], text=True)
        if not vermagic.split() or vermagic.split()[0] != release:
            raise ValueError("Built module does not match the running kernel")
        parameters = subprocess.check_output(["modinfo", "-p", str(module)], text=True)
        if not any(line.startswith("disable_aspm:") for line in parameters.splitlines()):
            raise ValueError("Built driver does not support disable_aspm")
        result = output / "mt7921e.ko"
        shutil.copyfile(module, result)
    print(f"Built {result}", flush=True)
    return result


def main():
    release = platform.release()
    parser = argparse.ArgumentParser(description="Build and install PS5 MT7921 PCIe Wi-Fi.")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--kernel-dir", type=Path, default=os.environ.get("KDIR", f"/lib/modules/{release}/build"))
    parser.add_argument("--jobs", type=int, default=os.environ.get("JOBS", "4"))
    parser.add_argument("--build-only", action="store_true")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    if platform.system() != "Linux" or platform.machine().lower() not in ("x86_64", "amd64"):
        parser.error("Run this on the PS5's x86-64 Linux installation")
    if not args.build_only and os.geteuid() != 0:
        parser.error("Installation requires sudo; use --build-only to compile without installing")
    try:
        module = build(release, args.kernel_dir.resolve(), args.source, args.jobs)
        if args.build_only:
            return 0
        destination = Path("/lib/modules") / release / "updates/ps5-mt7921/mt7921e.ko"
        subprocess.run(["install", "-Dm644", str(module), str(destination)], check=True)
        configuration = Path("/etc/modprobe.d/ps5-mt7921e.conf")
        configuration.parent.mkdir(parents=True, exist_ok=True)
        configuration.write_text("options mt7921e disable_aspm=1\n")
        configuration.chmod(0o644)
        subprocess.run(["depmod", "-a", release], check=True)
        if not Path("/sys/module/mt7921e").exists():
            subprocess.run(["modprobe", "mt7921e"], check=True)
    except (OSError, ValueError, tarfile.TarError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print("Installed. An already loaded driver was not reloaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
