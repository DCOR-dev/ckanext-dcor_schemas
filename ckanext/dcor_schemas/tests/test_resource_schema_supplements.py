from ckanext.dcor_schemas import resource_schema_supplements as rss
import pytest


def test_check_types():
    schema = rss.load_schema_supplements()
    for section in schema:
        assert section == schema[section]["key"]
        for item in schema[section]["items"]:
            msg = "Invalid type [{}]:{} '{}'".format(
                section, item["key"], item["type"])
            assert item["type"] in rss.PARSERS, msg
            assert item["type"] in rss.CLASSES, msg


def test_check_units():
    schema = rss.load_schema_supplements()
    for section in schema:
        assert section == schema[section]["key"]
        for item in schema[section]["items"]:
            if "unit" in item:
                msg = "Invalid unit [{}]:{} '{}'".format(
                    section, item["key"], item["unit"])
                assert isinstance(item["unit"], str), msg


@pytest.mark.parametrize("invalid_date", ["2011-15-01", "peter", "2020-1212"])
def test_date_string(invalid_date):
    try:
        rss.SupplementItem.from_composite(
                composite_key="sp:chip:production date",
                composite_value=invalid_date)  # invalid date
    except ValueError:
        pass


def test_composite_loop():
    cil = rss.get_composite_item_list()
    for ci in cil:
        si = rss.SupplementItem.from_composite(composite_key=ci)
        ci2, val = si.to_composite()
        assert val is None
        assert ci == ci2


def test_composite_loop_with_example():
    cil = rss.get_composite_item_list()
    for ci in cil:
        si = rss.SupplementItem.from_composite(composite_key=ci)
        if "example" in si:
            si.set_value(si["example"])
            ci2, cval = si.to_composite()
            assert cval is not None
            # and one more back
            si2 = rss.SupplementItem.from_composite(composite_key=ci2,
                                                    composite_value=cval)
            assert si2.value == si["example"]


def test_get_composite_list():
    cil = rss.get_composite_item_list()
    for ci in cil:
        assert ci.startswith("sp:")
        assert ci.count(":") == 2


def test_get_composite_section_item_list():
    rss.get_composite_section_item_list()


def test_get_wrong_item():
    try:
        rss.SupplementItem.from_composite(composite_key="sp:cells:peter pan",
                                          composite_value="human")
    except KeyError:
        pass


def test_load():
    rss.load_schema_supplements()


def test_supplement_item():
    si = rss.SupplementItem.from_composite(composite_key="sp:cells:organism",
                                           composite_value="human")
    assert si["type"] == "string"
    assert si["key"] == "organism"


if __name__ == "__main__":
    # Run all tests
    loc = locals()
    for key in list(loc.keys()):
        if key.startswith("test_") and hasattr(loc[key], "__call__"):
            loc[key]()
