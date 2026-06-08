#!/usr/bin/env python3
import collections
import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT_CSV = ROOT / "data" / "logos_kana_layout.csv"
ROMAJI_CSV = ROOT / "data" / "logos_kana_romaji.csv"
OUT_DIR = ROOT / "config" / "logos_kana"

LOGOS_KANA_OUT = OUT_DIR / "logos_kana.dtsi"
QWERTY_OUT = OUT_DIR / "logos_kana_qwerty.dtsi"
PROFILE_OUT = OUT_DIR / "logos_kana_torabo_tsuki_lp.dtsi"

TOTAL_POSITIONS = 66
KANA_TOGGLE_POSITION = 65
ROW_LENGTHS = [12, 12, 14, 14, 14]

EXPECTED_SINGLE_KEYS = 30
EXPECTED_COMBOS = 105
EXPECTED_TOTAL = 135

KEY_POSITIONS = {
    "q": 13,
    "w": 14,
    "e": 15,
    "r": 16,
    "t": 17,
    "y": 18,
    "u": 19,
    "i": 20,
    "o": 21,
    "p": 22,
    "a": 25,
    "s": 26,
    "d": 27,
    "f": 28,
    "g": 29,
    "h": 32,
    "j": 33,
    "k": 34,
    "l": 35,
    ";": 36,
    "z": 39,
    "x": 40,
    "c": 41,
    "v": 42,
    "b": 43,
    "n": 46,
    "m": 47,
    ",": 48,
    ".": 49,
    "/": 50,
}

LAYOUT_KEYCODES = {
    ";": "SEMI",
    ",": "COMMA",
    ".": "DOT",
    "/": "SLASH",
}

ROMAJI_KEYCODES = {
    "-": "MINUS",
    ",": "COMMA",
    ".": "DOT",
}

NAME_OVERRIDES = {
    "、": "comma",
    "。": "period",
    "ー": "long",
}

LAYOUT_KEY_ORDER = [
    "q",
    "w",
    "e",
    "r",
    "t",
    "y",
    "u",
    "i",
    "o",
    "p",
    "a",
    "s",
    "d",
    "f",
    "g",
    "h",
    "j",
    "k",
    "l",
    ";",
    "z",
    "x",
    "c",
    "v",
    "b",
    "n",
    "m",
    ",",
    ".",
    "/",
]


def read_csv(path, expected_headers):
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != expected_headers:
            raise ValueError(f"{path}: expected headers {expected_headers}, got {reader.fieldnames}")
        rows = list(reader)

    for index, row in enumerate(rows, start=2):
        if any(value is None for value in row.values()):
            raise ValueError(f"{path}:{index}: malformed row {row}")
        for header in expected_headers:
            if header != "key2" and not row[header]:
                raise ValueError(f"{path}:{index}: {header} is required")
    return rows


def macro_suffix_for_key(key):
    if re.fullmatch(r"[a-z]", key):
        return key.upper()
    return keycode_for_layout_key(key)


def keycode_for_char(char):
    if re.fullmatch(r"[a-z]", char):
        return char.upper()
    if char in ROMAJI_KEYCODES:
        return ROMAJI_KEYCODES[char]
    raise ValueError(f"Unsupported romaji character: {char!r}")


def keycode_for_layout_key(key):
    if re.fullmatch(r"[a-z]", key):
        return key.upper()
    if key in LAYOUT_KEYCODES:
        return LAYOUT_KEYCODES[key]
    raise ValueError(f"Unsupported layout key: {key!r}")


def make_node_name(row, used_names):
    base = NAME_OVERRIDES.get(row["output"], row["romaji"])
    base = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")
    name = f"logos_kana_{base}"
    if name not in used_names:
        used_names.add(name)
        return name

    suffix = 2
    while f"{name}_{suffix}" in used_names:
        suffix += 1
    name = f"{name}_{suffix}"
    used_names.add(name)
    return name


def validate_unique(rows, key_fn, label):
    duplicates = [item for item, count in collections.Counter(map(key_fn, rows)).items() if count > 1]
    if duplicates:
        raise ValueError(f"Duplicate {label}: {duplicates}")


def load_romaji():
    rows = read_csv(ROMAJI_CSV, ["output", "romaji"])
    validate_unique(rows, lambda row: row["output"], "romaji output")
    romaji = {row["output"]: row["romaji"] for row in rows}
    for output, value in romaji.items():
        for char in value:
            keycode_for_char(char)
    return romaji


def load_layout():
    rows = read_csv(LAYOUT_CSV, ["output", "key1", "key2"])
    validate_unique(rows, lambda row: row["output"], "layout output")
    validate_unique(rows, lambda row: (row["key1"], row["key2"]), "layout key combo")

    for index, row in enumerate(rows, start=2):
        for key_name in ["key1", "key2"]:
            key = row[key_name]
            if key and key not in KEY_POSITIONS:
                raise ValueError(f"{LAYOUT_CSV}:{index}: unknown {key_name} {key!r}")

    single_count = sum(not row["key2"] for row in rows)
    combo_count = sum(bool(row["key2"]) for row in rows)
    if len(rows) != EXPECTED_TOTAL or single_count != EXPECTED_SINGLE_KEYS or combo_count != EXPECTED_COMBOS:
        raise ValueError(
            "Unexpected layout counts: "
            f"total={len(rows)}, single={single_count}, combo={combo_count}"
        )
    return rows


def prepare_rows():
    romaji = load_romaji()
    rows = load_layout()

    missing = sorted({row["output"] for row in rows if row["output"] not in romaji})
    if missing:
        raise ValueError(f"Missing romaji mapping for: {', '.join(missing)}")

    used_names = set()
    for row in rows:
        row["romaji"] = romaji[row["output"]]
        row["node"] = make_node_name(row, used_names)
    return rows


def fallback_macro(key):
    return f"LOGOS_KANA_FALLBACK_{macro_suffix_for_key(key)}"


def position_macro(key):
    return f"LOGOS_KANA_POS_{macro_suffix_for_key(key)}"


def write_required_define_checks(lines):
    required = [
        "LOGOS_KANA_LAYER",
        "LOGOS_KANA_TOTAL_POSITIONS",
        "LOGOS_KANA_ROW_LENGTHS",
        "LOGOS_KANA_TOGGLE_POSITION",
        "LOGOS_KANA_LAYER_BINDINGS",
    ]
    required.extend(position_macro(key) for key in LAYOUT_KEY_ORDER)
    required.extend(fallback_macro(key) for key in LAYOUT_KEY_ORDER)

    for define in required:
        lines.extend(
            [
                f"#ifndef {define}",
                f'#error "{define} must be defined before including logos_kana.dtsi"',
                "#endif",
            ]
        )
    lines.append("")


def write_defaults(lines):
    lines.extend(
        [
            "#ifndef LOGOS_KANA_COMBO_TIMEOUT_MS",
            "#define LOGOS_KANA_COMBO_TIMEOUT_MS 60",
            "#endif",
            "",
            "#ifndef LOGOS_KANA_MACRO_WAIT_MS",
            "#define LOGOS_KANA_MACRO_WAIT_MS 40",
            "#endif",
            "",
            "#ifndef LOGOS_KANA_MACRO_TAP_MS",
            "#define LOGOS_KANA_MACRO_TAP_MS 40",
            "#endif",
            "",
            "#ifndef LOGOS_KANA_MODS",
            "#define LOGOS_KANA_MODS (MOD_LCTL|MOD_RCTL|MOD_LSFT|MOD_RSFT|MOD_LALT|MOD_RALT|MOD_LGUI|MOD_RGUI)",
            "#endif",
            "",
            "#ifndef LOGOS_KANA_ON_BINDINGS",
            "#define LOGOS_KANA_ON_BINDINGS <&tog LOGOS_KANA_LAYER>",
            "#endif",
            "",
            "#ifndef LOGOS_KANA_OFF_BINDINGS",
            "#define LOGOS_KANA_OFF_BINDINGS <&tog LOGOS_KANA_LAYER>",
            "#endif",
            "",
        ]
    )


def write_layer_node_macro(lines):
    lines.extend(
        [
            "#define LOGOS_KANA_LAYER_NODE \\",
            "        logos_kana_layer { \\",
            '            display-name = "Logos Kana"; \\',
            "            bindings = < \\",
            "LOGOS_KANA_LAYER_BINDINGS \\",
            "            >; \\",
            "        };",
            "",
        ]
    )


def write_main_dtsi(rows):
    lines = [
        "// Generated by tools/generate_logos_kana_zmk.py. Do not edit manually.",
        "",
    ]
    write_required_define_checks(lines)
    write_defaults(lines)
    write_layer_node_macro(lines)

    lines.extend(
        [
            "/ {",
            "    behaviors {",
        ]
    )

    for row in rows:
        if row["key2"]:
            normal_binding = f"&{row['node']}"
            modified_binding = f"&{row['node']}_pass"
            behavior_name = f"{row['node']}_combo"
        else:
            normal_binding = f"&{row['node']}"
            modified_binding = f"&kp {fallback_macro(row['key1'])}"
            behavior_name = f"{row['node']}_key"

        lines.extend(
            [
                f"        {behavior_name}: {behavior_name} {{",
                '            compatible = "zmk,behavior-mod-morph";',
                "            #binding-cells = <0>;",
                f"            bindings = <{normal_binding}>, <{modified_binding}>;",
                "            mods = <LOGOS_KANA_MODS>;",
                "            keep-mods = <LOGOS_KANA_MODS>;",
                "        };",
                "",
            ]
        )

    lines.extend(
        [
            "    };",
            "",
            "    macros {",
            "        logos_kana_on: logos_kana_on {",
            '            compatible = "zmk,behavior-macro";',
            "            #binding-cells = <0>;",
            "            wait-ms = <LOGOS_KANA_MACRO_WAIT_MS>;",
            "            tap-ms = <LOGOS_KANA_MACRO_TAP_MS>;",
            "            bindings = LOGOS_KANA_ON_BINDINGS;",
            "        };",
            "",
            "        logos_kana_off: logos_kana_off {",
            '            compatible = "zmk,behavior-macro";',
            "            #binding-cells = <0>;",
            "            wait-ms = <LOGOS_KANA_MACRO_WAIT_MS>;",
            "            tap-ms = <LOGOS_KANA_MACRO_TAP_MS>;",
            "            bindings = LOGOS_KANA_OFF_BINDINGS;",
            "        };",
            "",
        ]
    )

    for row in rows:
        output_bindings = " ".join(f"&kp {keycode_for_char(char)}" for char in row["romaji"])
        lines.extend(
            [
                f"        {row['node']}: {row['node']} {{",
                '            compatible = "zmk,behavior-macro";',
                "            #binding-cells = <0>;",
                "            wait-ms = <LOGOS_KANA_MACRO_WAIT_MS>;",
                "            tap-ms = <LOGOS_KANA_MACRO_TAP_MS>;",
                f"            bindings = <{output_bindings}>;",
                "        };",
                "",
            ]
        )

        if row["key2"]:
            pass_bindings = " ".join(
                f"&kp {fallback_macro(key)}" for key in [row["key1"], row["key2"]]
            )
            lines.extend(
                [
                    f"        {row['node']}_pass: {row['node']}_pass {{",
                    '            compatible = "zmk,behavior-macro";',
                    "            #binding-cells = <0>;",
                    "            wait-ms = <LOGOS_KANA_MACRO_WAIT_MS>;",
                    "            tap-ms = <LOGOS_KANA_MACRO_TAP_MS>;",
                    f"            bindings = <{pass_bindings}>;",
                    "        };",
                    "",
                ]
            )

    lines.extend(
        [
            "    };",
            "",
            "    combos {",
            '        compatible = "zmk,combos";',
            "",
        ]
    )

    for row in rows:
        if not row["key2"]:
            continue
        lines.extend(
            [
                f"        combo_{row['node']} {{",
                "            timeout-ms = <LOGOS_KANA_COMBO_TIMEOUT_MS>;",
                f"            key-positions = <{position_macro(row['key1'])} {position_macro(row['key2'])}>;",
                "            layers = <LOGOS_KANA_LAYER>;",
                f"            bindings = <&{row['node']}_combo>;",
                "        };",
                "",
            ]
        )

    lines.extend(["    };", "};", ""])
    LOGOS_KANA_OUT.write_text("\n".join(lines), encoding="utf-8")


def write_qwerty_dtsi():
    lines = [
        "// Generated by tools/generate_logos_kana_zmk.py. Do not edit manually.",
        "",
    ]
    for key in LAYOUT_KEY_ORDER:
        define = fallback_macro(key)
        lines.extend(
            [
                f"#ifndef {define}",
                f"#define {define} {keycode_for_layout_key(key)}",
                "#endif",
                "",
            ]
        )
    QWERTY_OUT.write_text("\n".join(lines), encoding="utf-8")


def write_profile_dtsi(rows):
    bindings = ["&trans"] * TOTAL_POSITIONS
    for row in rows:
        if row["key2"]:
            continue
        bindings[KEY_POSITIONS[row["key1"]]] = f"&{row['node']}_key"
    bindings[KANA_TOGGLE_POSITION] = "LOGOS_KANA_TOGGLE_BINDING"

    offset = 0
    layer_rows = []
    for row_length in ROW_LENGTHS:
        row_bindings = bindings[offset : offset + row_length]
        layer_rows.append(" ".join(f"{binding:<24}" for binding in row_bindings).rstrip())
        offset += row_length

    if offset != TOTAL_POSITIONS:
        raise ValueError(f"ROW_LENGTHS add up to {offset}, expected {TOTAL_POSITIONS}")

    lines = [
        "// Generated by tools/generate_logos_kana_zmk.py. Do not edit manually.",
        "",
        "#ifndef LOGOS_KANA_TOTAL_POSITIONS",
        f"#define LOGOS_KANA_TOTAL_POSITIONS {TOTAL_POSITIONS}",
        "#endif",
        "",
        "#ifndef LOGOS_KANA_ROW_LENGTHS",
        "#define LOGOS_KANA_ROW_LENGTHS 12 12 14 14 14",
        "#endif",
        "",
        "#ifndef LOGOS_KANA_TOGGLE_POSITION",
        f"#define LOGOS_KANA_TOGGLE_POSITION {KANA_TOGGLE_POSITION}",
        "#endif",
        "",
        "#ifndef LOGOS_KANA_TOGGLE_BINDING",
        "#define LOGOS_KANA_TOGGLE_BINDING &logos_kana_off",
        "#endif",
        "",
    ]

    for key in LAYOUT_KEY_ORDER:
        define = position_macro(key)
        lines.extend(
            [
                f"#ifndef {define}",
                f"#define {define} {KEY_POSITIONS[key]}",
                "#endif",
                "",
            ]
        )

    lines.extend(
        [
            "#ifndef LOGOS_KANA_LAYER_BINDINGS",
            "#define LOGOS_KANA_LAYER_BINDINGS \\",
        ]
    )
    for index, layer_row in enumerate(layer_rows):
        suffix = " \\" if index < len(layer_rows) - 1 else ""
        lines.append(f"{layer_row}{suffix}")
    lines.extend(["#endif", ""])
    PROFILE_OUT.write_text("\n".join(lines), encoding="utf-8")


def main():
    rows = prepare_rows()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_main_dtsi(rows)
    write_qwerty_dtsi()
    write_profile_dtsi(rows)
    print(
        "generated "
        f"{len(rows)} mappings "
        f"({sum(not row['key2'] for row in rows)} single, "
        f"{sum(bool(row['key2']) for row in rows)} combos)"
    )


if __name__ == "__main__":
    main()
