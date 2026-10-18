# PS5 MT7921 Wi-Fi

Builds the driver for your running kernel and installs it with `disable_aspm=1`.
Requires matching PS5 kernel headers, `Module.symvers`, make, a compiler and temporary internet.

```sh
git clone https://github.com/j4lenj/ps5-mt7921-wifi.git
cd ps5-mt7921-wifi
sudo python3 install.py
```

Offline: add `--source /path/to/linux-X.Y.Z.tar.xz`. Compile without installing: `--build-only`.

Tested on PS5 Slim, firmware 13.60, Ubuntu 26.04.1, kernel 7.1.7. Other kernels are untested.
