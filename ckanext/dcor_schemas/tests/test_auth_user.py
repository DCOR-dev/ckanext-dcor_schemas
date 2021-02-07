import pytest

import ckan.tests.factories as factories
import ckan.tests.helpers as helpers
from ckan import model


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_login_user_create_datasets():
    """allow all logged-in users to create datasets"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    context = {'ignore_auth': False, 'user': user['name'], "model": model}
    success = helpers.call_auth("package_create", context,
                                title="test-group",
                                authors="Peter Pan",
                                license_id="CC-BY-4.0",
                                owner_org=owner_org["id"],
                                )
    assert success


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_login_user_create_circles():
    """allow all logged-in users to create circles"""
    user = factories.User()
    context = {'ignore_auth': False, 'user': user['name'], "model": model}
    success = helpers.call_auth("organization_create", context,
                                name="test-org")
    assert success


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_login_user_create_collections():
    """allow all logged-in users to create collections"""
    user = factories.User()
    context = {'ignore_auth': False, 'user': user['name'], "model": model}
    success = helpers.call_auth("group_create", context, name="test-group")
    assert success
