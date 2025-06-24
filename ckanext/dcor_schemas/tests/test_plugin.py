import pathlib
from unittest import mock

import pytest

import ckan.logic as logic
import ckan.model as model
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers

from dcor_shared.testing import (
    get_ckan_config_option,
    make_dataset_via_s3,
    synchronous_enqueue_job
)

import requests

data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_ipermissionlabels_user_group_see_privates():
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

    ds_dict, _ = make_dataset_via_s3(
        create_context=context_a,
        owner_org=owner_org,
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
        ):
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

    ds_dict, _ = make_dataset_via_s3(
        create_context=context_a,
        owner_org=owner_org,
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


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
# We have to use synchronous_enqueue_job, because the background workers
# are running as www-data and cannot move files across the file system.
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_ipackagecontroller_after_dataset_update_make_private_public_on_s3(
        enqueue_job_mock,
        tmp_path):
    user = factories.User()
    user_obj = model.User.by_name(user["name"])
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False,
                      'auth_user_obj': user_obj,
                      'user': user['name'],
                      'api_version': 3}
    # Create a private dataset
    ds_dict, res_dict = make_dataset_via_s3(
        create_context=create_context,
        owner_org=owner_org,
        activate=True,
        resource_path=data_path / "calibration_beads_47.rtdc",
        private=True,
    )

    # make sure the dataset is private
    assert ds_dict["private"]

    rid = res_dict["id"]

    # make sure this worked
    res_dict = logic.get_action("resource_show")(
        context=create_context,
        data_dict={"id": rid}
    )
    assert res_dict["s3_available"]

    # attempt to download the resource, which should fail, since it is private
    response = requests.get(res_dict["s3_url"])
    assert not response.ok
    assert response.status_code == 403

    # make the dataset public
    logic.get_action("package_patch")(
        context=create_context,
        data_dict={"id": ds_dict["id"],
                   "private": False}
    )

    # attempt to download - this time it should work
    response = requests.get(res_dict["s3_url"])
    assert response.ok
    assert response.status_code == 200
