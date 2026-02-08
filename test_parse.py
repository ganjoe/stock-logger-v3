
import sys

def test_parse(val):
    try:
        parsed = float(val.replace(",", "."))
        print(f"Input: '{val}' -> Parsed: {parsed}")
    except ValueError:
        print(f"Input: '{val}' -> FAILED")

test_parse("10,50")
test_parse("10.50")
test_parse("10")
test_parse("1.234,56")
