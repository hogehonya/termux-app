import hashlib
import re
import unittest
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

MODULES = {
    "app": {
        "default": REPO_ROOT / "app/src/main/res/values/strings.xml",
        "japanese": REPO_ROOT / "app/src/main/res/values-ja/strings.xml",
        "count": 105,
        "sha256": "7972df37deeefe747339e4a464c1bbde708575abc95f5234bb365aba2505d2f9",
        "identical_allowed": {
            "application_name",
            "termux_preferences_title",
            "termux_api_preferences_title",
            "termux_float_preferences_title",
            "termux_tasker_preferences_title",
            "termux_widget_preferences_title",
        },
    },
    "termux-shared": {
        "default": REPO_ROOT / "termux-shared/src/main/res/values/strings.xml",
        "japanese": REPO_ROOT / "termux-shared/src/main/res/values-ja/strings.xml",
        "count": 55,
        "sha256": "281f6ee45d10fa40fecdb9d548236f9863acad825a05e03051b90d1460ccb2a1",
        "identical_allowed": set(),
    },
}

FORMAT_ARGUMENT_RE = re.compile(r"%(?:\d+\$)?[-#+ 0,(]*\d*(?:\.\d+)?[A-Za-z%]")
ENTITY_REFERENCE_RE = re.compile(r"&([A-Za-z_][A-Za-z0-9_]*);")
STRING_BODY_RE = re.compile(r'<string\s+name="([^"]+)"\s*>(.*?)</string>', re.DOTALL)
BACKTICK_TOKEN_RE = re.compile(r"`[^`]+`")
TECHNICAL_TOKEN_RE = re.compile(
    r"`[^`]+`|https?://[^\s`]+|\$[A-Z_][A-Z0-9_]*|~/[^\s`]+|"
    r"[A-Z][A-Z0-9_]{2,}|(?<!\\)[a-z][a-z0-9]*(?:[A-Z][a-z0-9]+)+"
)


def parse_strings(path):
    root = ET.parse(path).getroot()
    strings = {}
    for element in root.findall("string"):
        name = element.get("name")
        if name in strings:
            raise AssertionError(f"Duplicate string resource {name!r} in {path}")
        strings[name] = "".join(element.itertext())
    return strings


def parse_raw_string_bodies(path):
    return {
        match.group(1): match.group(2)
        for match in STRING_BODY_RE.finditer(path.read_text(encoding="utf-8"))
    }


def format_arguments(value):
    return Counter(FORMAT_ARGUMENT_RE.findall(value))


def validate_pair(name, default_value, japanese_value, default_raw, japanese_raw, identical_allowed):
    problems = []

    if not japanese_value.strip():
        problems.append(f"{name}: translation is empty")

    if name not in identical_allowed and japanese_value == default_value:
        problems.append(f"{name}: translation is identical to the default English string")

    default_arguments = format_arguments(default_value)
    japanese_arguments = format_arguments(japanese_value)
    if default_arguments != japanese_arguments:
        problems.append(
            f"{name}: format arguments differ: default={dict(default_arguments)}, "
            f"japanese={dict(japanese_arguments)}"
        )

    default_entities = Counter(ENTITY_REFERENCE_RE.findall(default_raw))
    japanese_entities = Counter(ENTITY_REFERENCE_RE.findall(japanese_raw))
    if default_entities != japanese_entities:
        problems.append(
            f"{name}: entity references differ: default={dict(default_entities)}, "
            f"japanese={dict(japanese_entities)}"
        )

    default_newlines = default_raw.count("\\n")
    japanese_newlines = japanese_raw.count("\\n")
    if default_newlines != japanese_newlines:
        problems.append(
            f"{name}: newline escapes differ: default={default_newlines}, "
            f"japanese={japanese_newlines}"
        )

    return problems


class JapaneseStringsTest(unittest.TestCase):
    def test_default_resources_are_unchanged(self):
        for module, spec in MODULES.items():
            with self.subTest(module=module):
                digest = hashlib.sha256(spec["default"].read_bytes()).hexdigest()
                self.assertEqual(
                    spec["sha256"],
                    digest,
                    f"{spec['default']} changed; update the Japanese translations and this fingerprint together",
                )

    def test_japanese_resources_cover_all_default_strings(self):
        for module, spec in MODULES.items():
            with self.subTest(module=module):
                self.assertTrue(
                    spec["japanese"].is_file(),
                    f"Missing Japanese resource file: {spec['japanese']}",
                )

                defaults = parse_strings(spec["default"])
                japanese = parse_strings(spec["japanese"])

                self.assertEqual(spec["count"], len(defaults))
                self.assertEqual(spec["count"], len(japanese))
                self.assertEqual(set(), set(defaults) - set(japanese), "Missing Japanese translations")
                self.assertEqual(set(), set(japanese) - set(defaults), "Unknown Japanese string names")

    def test_translations_preserve_arguments_entities_and_line_breaks(self):
        for module, spec in MODULES.items():
            with self.subTest(module=module):
                defaults = parse_strings(spec["default"])
                japanese = parse_strings(spec["japanese"])
                default_raw = parse_raw_string_bodies(spec["default"])
                japanese_raw = parse_raw_string_bodies(spec["japanese"])

                problems = []
                for name, default_value in defaults.items():
                    if name not in japanese:
                        continue
                    problems.extend(
                        validate_pair(
                            name,
                            default_value,
                            japanese[name],
                            default_raw[name],
                            japanese_raw[name],
                            spec["identical_allowed"],
                        )
                    )

                self.assertEqual([], problems, "\n".join(problems))

    def test_translations_preserve_technical_tokens_and_markup(self):
        for module, spec in MODULES.items():
            with self.subTest(module=module):
                defaults = parse_strings(spec["default"])
                japanese = parse_strings(spec["japanese"])

                problems = []
                for name, default_value in defaults.items():
                    if name not in japanese:
                        continue

                    japanese_value = japanese[name]
                    for token in sorted(set(TECHNICAL_TOKEN_RE.findall(default_value))):
                        if token not in japanese_value:
                            problems.append(f"{name}: missing technical token {token!r}")

                    if Counter(BACKTICK_TOKEN_RE.findall(default_value)) != Counter(
                        BACKTICK_TOKEN_RE.findall(japanese_value)
                    ):
                        problems.append(f"{name}: backtick markup differs")

                    if default_value.count("**") != japanese_value.count("**"):
                        problems.append(f"{name}: bold markup differs")

                self.assertEqual([], problems, "\n".join(problems))

    def test_validator_rejects_missing_translation(self):
        problems = validate_pair("sample", "Default", "", "Default", "", set())
        self.assertIn("sample: translation is empty", problems)

    def test_validator_rejects_missing_format_argument(self):
        problems = validate_pair("sample", "Kill process (%d)", "プロセスを終了", "Kill process (%d)", "プロセスを終了", set())
        self.assertTrue(any("format arguments differ" in problem for problem in problems))

    def test_validator_rejects_changed_format_argument_type(self):
        problems = validate_pair("sample", "Kill process (%d)", "プロセスを終了 (%s)", "Kill process (%d)", "プロセスを終了 (%s)", set())
        self.assertTrue(any("format arguments differ" in problem for problem in problems))

    def test_validator_rejects_missing_entity_reference(self):
        problems = validate_pair(
            "sample",
            "Termux Settings",
            "Termux の設定",
            "&TERMUX_APP_NAME; Settings",
            "Termux の設定",
            set(),
        )
        self.assertTrue(any("entity references differ" in problem for problem in problems))

    def test_validator_rejects_missing_line_break(self):
        problems = validate_pair("sample", "one\ntwo", "いちに", "one\\ntwo", "いちに", set())
        self.assertTrue(any("newline escapes differ" in problem for problem in problems))

    def test_validator_rejects_untranslated_string(self):
        problems = validate_pair("sample", "Settings", "Settings", "Settings", "Settings", set())
        self.assertIn(
            "sample: translation is identical to the default English string",
            problems,
        )


if __name__ == "__main__":
    unittest.main()
