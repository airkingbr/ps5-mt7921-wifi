#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RELEASE=$(uname -r)
KDIR=${KDIR:-/lib/modules/$RELEASE/build}
BUILD="$ROOT/build"
OUT="$BUILD/mt7921"
JOBS=${JOBS:-4}

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

[ -f "$KDIR/Module.symvers" ] || die "kernel build files with Module.symvers not found in $KDIR"

# The module links against mt76.ko, mt792x-lib.ko and mt7921-common.ko of the
# running kernel, so it must be compiled from that kernel's own mt76 sources.
# The bundled copy in source/mt76 only matches the 7.1.7 kernel ABI.
if [ -z "${MT76_SRC:-}" ]; then
    for dir in "$KDIR/drivers/net/wireless/mediatek/mt76" \
               "$KDIR/source/drivers/net/wireless/mediatek/mt76"; do
        if [ -f "$dir/mt7921/pci.c" ]; then
            MT76_SRC=$dir
            break
        fi
    done
fi
if [ -z "${MT76_SRC:-}" ]; then
    case "$RELEASE" in
    7.1.7*)
        MT76_SRC="$ROOT/source/mt76"
        ;;
    *)
        die "mt76 sources for $RELEASE not found in $KDIR; set MT76_SRC to drivers/net/wireless/mediatek/mt76 of this kernel's source tree"
        ;;
    esac
fi
[ -f "$MT76_SRC/mt7921/pci.c" ] || die "$MT76_SRC does not contain mt7921/pci.c"

# Modules must be built with the same toolchain as the kernel.
if [ -z "${LLVM:-}" ] && grep -qs '^CONFIG_CC_IS_CLANG=y' "$KDIR/.config"; then
    clang_version=$(sed -n 's/^CONFIG_CLANG_VERSION=//p' "$KDIR/.config")
    clang_major=$((clang_version / 10000))
    if command -v "clang-$clang_major" >/dev/null; then
        LLVM=-$clang_major
    elif command -v clang >/dev/null; then
        LLVM=1
    else
        die "kernel was built with clang $clang_major; install clang-$clang_major lld-$clang_major llvm-$clang_major"
    fi
fi

make_args=(ARCH=x86 -j"$JOBS")
if [ -n "${LLVM:-}" ]; then
    make_args+=(LLVM="$LLVM")
    [ -n "${CC:-}" ] && make_args+=(CC="$CC")
    compiler="LLVM=$LLVM${CC:+ CC=$CC}"
else
    CC=${CC:-cc}
    make_args+=(CC="$CC")
    compiler="CC=$CC"
fi

rm -rf -- "$OUT" "$BUILD"/*.h "$BUILD/mt7921e.ko"
mkdir -p "$OUT"
cp -- "$MT76_SRC"/*.h "$BUILD/"
cp -- "$MT76_SRC"/mt7921/{Makefile,pci.c,pci_mac.c,pci_mcu.c} "$MT76_SRC"/mt7921/*.h "$OUT/"
printf 'Kernel release: %s\nKernel build dir: %s\nmt76 sources: %s\nCompiler: %s\nModule output: %s\n' \
    "$RELEASE" "$KDIR" "$MT76_SRC" "$compiler" "$OUT"

make -C "$KDIR" \
    M="$OUT" MO= KBUILD_OUTPUT= \
    "${make_args[@]}" \
    CONFIG_MT7921E=m \
    CONFIG_MT7921_COMMON= \
    CONFIG_MT7921U= \
    CONFIG_MT7921S= \
    modules

vermagic=$(modinfo -F vermagic "$OUT/mt7921e.ko" | awk '{print $1}')
[ "$vermagic" = "$RELEASE" ] || die "built module is for $vermagic, not the running kernel $RELEASE"
cp -- "$OUT/mt7921e.ko" "$BUILD/mt7921e.ko"
printf 'Built %s\n' "$BUILD/mt7921e.ko"
