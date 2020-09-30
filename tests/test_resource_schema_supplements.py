from ckanext.dcor_schemas import resource_schema_supplements as rss


def test_load():
    rss.load_schema_supplements()


def test_composite_loop():
    cil = rss.get_composite_item_list()
    for ci in cil:
        si = rss.SupplementItem.from_composite(composite_key=ci)
        ci2, val = si.to_composite()
        assert val is None
        assert ci == ci2


def test_get_composite_list():
    cil = rss.get_composite_item_list()
    for ci in cil:
        assert ci.startswith("sp:")
        assert ci.count(":") == 2


def test_get_composite_section_item_list():
    rss.get_composite_section_item_list()


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
