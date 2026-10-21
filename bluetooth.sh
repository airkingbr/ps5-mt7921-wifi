#!/usr/bin/env bash
# Builds btusb.ko and bluetooth.ko for the running kernel with the fixes for
# the PS5 MediaTek Bluetooth chip (0e8d:3603) from
# https://github.com/WizGery/ps5-mediatek-fixes:
#   0003: send ACL data on bulk OUT 0x02, the only endpoint the chip drains
#   0004: answer L2CAP connections "pending" while encryption is on its way
set -euo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RELEASE=$(uname -r)
KDIR=${KDIR:-/lib/modules/$RELEASE/build}
BUILD="$ROOT/build/bluetooth"
JOBS=${JOBS:-4}

# Pinned upstream commit; the hashes guard against changed patches.
FIXES_URL=https://raw.githubusercontent.com/WizGery/ps5-mediatek-fixes/b84c899348a6b71aa62cc1c73dfc5e7c03860b4c/patches
PATCHES=(
    "0003-btusb-ps5-mediatek-bulk-out-0x02.patch 60f2e22781f949f3afe35ec443df1232074cf823df3f41f2be642ef6bb8eabf7"
    "0004-l2cap-defer-security-when-encryption-pending.patch 69f1c17747dfd2f7b1ec5532e259d2d937d9ad0f1940e239caf863db28ddb6c2"
)

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

[ -f "$KDIR/Module.symvers" ] || die "kernel build files with Module.symvers not found in $KDIR"
# The modules replace bluetooth.ko and btusb.ko of the running kernel, so they
# must be built from that kernel's own sources.
[ -f "$KDIR/drivers/bluetooth/btusb.c" ] || die "Bluetooth sources not found in $KDIR"
# The PS5 kernel already carries ps5-linux's btusb/hci_sync changes
# (WizGery's patches 0001 and 0002), so they are not applied again.
grep -q BTUSB_NO_AUTOSUSPEND "$KDIR/drivers/bluetooth/btusb.c" ||
    die "$KDIR is not a PS5 kernel (ps5-linux btusb changes missing)"

# Modules must be built with the same toolchain as the kernel.
make_args=(ARCH=x86 -j"$JOBS")
if [ -z "${LLVM:-}" ] && grep -qs '^CONFIG_CC_IS_CLANG=y' "$KDIR/.config"; then
    clang_major=$(( $(sed -n 's/^CONFIG_CLANG_VERSION=//p' "$KDIR/.config") / 10000 ))
    if command -v "clang-$clang_major" >/dev/null; then
        LLVM=-$clang_major
    elif command -v clang >/dev/null; then
        LLVM=1
    else
        die "kernel was built with clang $clang_major; install clang-$clang_major lld-$clang_major llvm-$clang_major"
    fi
fi
if [ -n "${LLVM:-}" ]; then
    make_args+=(LLVM="$LLVM")
    [ -n "${CC:-}" ] && make_args+=(CC="$CC")
else
    make_args+=(CC="${CC:-cc}")
fi

rm -rf -- "$BUILD"
mkdir -p "$BUILD/patches"
for entry in "${PATCHES[@]}"; do
    read -r name sha <<<"$entry"
    if [ -n "${BT_PATCHES:-}" ]; then
        cp -- "$BT_PATCHES/$name" "$BUILD/patches/$name"
    else
        curl -fsSL -o "$BUILD/patches/$name" "$FIXES_URL/$name"
    fi
    echo "$sha  $BUILD/patches/$name" | sha256sum -c --quiet - || die "$name does not match the pinned patch"
done

# Copy only sources: an in-tree kernel build leaves objects next to them.
(cd "$KDIR" && find drivers/bluetooth net/bluetooth -type f \
    \( -name '*.c' -o -name '*.h' -o -name Makefile -o -name Kconfig \) \
    ! -name '*.mod.c' -exec cp --parents {} "$BUILD" \;)
for entry in "${PATCHES[@]}"; do
    read -r name _ <<<"$entry"
    patch -d "$BUILD" -p1 --no-backup-if-mismatch < "$BUILD/patches/$name"
done
printf 'Kernel release: %s\nKernel build dir: %s\nmake: %s\n' "$RELEASE" "$KDIR" "${make_args[*]}"

for dir in drivers/bluetooth net/bluetooth; do
    make -C "$KDIR" M="$BUILD/$dir" MO= KBUILD_OUTPUT= "${make_args[@]}" modules
done

for module in drivers/bluetooth/btusb.ko net/bluetooth/bluetooth.ko; do
    vermagic=$(modinfo -F vermagic "$BUILD/$module" | awk '{print $1}')
    [ "$vermagic" = "$RELEASE" ] || die "$module is for $vermagic, not the running kernel $RELEASE"
    cp -- "$BUILD/$module" "$BUILD/"
done
modinfo -p "$BUILD/btusb.ko" | grep -q '^ps5_tx_ep:' || die "btusb.ko was built without the bulk OUT fix"
printf 'Built %s and %s\n' "$BUILD/btusb.ko" "$BUILD/bluetooth.ko"
