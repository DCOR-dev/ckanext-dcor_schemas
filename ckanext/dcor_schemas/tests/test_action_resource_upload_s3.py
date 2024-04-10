import pathlib
from unittest import mock

import pytest

from ckan import model
import ckan.tests.helpers as helpers
import ckan.tests.factories as factories
from dcor_shared.testing import synchronous_enqueue_job, upload_presigned_to_s3


import requests


data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
def test_action_resource_upload_get_url():
    """Get a simple upload URL and fields"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    test_context = {'ignore_auth': False,
                    'user': user['name'], 'model': model, 'api_version': 3}

    response = helpers.call_action("resource_upload_s3_urls",
                                   test_context,
                                   organization_id=owner_org["id"],
                                   )
    assert "url" in response
    assert "fields" in response
    assert "key" in response["fields"]
    assert "AWSAccessKeyId" in response["fields"]
    assert "policy" in response["fields"]
    assert "signature" in response["fields"]


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_action_resource_upload_get_url_and_upload(enqueue_job_mock):
    """Perform an upload directly to S3"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])

    test_context = {'ignore_auth': False,
                    'user': user['name'], 'model': model, 'api_version': 3}

    # Upload the resource to S3 (note that it is not required that the
    # dataset exists)
    response = helpers.call_action("resource_upload_s3_urls",
                                   test_context,
                                   organization_id=owner_org["id"],
                                   )
    upload_presigned_to_s3(
        psurl=response["url"],
        fields=response["fields"],
        path_to_upload=data_path / "calibration_beads_47.rtdc")

    # Create the dataset
    pkg_dict = helpers.call_action("package_create",
                                   test_context,
                                   title="My Test Dataset",
                                   authors="Peter Parker",
                                   license_id="CC-BY-4.0",
                                   state="draft",
                                   private=False,
                                   owner_org=owner_org["name"],
                                   )
    assert not pkg_dict["private"]

    # Update the dataset
    new_pkg_dict = helpers.call_action(
        "package_revise",
        test_context,
        match__id=pkg_dict["id"],
        update__resources__extend=[{"id": response["resource_id"],
                                    "name": "new_test.rtdc",
                                    }],
        )
    assert new_pkg_dict["package"]["num_resources"] == 1

    # Make sure the resource exists
    res_dict = helpers.call_action("resource_show", id=response["resource_id"])
    assert res_dict
    assert res_dict["id"] == response["resource_id"]
    assert res_dict["name"] == "new_test.rtdc"

    # Also attempt to download the resource
    dlurl = response["url"] + "/" + response["fields"]["key"]
    retdl = requests.get(dlurl)
    assert retdl.ok
