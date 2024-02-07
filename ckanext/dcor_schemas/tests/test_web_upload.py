import json
import pathlib
import pytest
from unittest import mock

import ckan.tests.factories as factories

from dcor_shared.testing import synchronous_enqueue_job, upload_presigned_to_s3

import requests


data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_upload_to_s3_and_verify(enqueue_job_mock, app):
    user = factories.UserWithToken()

    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])

    # Get the upload URL
    resp_s3 = app.get(
        "/api/3/action/resource_upload_s3_url",
        params={"organization_id": owner_org["id"]},
        headers={"authorization": user["token"]},
        status=200)
    data_s3 = json.loads(resp_s3.data)["result"]

    # Upload a resource with that information
    upload_presigned_to_s3(
        psurl=data_s3["url"],
        fields=data_s3["fields"],
        path_to_upload=data_path / "calibration_beads_47.rtdc")

    # Create a dataset
    resp_ds = app.post(
        "/api/3/action/package_create",
        params={"state": "draft",
                "private": True,
                "owner_org": owner_org["id"],
                "authors": "Hans Peter",
                "title": "a new world",
                "license_id": "CC0-1.0",
                },
        headers={"authorization": user["token"]},
        status=200)
    data_ds = json.loads(resp_ds.data)["result"]
    assert "id" in data_ds, "sanity check"

    # Add the resource to the dataset
    rid = data_s3["resource_id"]
    res_str = ('[{'
               '"name":"data.rtdc",'
               f'"id":"{rid}"'
               '}]'
               )
    resp_res = app.post(
        "/api/3/action/package_revise",
        params={"match__id": data_ds["id"],
                "update__resources__extend": res_str,
                },
        headers={"authorization": user["token"]},
        status=200
        )
    data_res = json.loads(resp_res.data)["result"]
    res_dict = data_res["package"]["resources"][0]
    assert res_dict["id"] == rid

    # activate the dataset
    app.post(
        "/api/3/action/package_revise",
        params={"match__id": data_ds["id"],
                "update__state": "active",
                },
        headers={"authorization": user["token"]},
        status=200
    )

    # Make sure the resource is OK
    resp_res2 = app.get(
        "/api/3/action/resource_show",
        params={"id": rid},
        headers={"authorization": user["token"]},
        status=200
        )
    data_res2 = json.loads(resp_res2.data)["result"]
    assert data_res2["id"] == rid
    assert data_res2["s3_available"]
    assert data_res2["s3_url"] == \
           data_s3["url"] + "/" + data_s3["fields"]["key"]

    # Attempt to download the resource without authorization
    ret = requests.get(data_res2["s3_url"])
    assert not ret.ok
    assert ret.reason == "Forbidden"
