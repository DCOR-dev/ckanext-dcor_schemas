from collections import OrderedDict
import functools
import json
from pkg_resources import resource_listdir, resource_filename


#: Parses from and to composite values
PARSERS = {
    "float": (float, float),
    "integer": (int, int),
    "list": (lambda x: [y.strip() for y in x.split(",")],
             lambda x: ", ".join(x)),
    "string": (str, str),
}


class SupplementItem(object):
    def __init__(self, section, key, value=None):
        # TODO:
        # - do some verification
        self.section = section
        self.key = key
        self._item = get_item(section, key)
        self.value = None
        if value is not None:
            self.set_value(value)

    def __getitem__(self, key):
        if key in self._item:
            return self._item[key]
        elif key == "type":
            return "string"
        elif key in ["example", "hint"]:
            return ""
        else:
            raise KeyError("Property not found: '{}'!".format(key))

    @staticmethod
    def from_composite(composite_key, composite_value=None):
        _, section, key = composite_key.strip().split(":")
        si = SupplementItem(section=section, key=key)
        if not (composite_value is None or len(composite_value) == 0):
            si.set_value(PARSERS[si["type"]][0](composite_value))
        return si

    def to_composite(self):
        composite_key = "sp:{}:{}".format(self.section, self.key)
        if self.value is not None:
            composite_value = PARSERS[self["type"]][1](self.value)
        else:
            composite_value = None
        return composite_key, composite_value

    def set_value(self, value):
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
            si = SupplementItem(section=sec, key=item["key"])
            ck, _ = si.to_composite()
            ph = "e.g. {}".format(si["example"]) if si["example"] else "text"
            ti = si["name"].capitalize()
            if si["hint"]:
                ti += " ({})".format(si["hint"])
            il.append([ck, ti, ph])
        sd = {"name": schemas[sec]["name"].capitalize(),
              "hint": schemas[sec].get("hint", ""),
              "items": il,
              }
        csil.append(sd)
    return csil


def get_item(section, key):
    schemas = load_schema_supplements()
    for item in schemas[section]["items"]:
        if item["key"] == key:
            return item
    else:
        raise KeyError("Supplement [{}]: '{}' not found!".format(section, key))


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
                assert key == schemas[key]["key"]
            except json.decoder.JSONDecodeError as e:
                if not e.args:
                    e.args = ('',)
                e.args = e.args + ("file {}".format(pp),)
                raise e
    return schemas
