from collections import OrderedDict
import datetime
import functools
import json
import numbers
import os
import pathlib
from pkg_resources import resource_listdir, resource_filename

from ckan.common import config


def validate_date(value):
    try:
        datetime.datetime.strptime(value, '%Y-%m-%d')
    except BaseException:
        return False
    else:
        return True


#: Parses from and to composite values
PARSERS = {
    "boolean": lambda x: str(x).lower() in ["true", "yes"],
    "date": str,
    "float": float,
    "integer": int,
    "list": lambda x: " ".join([y.strip() for y in x.split()]),
    "string": str,
}

#: Data types of supplements
CLASSES = {
    "boolean": bool,
    "date": str,
    "float": numbers.Real,
    "integer": numbers.Integral,
    "list": str,
    "string": str,
}

#: Data type validators
VALIDATORS = {
    "boolean": lambda x: isinstance(x, bool),
    "date": validate_date,
    "float": lambda x: isinstance(x, numbers.Real),
    "integer": lambda x: isinstance(x, numbers.Integral),
    "list": lambda x: isinstance(x, str),
    "string": lambda x: isinstance(x, str),
}


class SupplementItem(object):
    def __init__(self, section, key, value=None):
        """Represents a supplementary resource schema item

        Supplementray resource schemas are defined via
        .json files. They are loaded with `load_schema_supplements`.
        This is a convenience class for handling them.
        """
        self.section = section
        self.key = key
        self._item = get_item(section, key)
        self.value = None
        if value is not None:
            self.set_value(value)

    def __contains__(self, key):
        return self._item.__contains__(key)

    def __getitem__(self, key):
        if key in self._item:
            return self._item[key]
        else:
            raise KeyError("Property not found: '{}'!".format(key))

    @staticmethod
    def from_composite(composite_key, composite_value=None):
        """Load an instance from a composite key-value pair

        Parameters
        ----------
        composite_key: str
            e.g. "sp:cells:organism"
        composite_value: str, int, float, None
            e.g. "eGFP mCherry", 123, or 5.24

        Returns
        -------
        si: SupplementItem
        """
        _, section, key = composite_key.strip().split(":")
        si = SupplementItem(section=section, key=key)
        if not (composite_value is None
                or (isinstance(composite_value, str) and
                    len(composite_value) == 0)):
            si.set_value(PARSERS[si["type"]](composite_value))
        return si

    def to_composite(self):
        """Export the current instance to a composite key-value pair

        This implies converting lists to comma-separated strings
        """
        composite_key = "sp:{}:{}".format(self.section, self.key)
        if self.value is None:
            composite_value = None
        else:
            composite_value = PARSERS[self["type"]](self.value)
        return composite_key, composite_value

    def set_value(self, value):
        """Set a value of the key, perform checks"""
        # Check for type
        if not VALIDATORS[self["type"]](value):
            raise ValueError(
                f"Invalid value for '{self.key}'! You were supposed to pass "
                f"an object of type '{self['type']}'/{CLASSES[self['type']]} "
                f"but you gave me an instance of {type(value)} with a value "
                f"of '{value}'!")
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
    """Return a list of section dicts with name, description and item list

    This is used for rendering the items in an online form.
    """
    schemas = load_schema_supplements()
    csil = []
    for sec in schemas:
        il = []
        for item in schemas[sec]["items"]:
            si = SupplementItem(section=sec, key=item["key"])
            ck, _ = si.to_composite()
            if "example" in si:
                ph = "e.g. {}".format(si["example"])
            elif si["type"] == "boolean":
                ph = "e.g. yes"
            else:
                ph = "text"
            ti = si["name"]
            if "unit" in si:
                ti += " [{}]".format(si["unit"])
            if "hint" in si:
                ti += " ({})".format(si["hint"])
            il.append([ck, ti, ph])
        sd = {"name": schemas[sec]["name"].capitalize(),
              "hint": schemas[sec].get("hint", ""),
              "items": il,
              }
        csil.append(sd)
    return csil


def get_item(section, key):
    """Return the schema dictionary item for a section-key pair"""
    schemas = load_schema_supplements()
    for item in schemas[section]["items"]:
        if item["key"] == key:
            return item
    else:
        raise KeyError("Supplement [{}]: '{}' not found!".format(section, key))


@functools.lru_cache(maxsize=32)
def load_schema_supplements():
    """Load and merge the entire supplementary resource schema

    If "ckanext.dcor_schemas.json_resource_schema_dir" in ckan.ini
    is set to a directory on disk, then json files will be loaded from
    there. Otherwise (or if it is set to "package"), the schema shipped
    with this extension is loaded.
    """
    # determine the directory from which to load json files
    jd = config.get("ckanext.dcor_schemas.json_resource_schema_dir", "package")
    if jd == "package":  # use package json files (in this directory here)
        module = "ckanext.dcor_schemas"
        submod = "resource_schema_supplements"
        root = pathlib.Path(resource_filename(module, submod))
        filelist = resource_listdir(module, submod)
    else:  # use user-defined json files
        filelist = os.listdir(jd)
        root = pathlib.Path(jd)
    jsons = sorted([fi for fi in filelist if fi.endswith(".json")])
    schemas = OrderedDict()
    for js in jsons:
        key = js.split("_", 1)[1][:-5]
        with (root / js).open("r") as fp:
            try:
                schemas[key] = json.load(fp)
                assert key == schemas[key]["key"]
            except json.decoder.JSONDecodeError as e:
                if not e.args:
                    e.args = ('',)
                e.args = e.args + ("file {}".format(root/js),)
                raise e
    return schemas
