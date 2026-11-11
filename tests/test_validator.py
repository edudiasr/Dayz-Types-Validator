import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from types_validator.cli import main
from types_validator.limits import Limits
from types_validator.validator import validate_bytes

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def make_type(name: str = "AKM", body: str | None = None) -> str:
    if body is None:
        body = """
        <nominal>4</nominal><lifetime>28800</lifetime><restock>0</restock><min>2</min>
        <quantmin>-1</quantmin><quantmax>-1</quantmax><cost>100</cost>
        <flags count_in_cargo="0" count_in_hoarder="0" count_in_map="1"
               count_in_player="0" crafted="0" deloot="0"/>
        <category name="weapons"/><usage name="Military"/>"""
    return f'<type name="{name}">{body}</type>'


def check(*types: str, limits: Limits | None = None):
    xml = "<types>" + "".join(types) + "</types>"
    return validate_bytes(xml.encode(), limits=limits)


def codes(report) -> list[str]:
    return [issue.code for issue in report.issues]


def replace(old: str, new: str) -> str:
    return make_type(body=make_type().split(">", 1)[1].rsplit("</type>", 1)[0].replace(old, new))


class ValidTypes(unittest.TestCase):
    def test_valid_type_has_no_issues(self):
        report = check(make_type())
        self.assertEqual(report.issues, [])
        self.assertEqual(report.type_count, 1)
        self.assertEqual(report.spawning_count, 1)

    def test_example_file_is_clean(self):
        report = validate_bytes((EXAMPLES / "types_ok.xml").read_bytes())
        self.assertEqual(report.issues, [])
        self.assertEqual(report.nominal_by_category["food"], 40)


class StructureErrors(unittest.TestCase):
    def test_broken_xml_reports_line(self):
        report = validate_bytes(b"<types>\n<type name='A'>\n</types>")
        self.assertEqual(codes(report), ["E001"])
        self.assertEqual(report.issues[0].line, 3)

    def test_wrong_root(self):
        self.assertEqual(codes(validate_bytes(b"<lists/>")), ["E002"])

    def test_type_without_name(self):
        self.assertIn("E003", codes(check(make_type(name=""))))

    def test_duplicate_is_case_insensitive(self):
        report = check(make_type("AKM"), make_type("akm"))
        self.assertEqual(codes(report), ["E004"])

    def test_repeated_single_tag(self):
        self.assertIn("E005", codes(check(replace("<cost>100</cost>", "<cost>100</cost><cost>5</cost>"))))

    def test_unknown_tag_is_warning(self):
        self.assertEqual(codes(check(replace("<cost>100</cost>", "<cost>100</cost><spawn/>"))), ["W001"])

    def test_missing_tag_is_warning(self):
        self.assertEqual(codes(check(replace("<cost>100</cost>", ""))), ["W002"])


class ValueErrors(unittest.TestCase):
    def test_non_integer(self):
        self.assertIn("E006", codes(check(replace("<lifetime>28800</lifetime>", "<lifetime>dez</lifetime>"))))

    def test_negative(self):
        self.assertIn("E007", codes(check(replace("<restock>0</restock>", "<restock>-5</restock>"))))

    def test_min_above_nominal(self):
        self.assertEqual(codes(check(replace("<min>2</min>", "<min>9</min>"))), ["E008"])

    def test_quantity_out_of_range(self):
        body = replace("<quantmin>-1</quantmin><quantmax>-1</quantmax>", "<quantmin>10</quantmin><quantmax>150</quantmax>")
        self.assertEqual(codes(check(body)), ["E009"])

    def test_quantmin_above_quantmax(self):
        body = replace("<quantmin>-1</quantmin><quantmax>-1</quantmax>", "<quantmin>80</quantmin><quantmax>20</quantmax>")
        self.assertEqual(codes(check(body)), ["E010"])

    def test_only_one_quantity_is_minus_one(self):
        body = replace("<quantmax>-1</quantmax>", "<quantmax>50</quantmax>")
        self.assertEqual(codes(check(body)), ["W004"])

    def test_flag_must_be_zero_or_one(self):
        self.assertEqual(codes(check(replace('crafted="0"', 'crafted="sim"'))), ["E011"])

    def test_missing_flag_attribute(self):
        self.assertEqual(codes(check(replace('deloot="0"', ""))), ["W007"])


class SpawnRules(unittest.TestCase):
    def test_spawning_item_without_location(self):
        body = replace('<category name="weapons"/><usage name="Military"/>', "")
        self.assertEqual(codes(check(body)), ["W003"])

    def test_item_with_zero_nominal_needs_no_location(self):
        body = replace('<category name="weapons"/><usage name="Military"/>', "").replace(
            "<nominal>4</nominal>", "<nominal>0</nominal>"
        ).replace("<min>2</min>", "<min>0</min>")
        self.assertEqual(codes(check(body)), [])

    def test_repeated_usage(self):
        body = replace('<usage name="Military"/>', '<usage name="Military"/><usage name="military"/>')
        self.assertEqual(codes(check(body)), ["W005"])

    def test_usage_without_name(self):
        self.assertEqual(codes(check(replace('<usage name="Military"/>', "<usage/>"))), ["E012"])


class LimitsRules(unittest.TestCase):
    def setUp(self):
        self.limits = Limits()
        self.limits.merge_file((EXAMPLES / "cfglimitsdefinition.xml").read_bytes())

    def test_known_names_pass(self):
        self.assertEqual(check(make_type(), limits=self.limits).issues, [])

    def test_unknown_usage(self):
        body = replace('<usage name="Military"/>', '<usage name="Militar"/>')
        self.assertEqual(codes(check(body, limits=self.limits)), ["E013"])

    def test_user_list(self):
        self.limits.merge_file(
            b'<user_lists><usageflags><user name="TownVillage"><usage name="Town"/></user>'
            b"</usageflags></user_lists>"
        )
        ok = replace('<usage name="Military"/>', '<usage user="TownVillage"/>')
        bad = replace('<usage name="Military"/>', '<usage user="Coastal"/>')
        self.assertEqual(codes(check(ok, limits=self.limits)), [])
        self.assertEqual(codes(check(bad, limits=self.limits)), ["E013"])


class CommandLine(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([*args, "--no-color"])
        return code, out.getvalue()

    def test_clean_file_exits_zero(self):
        code, output = self.run_cli(str(EXAMPLES / "types_ok.xml"))
        self.assertEqual(code, 0)
        self.assertIn("nenhum problema encontrado", output)

    def test_file_with_errors_exits_one(self):
        code, _ = self.run_cli(str(EXAMPLES / "types_com_erros.xml"))
        self.assertEqual(code, 1)

    def test_json_output(self):
        _, output = self.run_cli(str(EXAMPLES / "types_com_erros.xml"), "--format", "json")
        data = json.loads(output)
        self.assertEqual(data[0]["types"], 4)
        self.assertGreater(data[0]["errors"], 0)

    def test_missing_file_exits_two(self):
        code, _ = self.run_cli("nao_existe.xml")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
