import ckan.plugins.toolkit as toolkit

from . import resource_schema_supplements as rss
from .validate import RESOURCE_EXTS


@toolkit.side_effect_free
def get_resource_schema_supplements(context, data_dict=None):
    """Dictionary of joined resource schema supplements"""
    schema = rss.load_schema_supplements()
    return schema


@toolkit.side_effect_free
def get_supported_resource_suffixes(context, data_dict=None):
    """List of supported resource suffixes"""
    return RESOURCE_EXTS
