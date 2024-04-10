import pathlib

import pytest

import ckan.logic as logic
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers
from ckan import model

data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_upload_s3_normal():
    """Test basic positive authentication for requesting S3 upload URL"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    test_context = {'ignore_auth': False,
                    'user': user['name'], 'model': model, 'api_version': 3}
    # create a dataset
    helpers.call_auth("resource_upload_s3_urls",
                      test_context,
                      organization_id=owner_org["id"],
                      file_size=1024 * 1024,
                      )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_upload_s3_with_anon_user_fails():
    """Test fail auth for anonymous user"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    test_context = {'ignore_auth': False,
                    'user': None,
                    'api_version': 3}
    # create a dataset
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("resource_upload_s3_urls",
                          test_context,
                          organization_id=owner_org["id"],
                          )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_upload_s3_wrong_organization_fails():
    """Test basic authentication for user not part of an organization"""
    user = factories.User()
    factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    invalid_org = factories.Organization()
    test_context = {'ignore_auth': False,
                    'user': user['name'], 'model': model, 'api_version': 3}
    # create a dataset
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("resource_upload_s3_urls",
                          test_context,
                          organization_id=invalid_org["id"],
                          )
