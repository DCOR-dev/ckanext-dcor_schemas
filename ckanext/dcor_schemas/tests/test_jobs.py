""" Testing background jobs

Due to the asynchronous nature of background jobs, code that uses them needs
to be handled specially when writing tests.

A common approach is to use the mock package to replace the
ckan.plugins.toolkit.enqueue_job function with a mock that executes jobs
synchronously instead of asynchronously
"""
import pathlib
from unittest import mock

import dclab
import numpy as np
import pytest

import ckan.tests.factories as factories
from ckan.tests import helpers

from dcor_shared.testing import (
    make_dataset_via_s3, make_resource_via_s3, synchronous_enqueue_job
)
from dcor_shared import sha256sum


data_dir = pathlib.Path(__file__).parent / "data"


def test_sha256sum(tmp_path):
    p = tmp_path / "test.txt"
    p.write_text("Sum this up!")
    ist = sha256sum(p)
    soll = "d00df55b97a60c78bbb137540e1b60647a5e6b216262a95ab96cafd4519bcf6a"
    assert ist == soll


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_check_dc_metadata(enqueue_job_mock):
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
    ds_dict, res_dict = make_dataset_via_s3(
        create_context=create_context,
        resource_path=data_dir / "calibration_beads_47.rtdc",
        owner_org=owner_org,
        activate=False)

    resource = helpers.call_action("resource_show", id=res_dict["id"])
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
    md5sum = "108d47e80f3e5f35110493b1fdcd30d5"
    assert resource["etag"] == md5sum


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_set_format_job(enqueue_job_mock, tmp_path):
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
    ds_dict = make_dataset_via_s3(
        create_context=create_context,
        owner_org=owner_org,
        activate=False)
    path = data_dir / "calibration_beads_47.rtdc"
    # create dataset without fluorescence
    path_ul = tmp_path / "calibratino_beads_nofl.rtdc"
    with dclab.new_dataset(path) as ds:
        ds.export.hdf5(path_ul, features=["deform", "bright_avg", "area_um"])

    rid = make_resource_via_s3(
        resource_path=path_ul,
        organization_id=owner_org['id'],
        dataset_id=ds_dict['id'],
    )
    resource = helpers.call_action("resource_show", id=rid)
    assert resource["format"] == "RT-DC"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_set_format_job_fl(enqueue_job_mock):
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    _, res_dict = make_dataset_via_s3(
        create_context=create_context,
        resource_path=data_dir / "calibration_beads_47.rtdc",
        owner_org=owner_org,
        activate=False)

    resource = helpers.call_action("resource_show", id=res_dict["id"])
    assert resource["format"] == "RT-FDC"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_set_sha256_job(enqueue_job_mock):
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    _, res_dict = make_dataset_via_s3(
        create_context=create_context,
        resource_path=data_dir / "calibration_beads_47.rtdc",
        owner_org=owner_org,
        activate=False)

    resource = helpers.call_action("resource_show", id=res_dict["id"])
    sha = "490efdf5d9bb4cd4b2a6bcf2fe54d4dc201c38530140bcb168980bf8bf846c73"
    assert resource["sha256"] == sha


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_set_sha256_job_empty_file(enqueue_job_mock, tmp_path):
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    ds_dict = make_dataset_via_s3(
        create_context=create_context,
        owner_org=owner_org,
        activate=False)

    path = tmp_path / "test.ini"
    path.touch()
    rid = make_resource_via_s3(
        resource_path=path,
        organization_id=owner_org['id'],
        dataset_id=ds_dict['id'],
    )
    resource = helpers.call_action("resource_show", id=rid)
    sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert resource["sha256"] == sha256
