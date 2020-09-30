from collections import OrderedDict
import functools
import json
from pkg_resources import resource_listdir, resource_filename


#: Parses from and to composite values
PARSERS = {
    "string": (str, str),
    "integer": (int, int),
    "list": (lambda x: [y.strip() for y in x.split(",")],
             lambda x: ", ".join(x)),
}


class SupplementItem(object):
    def __init__(self, section, item, value=None):
        # TODO:
        # - do some verification
        self.section = section
        self.item = item
        self.value = None
        if value is not None:
            self.set_value(value)

    @staticmethod
    def from_composite(composite_key, composite_value):
        _, section, item = composite_key.strip().split(":")
        si = SupplementItem(section=section, item=item)
        schemas = load_schema_supplements()
        stype = schemas[si.section, si.item].get("type", "string")
        si.set_value(PARSERS[stype][0](composite_value))

    def to_composite(self):
        composite_key = "sp:{}:{}".format(self.section, self.item)
        schemas = load_schema_supplements()
        stype = schemas[self.section, self.item].get("type", "string")
        composite_value = PARSERS[stype][1](self.value)
        return composite_key, composite_value

    def set_value(self, value):
        # TODO:
        # - do some verification?
        self.value = value


def get_composite_item_list():
    """Return the composite item keys list (sp:section:key)"""
    schemas = load_schema_supplements()
    cil = []
    for sec in schemas:
        for item in schemas[sec]["items"]:
            cil.append("sp:{}:{}".format(sec, item["key"]))
    return cil


def get_composite_section_item_list():
    """Return a list of section dicts with name, description and item list"""
    schemas = load_schema_supplements()
    csil = []
    for sec in schemas:
        il = []
        for item in schemas[sec]["items"]:
            il.append("sp:{}:{}".format(sec, item["key"]))
        sd = {"name": schemas[sec]["name"].capitalize(),
              "hint": schemas[sec].get("hint", ""),
              "items": il,
              }
        csil.append(sd)
    return csil


@functools.lru_cache(maxsize=32)
def load_schema_supplements():
    module = "ckanext.dcor_schemas"
    submod = "resource_schema_supplements"
    filelist = resource_listdir(module, submod)
    jsons = sorted([fi for fi in filelist if fi.endswith(".json")])
    schemas = OrderedDict()
    for js in jsons:
        pp = resource_filename(module + "." + submod, js)
        key = js.split("_", 1)[1][:-5]
        with open(pp, "r") as fp:
            try:
                schemas[key] = json.load(fp)
            except json.decoder.JSONDecodeError as e:
                if not e.args:
                    e.args = ('',)
                e.args = e.args + ("file {}".format(pp),)
                raise e
    return schemas
