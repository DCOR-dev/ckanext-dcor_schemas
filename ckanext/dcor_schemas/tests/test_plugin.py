import pathlib
from unittest import mock

import pytest

import ckan.logic as logic
import ckan.model as model
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers

from dcor_shared.testing import (
    get_ckan_config_option, make_dataset, make_dataset_via_s3,
    synchronous_enqueue_job
)


data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_ipermissionlabels_user_group_see_privates(create_with_upload):
    """
    Allow a user A to see user B's private dataset if the private dataset
    is in a group that user A is a member of.
    """
    user_a = factories.User()
    user_b = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user_a['id'],
        'capacity': 'admin'
    }])
    owner_group = factories.Group(users=[
        {'name': user_a['id'], 'capacity': 'admin'},
        {'name': user_b['id'], 'capacity': 'member'},
    ])
    context_a = {'ignore_auth': False,
                 'user': user_a['name'], 'model': model, 'api_version': 3}
    context_b = {'ignore_auth': False,
                 'user': user_b['name'], 'model': model, 'api_version': 3}

    ds_dict, _ = make_dataset(
        context_a, owner_org,
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True,
        groups=[{"id": owner_group["id"]}],
        private=True)

    success = helpers.call_auth("package_show", context_b,
                                id=ds_dict["id"]
                                )
    assert success


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_ipermissionlabels_user_group_see_privates_inverted(
        create_with_upload):
    """User is not allowed to see another user's private datasets"""
    user_a = factories.User()
    user_b = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user_a['id'],
        'capacity': 'admin'
    }])
    owner_group = factories.Group(users=[
        {'name': user_a['id'], 'capacity': 'admin'},
    ])
    context_a = {'ignore_auth': False,
                 'user': user_a['name'], 'model': model, 'api_version': 3}
    context_b = {'ignore_auth': False,
                 'user': user_b['name'], 'model': model, 'api_version': 3}

    ds_dict, _ = make_dataset(
        context_a, owner_org,
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True,
        groups=[{"id": owner_group["id"]}],
        private=True)

    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_show", context_b,
                          id=ds_dict["id"]
                          )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_iresourcecontroller_after_resource_create_properties(
        enqueue_job_mock):
    ds_dict, res_dict = make_dataset_via_s3(
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True,
        private=True)
    site_url = get_ckan_config_option("ckan.site_url")
    assert res_dict["mimetype"] == "RT-DC"
    assert res_dict["url"] == (f"{site_url}"
                               f"/dataset/{ds_dict['id']}"
                               f"/resource/{res_dict['id']}"
                               f"/download/{res_dict['name'].lower()}")
    assert res_dict["size"] == 904729
    assert res_dict["last_modified"]
    assert res_dict["s3_available"]
    assert res_dict["s3_url"]
    assert res_dict["format"] == "RT-FDC"
