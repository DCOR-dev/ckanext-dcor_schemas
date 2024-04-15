""" Testing background jobs

Due to the asynchronous nature of background jobs, code that uses them needs
to be handled specially when writing tests.

A common approach is to use the mock package to replace the
ckan.plugins.toolkit.enqueue_job function with a mock that executes jobs
synchronously instead of asynchronously
"""
from unittest import mock
import pathlib

import dclab
import numpy as np
import pytest

import ckan.lib
import ckan.tests.factories as factories
from ckan.tests import helpers

from dcor_shared.testing import (
    make_dataset, make_dataset_via_s3, synchronous_enqueue_job
)
import dcor_shared
import ckanext.dcor_schemas.plugin
import ckanext.dcor_schemas.jobs


data_dir = pathlib.Path(__file__).parent / "data"


def test_sha256sum(tmp_path):
    p = tmp_path / "test.txt"
    p.write_text("Sum this up!")
    ist = ckanext.dcor_schemas.jobs.sha256sum(p)
    soll = "d00df55b97a60c78bbb137540e1b60647a5e6b216262a95ab96cafd4519bcf6a"
    assert ist == soll


# dcor_depot must come first, because jobs are run in sequence and the
# symlink_user_dataset jobs must be executed first so that dcor_schemas
# does not complain about resources not available in wait_for_resource.
@pytest.mark.ckan_config('ckan.plugins', 'dcor_depot dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_symlink_user_dataset(enqueue_job_mock, create_with_upload,
                              monkeypatch, ckan_config, tmpdir):
    monkeypatch.setitem(ckan_config, 'ckan.storage_path', str(tmpdir))
    monkeypatch.setattr(ckan.lib.uploader,
                        'get_storage_path',
                        lambda: str(tmpdir))
    monkeypatch.setattr(
        ckanext.dcor_schemas.plugin,
        'DISABLE_AFTER_DATASET_CREATE_FOR_CONCURRENT_JOB_TESTS',
        True)

    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False,
                      'user': user['name'],
                      'api_version': 3}
    ds_dict = make_dataset(create_context, owner_org,
                           activate=False)

    content = (data_dir / "calibration_beads_47.rtdc").read_bytes()
    result = create_with_upload(
        content, 'test.rtdc',
        url="upload",
        package_id=ds_dict["id"],
        context=create_context,
    )

    resource = helpers.call_action("resource_show", id=result["id"])
    assert dcor_shared.get_resource_path(result["id"]).exists()
    assert resource["dc:experiment:date"] == "2018-12-11"
    assert resource["dc:experiment:event count"] == 47
    assert np.allclose(resource["dc:setup:flow rate"], 0.06)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_set_etag_job(enqueue_job_mock):
    user = factories.User()
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    path = data_dir / "calibration_beads_47.rtdc"
    ds_dict, rs_dict = make_dataset_via_s3(
        create_context=create_context,
        resource_path=path,
        activate=False)
    print(rs_dict)
    resource = helpers.call_action("resource_show", id=rs_dict["id"])
    assert not dcor_shared.get_resource_path(rs_dict["id"]).exists()
    md5sum = "108d47e80f3e5f35110493b1fdcd30d5"
    assert resource["etag"] == md5sum


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_set_format_job(enqueue_job_mock, create_with_upload, monkeypatch,
                        ckan_config, tmpdir):
    monkeypatch.setitem(ckan_config, 'ckan.storage_path', str(tmpdir))
    monkeypatch.setattr(ckan.lib.uploader,
                        'get_storage_path',
                        lambda: str(tmpdir))
    monkeypatch.setattr(
        ckanext.dcor_schemas.plugin,
        'DISABLE_AFTER_DATASET_CREATE_FOR_CONCURRENT_JOB_TESTS',
        True)

    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    ds_dict = make_dataset(create_context, owner_org, activate=False)
    path = data_dir / "calibration_beads_47.rtdc"
    # create dataset without fluorescence
    tmppath = pathlib.Path(tmpdir) / "calibratino_beads_nofl.rtdc"
    with dclab.new_dataset(path) as ds:
        ds.export.hdf5(tmppath, features=["deform", "bright_avg", "area_um"])
    content = tmppath.read_bytes()
    result = create_with_upload(
        content, 'test.rtdc',
        url="upload",
        package_id=ds_dict["id"],
        context=create_context,
    )
    resource = helpers.call_action("resource_show", id=result["id"])
    assert dcor_shared.get_resource_path(result["id"]).exists()
    assert resource["format"] == "RT-DC"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_set_format_job_fl(enqueue_job_mock, create_with_upload, monkeypatch,
                           ckan_config, tmpdir):
    monkeypatch.setitem(ckan_config, 'ckan.storage_path', str(tmpdir))
    monkeypatch.setattr(ckan.lib.uploader,
                        'get_storage_path',
                        lambda: str(tmpdir))
    monkeypatch.setattr(
        ckanext.dcor_schemas.plugin,
        'DISABLE_AFTER_DATASET_CREATE_FOR_CONCURRENT_JOB_TESTS',
        True)

    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    ds_dict = make_dataset(create_context, owner_org, activate=False)
    content = (data_dir / "calibration_beads_47.rtdc").read_bytes()
    result = create_with_upload(
        content, 'test.rtdc',
        url="upload",
        package_id=ds_dict["id"],
        context=create_context,
    )
    resource = helpers.call_action("resource_show", id=result["id"])
    assert dcor_shared.get_resource_path(result["id"]).exists()
    assert resource["format"] == "RT-FDC"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_set_sha256_job(enqueue_job_mock, create_with_upload, monkeypatch,
                        ckan_config, tmpdir):
    monkeypatch.setitem(ckan_config, 'ckan.storage_path', str(tmpdir))
    monkeypatch.setattr(ckan.lib.uploader,
                        'get_storage_path',
                        lambda: str(tmpdir))
    monkeypatch.setattr(
        ckanext.dcor_schemas.plugin,
        'DISABLE_AFTER_DATASET_CREATE_FOR_CONCURRENT_JOB_TESTS',
        True)

    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    ds_dict = make_dataset(create_context, owner_org, activate=False)
    content = (data_dir / "calibration_beads_47.rtdc").read_bytes()
    result = create_with_upload(
        content, 'test.rtdc',
        url="upload",
        package_id=ds_dict["id"],
        context=create_context,
    )
    resource = helpers.call_action("resource_show", id=result["id"])
    assert dcor_shared.get_resource_path(result["id"]).exists()
    sha = "490efdf5d9bb4cd4b2a6bcf2fe54d4dc201c38530140bcb168980bf8bf846c73"
    assert resource["sha256"] == sha


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_set_sha256_job_empty_file(enqueue_job_mock, create_with_upload,
                                   monkeypatch, ckan_config, tmpdir):
    monkeypatch.setitem(ckan_config, 'ckan.storage_path', str(tmpdir))
    monkeypatch.setattr(ckan.lib.uploader,
                        'get_storage_path',
                        lambda: str(tmpdir))
    monkeypatch.setattr(
        ckanext.dcor_schemas.plugin,
        'DISABLE_AFTER_DATASET_CREATE_FOR_CONCURRENT_JOB_TESTS',
        True)

    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    ds_dict = make_dataset(create_context, owner_org, activate=False)
    result = create_with_upload(
        b"", 'test.ini',
        url="upload",
        package_id=ds_dict["id"],
        context=create_context,
    )
    resource = helpers.call_action("resource_show", id=result["id"])
    assert dcor_shared.get_resource_path(result["id"]).exists()
    sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert resource["sha256"] == sha256
