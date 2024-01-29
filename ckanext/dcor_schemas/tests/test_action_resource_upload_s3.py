import pytest

from ckan import model
import ckan.tests.helpers as helpers
import ckan.tests.factories as factories


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_action_resource_upload_get_url():
    """Get a simple upload URL and fields"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    test_context = {'ignore_auth': False,
                    'user': user['name'], 'model': model, 'api_version': 3}

    response = helpers.call_action("resource_upload_s3_url",
                                   test_context,
                                   organization_id=owner_org["id"],
                                   )
    assert "url" in response
    assert "fields" in response
    assert "key" in response["fields"]
    assert "AWSAccessKeyId" in response["fields"]
    assert "policy" in response["fields"]
    assert "signature" in response["fields"]
