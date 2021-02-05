import pytest

# import ckan.logic as logic
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_allow_user_to_create_datasets():
    """allow all logged-in users to create datasets"""
    user = factories.User()
    context = {'ignore_auth': False, 'user': user['name']}
    helpers.call_action("organization_create", context, name="test-org")
    helpers.call_action("package_create", context,
                        title="test-group",
                        authors="Peter Pan",
                        license_id="CC-BY-4.0",
                        owner_org="test-org",
                        )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_allow_user_to_create_collections():
    """allow all logged-in users to create collections"""
    user = factories.User()
    context = {'ignore_auth': False, 'user': user['name']}
    helpers.call_action("group_create", context, name="test-group")
