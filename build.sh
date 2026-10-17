#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
KDIR=${KDIR:-/lib/modules/$(uname -r)/build}
OUT="$ROOT/build/mt7921"
SRC="$ROOT/source/mt76"
JOBS=${JOBS:-4}

CC=${CC:-cc}
mkdir -p "$OUT"
cp -- "$SRC"/{dma.h,mt76.h,mt76_connac.h,mt76_connac2_mac.h,mt76_connac_mcu.h,mt792x.h,mt792x_acpi_sar.h,mt792x_regs.h,testmode.h,util.h} "$ROOT/build/"
cp -- "$SRC"/mt7921/{Makefile,pci.c,pci_mac.c,pci_mcu.c,mcu.h,mt7921.h,regs.h} "$OUT/"
printf 'Using compiler: %s\nKernel headers: %s\nModule output: %s\n' "$CC" "$KDIR" "$OUT"

exec make -C "$KDIR" \
    M="$OUT" MO= KBUILD_OUTPUT= \
    ARCH=x86 CC="$CC" -j"$JOBS" \
    CONFIG_MT7921E=m \
    CONFIG_MT7921_COMMON= \
    CONFIG_MT7921U= \
    CONFIG_MT7921S= \
    modules
