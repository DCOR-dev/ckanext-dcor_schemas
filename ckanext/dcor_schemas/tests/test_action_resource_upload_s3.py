import time
import pathlib

import pytest

from ckan import model
import ckan.tests.helpers as helpers
import ckan.tests.factories as factories

import requests
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

data_path = pathlib.Path(__file__).parent / "data"


def upload_presigned_to_s3(psurl, fields, path_to_upload):
    """Helper function for uploading data to S3

    This is exactly how DCOR-Aid would be uploading things (with the
    requests_toolbelt package). This could have been a little simpler,
    but for the sake of reproducibility, we do it the DCOR-Aid way.
    """
    # callback function for monitoring the upload progress
    # open the input file for streaming
    with path_to_upload.open("rb") as fd:
        fields["file"] = (fields["key"], fd)
        e = MultipartEncoder(fields=fields)
        m = MultipartEncoderMonitor(
            e, lambda monitor: print(f"Bytes: {monitor.bytes_read}"))
        # Increase the read size to speed-up upload (the default chunk
        # size for uploads in urllib is 8k which results in a lot of
        # Python code being involved in uploading a 20GB file; Setting
        # the chunk size to 4MB should increase the upload speed):
        # https://github.com/requests/toolbelt/issues/75
        # #issuecomment-237189952
        m._read = m.read
        m.read = lambda size: m._read(4 * 1024 * 1024)
        # perform the actual upload
        hrep = requests.post(
            psurl,
            data=m,
            headers={'Content-Type': m.content_type},
            verify=True,  # verify SSL connection
            timeout=27.3,  # timeout to avoid freezing
        )
    if hrep.status_code != 204:
        raise ValueError(
            f"Upload failed with {hrep.status_code}: {hrep.reason}")


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


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas dcor_depot')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_action_resource_upload_get_url_and_upload():
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
    response = helpers.call_action("resource_upload_s3_url",
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
                                   owner_org=owner_org["name"],
                                   )

    # Update the dataset
    new_pkg_dict = helpers.call_action(
        "package_revise",
        test_context,
        match__id=pkg_dict["id"],
        update__resources__extend=[{"id": response["resource_id"],
                                    "name": "new_test.rtdc",
                                    "private": False,
                                    }],
        )
    assert new_pkg_dict["package"]["num_resources"] == 1

    # Make sure the resource exists
    res_dict = helpers.call_action("resource_show", id=response["resource_id"])
    assert res_dict
    assert res_dict["id"] == response["resource_id"]
    assert res_dict["name"] == "new_test.rtdc"
    assert not res_dict["private"]

    # Also attempt to download the resource
    for ii in range(20):
        dlurl = response["url"] + "/" + response["fields"]["key"]
        retdl = requests.get(dlurl)
        if retdl.ok:
            break
        time.sleep(1)
    else:
        assert False
