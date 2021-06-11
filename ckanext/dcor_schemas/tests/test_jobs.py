""" Testing background jobs

Due to the asynchronous nature of background jobs, code that uses them needs
to be handled specially when writing tests.

A common approach is to use the mock package to replace the
ckan.plugins.toolkit.enqueue_job function with a mock that executes jobs
synchronously instead of asynchronously
"""
import mock
import pathlib

import dclab
import numpy as np
import pytest

import ckan.lib
import ckan.tests.factories as factories
from ckan.tests import helpers

import dcor_shared

from .helper_methods import make_dataset


data_dir = pathlib.Path(__file__).parent / "data"


def synchronous_enqueue_job(job_func, args=None, kwargs=None, title=None,
                            queue=None, rq_kwargs={}):
    """
    Synchronous mock for ``ckan.plugins.toolkit.enqueue_job``.
    """
    args = args or []
    kwargs = kwargs or {}
    job_func(*args, **kwargs)


# We need the dcor_depot extension to make sure that the symbolic-
# linking pipeline is used.
@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas dcor_depot')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_set_dc_config_job_fl(enqueue_job_mock, create_with_upload,
                              monkeypatch, ckan_config, tmpdir):
    monkeypatch.setitem(ckan_config, 'ckan.storage_path', str(tmpdir))
    monkeypatch.setattr(ckan.lib.uploader, '_storage_path', str(tmpdir))

    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False, 'user': user['name']}
    dataset = make_dataset(create_context, owner_org, with_resource=False,
                           activate=False)
    content = (data_dir / "calibration_beads_47.rtdc").read_bytes()
    result = create_with_upload(
        content, 'test.rtdc',
        url="upload",
        package_id=dataset["id"],
        context=create_context,
    )
    resource = helpers.call_action("resource_show", id=result["id"])
    assert dcor_shared.get_resource_path(result["id"]).exists()
    assert resource["dc:experiment:date"] == "2018-12-11"
    assert resource["dc:experiment:event count"] == 47
    assert np.allclose(resource["dc:setup:flow rate"], 0.06)


# We need the dcor_depot extension to make sure that the symbolic-
# linking pipeline is used.
@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas dcor_depot')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_set_format_job(enqueue_job_mock, create_with_upload, monkeypatch,
                        ckan_config, tmpdir):
    monkeypatch.setitem(ckan_config, 'ckan.storage_path', str(tmpdir))
    monkeypatch.setattr(ckan.lib.uploader, '_storage_path', str(tmpdir))

    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False, 'user': user['name']}
    dataset = make_dataset(create_context, owner_org, with_resource=False,
                           activate=False)
    path = data_dir / "calibration_beads_47.rtdc"
    # create dataset without fluorescence
    tmppath = pathlib.Path(tmpdir) / "calibratino_beads_nofl.rtdc"
    with dclab.new_dataset(path) as ds:
        ds.export.hdf5(tmppath, features=["deform", "bright_avg", "area_um"])
    content = tmppath.read_bytes()
    result = create_with_upload(
        content, 'test.rtdc',
        url="upload",
        package_id=dataset["id"],
        context=create_context,
    )
    resource = helpers.call_action("resource_show", id=result["id"])
    assert dcor_shared.get_resource_path(result["id"]).exists()
    assert resource["format"] == "RT-DC"


# We need the dcor_depot extension to make sure that the symbolic-
# linking pipeline is used.
@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas dcor_depot')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_set_format_job_fl(enqueue_job_mock, create_with_upload, monkeypatch,
                           ckan_config, tmpdir):
    monkeypatch.setitem(ckan_config, 'ckan.storage_path', str(tmpdir))
    monkeypatch.setattr(ckan.lib.uploader, '_storage_path', str(tmpdir))

    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False, 'user': user['name']}
    dataset = make_dataset(create_context, owner_org, with_resource=False,
                           activate=False)
    content = (data_dir / "calibration_beads_47.rtdc").read_bytes()
    result = create_with_upload(
        content, 'test.rtdc',
        url="upload",
        package_id=dataset["id"],
        context=create_context,
    )
    resource = helpers.call_action("resource_show", id=result["id"])
    assert dcor_shared.get_resource_path(result["id"]).exists()
    assert resource["format"] == "RT-FDC"


# We need the dcor_depot extension to make sure that the symbolic-
# linking pipeline is used.
@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas dcor_depot')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_set_sha256_job(enqueue_job_mock, create_with_upload, monkeypatch,
                        ckan_config, tmpdir):
    monkeypatch.setitem(ckan_config, 'ckan.storage_path', str(tmpdir))
    monkeypatch.setattr(ckan.lib.uploader, '_storage_path', str(tmpdir))

    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False, 'user': user['name']}
    dataset = make_dataset(create_context, owner_org, with_resource=False,
                           activate=False)
    content = (data_dir / "calibration_beads_47.rtdc").read_bytes()
    result = create_with_upload(
        content, 'test.rtdc',
        url="upload",
        package_id=dataset["id"],
        context=create_context,
    )
    resource = helpers.call_action("resource_show", id=result["id"])
    assert dcor_shared.get_resource_path(result["id"]).exists()
    sha = "490efdf5d9bb4cd4b2a6bcf2fe54d4dc201c38530140bcb168980bf8bf846c73"
    assert resource["sha256"] == sha


# We need the dcor_depot extension to make sure that the symbolic-
# linking pipeline is used.
@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas dcor_depot')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_set_sha256_job_empty_file(enqueue_job_mock, create_with_upload,
                                   monkeypatch, ckan_config, tmpdir):
    monkeypatch.setitem(ckan_config, 'ckan.storage_path', str(tmpdir))
    monkeypatch.setattr(ckan.lib.uploader, '_storage_path', str(tmpdir))

    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False, 'user': user['name']}
    dataset = make_dataset(create_context, owner_org, with_resource=False,
                           activate=False)
    result = create_with_upload(
        b"", 'test.ini',
        url="upload",
        package_id=dataset["id"],
        context=create_context,
    )
    resource = helpers.call_action("resource_show", id=result["id"])
    assert dcor_shared.get_resource_path(result["id"]).exists()
    sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert resource["sha256"] == sha256
