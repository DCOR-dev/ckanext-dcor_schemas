import json
import pathlib
import pytest
from unittest import mock
import uuid

import ckan.tests.factories as factories

from dcor_shared import sha256sum
from dcor_shared.testing import synchronous_enqueue_job, upload_presigned_to_s3

import requests


data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_upload_to_s3_and_verify(enqueue_job_mock, app):
    upload_path = data_path / "calibration_beads_47.rtdc"

    user = factories.UserWithToken()

    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])

    # Get the upload URL
    resp_s3 = app.get(
        "/api/3/action/resource_upload_s3_urls",
        params={"organization_id": owner_org["id"],
                "file_size": upload_path.stat().st_size},
        headers={"authorization": user["token"]},
        status=200)
    data_s3 = json.loads(resp_s3.data)["result"]

    # Upload a resource with that information
    upload_presigned_to_s3(
        path=data_path / "calibration_beads_47.rtdc",
        upload_urls=data_s3["upload_urls"],
        complete_url=data_s3["complete_url"],
    )

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

    # Activate the dataset
    app.post(
        "/api/3/action/package_revise",
        params={"match__id": data_ds["id"],
                "update__state": "active",
                },
        headers={"authorization": user["token"]},
        status=200
    )

    # Make sure the resource is OK in the database
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
        data_s3["upload_urls"][0].split("?")[0]

    # Attempt to download the resource without authorization
    ret = requests.get(data_res2["s3_url"])
    assert not ret.ok
    assert ret.reason == "Forbidden"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_upload_to_s3_and_verify_public(enqueue_job_mock, app):
    upload_path = data_path / "calibration_beads_47.rtdc"

    user = factories.UserWithToken()

    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])

    # Get the upload URL
    resp_s3 = app.get(
        "/api/3/action/resource_upload_s3_urls",
        params={"organization_id": owner_org["id"],
                "file_size": upload_path.stat().st_size},
        headers={"authorization": user["token"]},
        status=200)
    data_s3 = json.loads(resp_s3.data)["result"]

    # Upload a resource with that information
    upload_presigned_to_s3(
        path=data_path / "calibration_beads_47.rtdc",
        upload_urls=data_s3["upload_urls"],
        complete_url=data_s3["complete_url"],
    )

    # Create a dataset
    resp_ds = app.post(
        "/api/3/action/package_create",
        params={"state": "draft",
                "private": False,
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

    # Activate the dataset
    app.post(
        "/api/3/action/package_revise",
        params={"match__id": data_ds["id"],
                "update__state": "active",
                },
        headers={"authorization": user["token"]},
        status=200
    )

    # Make sure the resource is OK in the database
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
        data_s3["upload_urls"][0].split("?")[0]

    # Download the resource without authentication
    ret = requests.get(data_res2["s3_url"])
    assert ret.ok

    # Verify that the resource is the same
    pout = upload_path.with_name("download.rtdc")
    pout.write_bytes(ret.content)
    assert sha256sum(pout) == sha256sum(upload_path)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_upload_to_s3_etag_not_allowed(enqueue_job_mock, app):
    upload_path = data_path / "calibration_beads_47.rtdc"

    user = factories.UserWithToken()

    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])

    # Get the upload URL
    resp_s3 = app.get(
        "/api/3/action/resource_upload_s3_urls",
        params={"organization_id": owner_org["id"],
                "file_size": upload_path.stat().st_size},
        headers={"authorization": user["token"]},
        status=200)
    data_s3 = json.loads(resp_s3.data)["result"]

    # Upload a resource with that information
    upload_presigned_to_s3(
        path=data_path / "calibration_beads_47.rtdc",
        upload_urls=data_s3["upload_urls"],
        complete_url=data_s3["complete_url"],
    )

    # Create a dataset
    resp_ds = app.post(
        "/api/3/action/package_create",
        params={"state": "draft",
                "private": False,
                "owner_org": owner_org["id"],
                "authors": "Hans Peter",
                "title": "a new world",
                "license_id": "CC0-1.0",
                },
        headers={"authorization": user["token"]},
        status=200)
    data_ds = json.loads(resp_ds.data)["result"]
    assert "id" in data_ds, "sanity check"

    # Add the resource to the dataset, specifying a random etag
    rid = data_s3["resource_id"]
    rnd256 = "81a89c74b50282fc02e4faa7b654a05a"
    res_str = ('[{'
               '"name":"data.rtdc",'
               f'"id":"{rid}",'
               f'"etag":"{rnd256}"'
               '}]'
               )
    resp_res = app.post(
        "/api/3/action/package_revise",
        params={"match__id": data_ds["id"],
                "update__resources__extend": res_str,
                },
        headers={"authorization": user["token"]},
        status=403  # User forbidden to set etag
    )
    error = json.loads(resp_res.data)["error"]
    assert "Regular users may not specify 'etag'" in error["message"]


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_upload_to_s3_sha256_not_allowed(enqueue_job_mock, app):
    upload_path = data_path / "calibration_beads_47.rtdc"

    user = factories.UserWithToken()

    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])

    # Get the upload URL
    resp_s3 = app.get(
        "/api/3/action/resource_upload_s3_urls",
        params={"organization_id": owner_org["id"],
                "file_size": upload_path.stat().st_size},
        headers={"authorization": user["token"]},
        status=200)
    data_s3 = json.loads(resp_s3.data)["result"]

    # Upload a resource with that information
    upload_presigned_to_s3(
        path=data_path / "calibration_beads_47.rtdc",
        upload_urls=data_s3["upload_urls"],
        complete_url=data_s3["complete_url"],
    )

    # Create a dataset
    resp_ds = app.post(
        "/api/3/action/package_create",
        params={"state": "draft",
                "private": False,
                "owner_org": owner_org["id"],
                "authors": "Hans Peter",
                "title": "a new world",
                "license_id": "CC0-1.0",
                },
        headers={"authorization": user["token"]},
        status=200)
    data_ds = json.loads(resp_ds.data)["result"]
    assert "id" in data_ds, "sanity check"

    # Add the resource to the dataset, specifying a random sha256sum
    rid = data_s3["resource_id"]
    rnd256 = "8486a10c4393cee1c25392769ddd3b2d6c242d6ec7928e1414efff7dfb2f07ef"
    res_str = ('[{'
               '"name":"data.rtdc",'
               f'"id":"{rid}",'
               f'"sha256":"{rnd256}"'
               '}]'
               )
    resp_res = app.post(
        "/api/3/action/package_revise",
        params={"match__id": data_ds["id"],
                "update__resources__extend": res_str,
                },
        headers={"authorization": user["token"]},
        status=403  # User forbidden to set SHA256
    )
    error = json.loads(resp_res.data)["error"]
    assert "Regular users may not specify 'sha256'" in error["message"]


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_upload_to_s3_sha256_not_allowed_update(enqueue_job_mock, app):
    upload_path = data_path / "calibration_beads_47.rtdc"

    user = factories.UserWithToken()

    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])

    # Get the upload URL
    resp_s3 = app.get(
        "/api/3/action/resource_upload_s3_urls",
        params={"organization_id": owner_org["id"],
                "file_size": upload_path.stat().st_size},
        headers={"authorization": user["token"]},
        status=200)
    data_s3 = json.loads(resp_s3.data)["result"]

    # Upload a resource with that information
    upload_presigned_to_s3(
        path=data_path / "calibration_beads_47.rtdc",
        upload_urls=data_s3["upload_urls"],
        complete_url=data_s3["complete_url"],
    )

    # Create a dataset
    resp_ds = app.post(
        "/api/3/action/package_create",
        params={"state": "draft",
                "private": False,
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
    app.post(
        "/api/3/action/package_revise",
        params={"match__id": data_ds["id"],
                "update__resources__extend": res_str,
                },
        headers={"authorization": user["token"]},
        status=200
    )

    # Attempt to update the resource with a bad SHA256 hash
    rnd256 = "8486a10c4393cee1c15392769ddd3b2d6c242d6ec7928e1414efff7dfb2f07ef"
    res_str2 = ('[{'
                '"name":"data.rtdc",'
                f'"id":"{rid}",'
                f'"sha256":"{rnd256}"'
                '}]'
                )
    resp_res2 = app.post(
        "/api/3/action/package_revise",
        params={"match__id": data_ds["id"],
                "update__resources__extend": res_str2,
                },
        headers={"authorization": user["token"]},
        status=403  # User forbidden to set SHA256
    )

    error = json.loads(resp_res2.data)["error"]
    assert "Regular users may not edit 'sha256'" in error["message"]


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_upload_to_s3_wrong_key_fails(enqueue_job_mock, app):
    user = factories.UserWithToken()

    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])

    # Create a dataset
    resp_ds = app.post(
        "/api/3/action/package_create",
        params={"state": "draft",
                "private": False,
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
    rid = str(uuid.uuid4())
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
        status=403  # Forbidden
    )
    error = json.loads(resp_res.data)["error"]
    assert "not available on S3" in error["message"]


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_upload_to_s3_not_allowed_to_specify_metadata(enqueue_job_mock, app):
    upload_path = data_path / "calibration_beads_47.rtdc"

    user = factories.UserWithToken()

    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])

    # Get the upload URL
    resp_s3 = app.get(
        "/api/3/action/resource_upload_s3_urls",
        params={"organization_id": owner_org["id"],
                "file_size": upload_path.stat().st_size},
        headers={"authorization": user["token"]},
        status=200)
    data_s3 = json.loads(resp_s3.data)["result"]

    # Upload a resource with that information
    upload_presigned_to_s3(
        path=data_path / "calibration_beads_47.rtdc",
        upload_urls=data_s3["upload_urls"],
        complete_url=data_s3["complete_url"],
    )

    # Create a dataset
    resp_ds = app.post(
        "/api/3/action/package_create",
        params={"state": "draft",
                "private": False,
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
               f'"id":"{rid}",'
               f'"url":"https://example.com/{rid}"'  # this is not allowed
               '}]'
               )
    app.post(
        "/api/3/action/package_revise",
        params={"match__id": data_ds["id"],
                "update__resources__extend": res_str,
                },
        headers={"authorization": user["token"]},
        status=403  # not authorized to set "url"
    )
