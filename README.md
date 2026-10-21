# PS5 MT7921 Wi-Fi and Bluetooth

Wi-Fi and Bluetooth fixes for PS5 units with the MediaTek MT7921 chip, for the
PS5 patched kernel 7.3. Tested: PS5 Slim, firmware 13.60, Ubuntu 26.04.1,
kernel 7.3.0.

```sh
sudo apt install clang-21 lld-21 llvm-21
git clone https://github.com/airkingbr/ps5-mt7921-wifi.git
cd ps5-mt7921-wifi
sudo python3 install.py
sudo reboot
```

Then connect through Ubuntu’s Wi-Fi and Bluetooth settings. To install only the
Wi-Fi module, use `sudo python3 install.py --no-bluetooth`.

## What is installed

| Device | Problem | Fix |
|---|---|---|
| Wi-Fi (PCIe `14c3:7961`) | The kernel is built without `mt7921e` | `build.sh` builds `mt7921e.ko` |
| Bluetooth (USB `0e8d:3603`) | Interfaces 3 and 4 expose a phantom second controller that keeps the real one from working | udev rule disabling those interfaces |
| Bluetooth | The chip stalls with USB autosuspend | udev rule and `btusb enable_autosuspend=0` |
| Bluetooth | ACL data never leaves: btusb sends it on bulk OUT `0x01`, the chip only drains `0x02` | patched `btusb.ko` |
| Bluetooth | The DualSense HID connection arrives before encryption is up and is refused | patched `bluetooth.ko` (L2CAP answers "pending") |

The Bluetooth fixes come from
[WizGery/ps5-mediatek-fixes](https://github.com/WizGery/ps5-mediatek-fixes).
`bluetooth.sh` downloads its patches `0003` and `0004` from a pinned commit,
checks their SHA-256 and applies them to the running kernel's Bluetooth
sources. Its patches `0001` and `0002` are already part of the PS5 kernel. The
bulk OUT endpoint can be changed with the `btusb.ps5_tx_ep` module parameter
(`0` restores the default behaviour). The Bluetooth fixes are skipped when no
`0e8d:3603` device is present.

## Requirements

`install.py` builds the modules for the running kernel with `build.sh` (Wi-Fi)
and `bluetooth.sh` (Bluetooth), which need:

- the build tree of the running kernel at `/lib/modules/$(uname -r)/build`,
  including `Module.symvers` and the kernel sources
  (`drivers/net/wireless/mediatek/mt76`, `drivers/bluetooth`,
  `net/bluetooth`);
- the toolchain the kernel was built with. The PS5 7.3 kernel is built with
  clang 21, so it needs `clang-21`, `lld-21` and `llvm-21`; the scripts pick
  them automatically;
- internet access to download the Bluetooth patches. Offline, put them in a
  directory and pass it as `BT_PATCHES=/path/to/patches`.

The modules are compiled from the kernel's own sources so they match the
modules already loaded. Building `mt7921e` against sources from another kernel
version compiles fine but crashes in `mt7921_pci_probe` because the structure
layouts differ.

If the mt76 sources are not in the build tree, point `MT76_SRC` at
`drivers/net/wireless/mediatek/mt76` of the same kernel version:

```sh
sudo MT76_SRC=/path/to/linux/drivers/net/wireless/mediatek/mt76 python3 install.py
```

Run `sudo python3 install.py` again after every kernel update, then reboot.

## Uninstall

```sh
sudo rm -rf /lib/modules/$(uname -r)/updates/ps5-mt7921 /lib/modules/$(uname -r)/updates/ps5-bt \
    /etc/modprobe.d/ps5-mt7921e.conf /etc/modprobe.d/btusb-ps5.conf \
    /etc/udev/rules.d/99-ps5-bt-phantom.rules
sudo depmod -a && sudo reboot
```

## Kernel 7.1.7

The bundled `mt7921e.ko` and `source/mt76` are from the original 7.1.7
release. `install.py` uses the bundled module only when the running kernel is
7.1.7; on any other kernel it builds the module.
