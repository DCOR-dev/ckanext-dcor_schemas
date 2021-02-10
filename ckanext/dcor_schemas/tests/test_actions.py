import pytest

import ckan.tests.helpers as helpers


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_action_resource_schema_supplements():
    """Just a general test, may fail if rss changes"""
    rss = helpers.call_action("resource_schema_supplements")
    for sec in ["general", "cells", "artificial"]:
        assert sec in rss
    assert len(rss["general"]["requires"]) == 0
    assert rss["general"]["items"][0]["key"] == "sample type"
    assert rss["general"]["items"][0]["type"] == "string"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_action_supported_resource_suffixes():
    """Just a general test, may fail if rss changes"""
    suffixes = helpers.call_action("supported_resource_suffixes")
    assert ".rtdc" in suffixes
    assert ".docx" not in suffixes, "please don't remove this assertion!"
