# PS5 MT7921 Wi-Fi

For the PS5 patched kernel 7.3. Tested: PS5 Slim, firmware 13.60,
Ubuntu 26.04.1, kernel 7.3.0.

```sh
sudo apt install clang-21 lld-21 llvm-21
git clone https://github.com/airkingbr/ps5-mt7921-wifi.git
cd ps5-mt7921-wifi
sudo python3 install.py
```

Then connect through Ubuntu’s Wi-Fi settings.

## Requirements

`install.py` builds the module for the running kernel with `build.sh`, which
needs:

- the build tree of the running kernel at `/lib/modules/$(uname -r)/build`,
  including `Module.symvers` and the kernel sources
  (`drivers/net/wireless/mediatek/mt76`);
- the toolchain the kernel was built with. The PS5 7.3 kernel is built with
  clang 21, so it needs `clang-21`, `lld-21` and `llvm-21`; `build.sh` picks
  them automatically.

The module is compiled from the kernel's own mt76 sources so it matches the
`mt76`, `mt792x-lib` and `mt7921-common` modules already loaded. Building it
against sources from another kernel version compiles fine but crashes in
`mt7921_pci_probe` because the structure layouts differ.

If the sources are not in the build tree, point `MT76_SRC` at
`drivers/net/wireless/mediatek/mt76` of the same kernel version:

```sh
sudo MT76_SRC=/path/to/linux/drivers/net/wireless/mediatek/mt76 python3 install.py
```

Rebuild with `sudo python3 install.py` after every kernel update. If a
previously installed module crashed and is still loaded, reboot after
installing.

## Kernel 7.1.7

The bundled `mt7921e.ko` and `source/mt76` are from the original 7.1.7
release. `install.py` uses the bundled module only when the running kernel is
7.1.7; on any other kernel it builds the module.
