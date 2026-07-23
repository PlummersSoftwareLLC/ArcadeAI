#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROM_ROOT="$SCRIPT_DIR/roms"
SOURCE_ZIP="$ROM_ROOT/robotron.zip"
OUT_DIR="$ROM_ROOT/robotron"
MAME_BIN="${MAME_BIN:-mame}"
RUN_VERIFY=1

usage() {
    echo "Usage: $0 [--zip PATH] [--out-dir PATH] [--no-verify]"
    echo
    echo "Stages a Robotron ROM zip into the canonical filenames expected by"
    echo "current MAME's 'robotron' driver. This is useful for patched sets"
    echo "such as TIE-DIE that use legacy names like robotron.sb4."
    echo
    echo "Defaults:"
    echo "  --zip      $SOURCE_ZIP"
    echo "  --out-dir  $OUT_DIR"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --zip)
            if [[ $# -lt 2 ]]; then
                echo "error: --zip requires PATH" >&2
                exit 2
            fi
            SOURCE_ZIP="$2"
            shift 2
            ;;
        --zip=*)
            SOURCE_ZIP="${1#*=}"
            shift
            ;;
        --out-dir)
            if [[ $# -lt 2 ]]; then
                echo "error: --out-dir requires PATH" >&2
                exit 2
            fi
            OUT_DIR="$2"
            shift 2
            ;;
        --out-dir=*)
            OUT_DIR="${1#*=}"
            shift
            ;;
        --no-verify)
            RUN_VERIFY=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "error: unrecognized argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ ! -f "$SOURCE_ZIP" ]]; then
    echo "error: source zip not found: $SOURCE_ZIP" >&2
    exit 1
fi

if ! command -v unzip >/dev/null 2>&1; then
    echo "error: unzip is required" >&2
    exit 1
fi

mkdir -p "$OUT_DIR"
ZIP_ENTRIES="$(unzip -Z1 "$SOURCE_ZIP")"

find_zip_entry_by_basename() {
    local wanted="$1"
    printf '%s\n' "$ZIP_ENTRIES" | awk -v wanted="$wanted" '
        {
            name = $0
            sub(/^.*\//, "", name)
            if (name == wanted) {
                print $0
                exit
            }
        }
    '
}

extract_first_available() {
    local dest_name="$1"
    shift

    local candidate entry
    for candidate in "$@"; do
        entry="$(find_zip_entry_by_basename "$candidate")"
        if [[ -n "$entry" ]]; then
            unzip -p "$SOURCE_ZIP" "$entry" > "$OUT_DIR/$dest_name"
            echo "  $entry -> $dest_name"
            return 0
        fi
    done

    echo "error: could not find a source entry for $dest_name" >&2
    echo "       tried: $*" >&2
    return 1
}

echo "Staging Robotron ROMs from: $SOURCE_ZIP"
echo "Output directory: $OUT_DIR"

extract_first_available "2084_rom_1b_3005-13.e4" "2084_rom_1b_3005-13.e4" "robotron.sb1"
extract_first_available "2084_rom_2b_3005-14.c4" "2084_rom_2b_3005-14.c4" "robotron.sb2"
extract_first_available "2084_rom_3b_3005-15.a4" "2084_rom_3b_3005-15.a4" "robotron.sb3"
extract_first_available "2084_rom_4b_3005-16.e5" "2084_rom_4b_3005-16.e5" "robotron.sb4"
extract_first_available "2084_rom_5b_3005-17.c5" "2084_rom_5b_3005-17.c5" "robotron.sb5"
extract_first_available "2084_rom_6b_3005-18.a5" "2084_rom_6b_3005-18.a5" "robotron.sb6"
extract_first_available "2084_rom_7b_3005-19.e6" "2084_rom_7b_3005-19.e6" "robotron.sb7"
extract_first_available "2084_rom_8b_3005-20.c6" "2084_rom_8b_3005-20.c6" "robotron.sb8"
extract_first_available "2084_rom_9b_3005-21.a6" "2084_rom_9b_3005-21.a6" "robotron.sb9"
extract_first_available "2084_rom_10b_3005-22.a7" "2084_rom_10b_3005-22.a7" "robotron.sba"
extract_first_available "2084_rom_11b_3005-23.c7" "2084_rom_11b_3005-23.c7" "robotron.sbb"
extract_first_available "2084_rom_12b_3005-24.e7" "2084_rom_12b_3005-24.e7" "robotron.sbc"
extract_first_available "video_sound_rom_3_std_767.ic12" "video_sound_rom_3_std_767.ic12" "robotron.snd"
extract_first_available "decoder_rom_4.3g" "decoder_rom_4.3g" "decoder.4"
extract_first_available "decoder_rom_6.3c" "decoder_rom_6.3c" "decoder.6"

echo
echo "Staged canonical Robotron filenames."

if [[ "$RUN_VERIFY" -eq 1 ]]; then
    if command -v "$MAME_BIN" >/dev/null 2>&1; then
        echo
        echo "MAME verification diagnostic:"
        if "$MAME_BIN" -rompath "$ROM_ROOT" -verifyroms robotron; then
            echo "MAME reports the staged set as stock-valid."
        else
            echo
            echo "If the diagnostic now says INCORRECT CHECKSUM instead of NOT FOUND,"
            echo "that is expected for patched/custom ROMs and MAME can still launch it."
        fi
    else
        echo "Note: MAME binary not found; skipped verification diagnostic."
    fi
fi
