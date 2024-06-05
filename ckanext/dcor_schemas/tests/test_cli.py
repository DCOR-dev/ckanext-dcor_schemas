import pathlib
from unittest import mock
import uuid

import pytest

from ckan.cli.cli import ckan as ckan_cli
from ckan import model
import ckan.tests.helpers as helpers
import ckan.tests.factories as factories
import ckan.lib.uploader

from dcor_shared.testing import (
    make_dataset, make_dataset_via_s3, synchronous_enqueue_job
)
from dcor_shared import s3, s3cc


data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins',
                         'dcor_depot dcor_schemas dc_serve dc_view')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
# We have to use synchronous_enqueue_job, because the background workers
# are running as www-data and cannot move files across the file system.
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_dcor_move_dataset_to_circle(
        enqueue_job_mock, cli, monkeypatch, tmpdir, ckan_config):
    monkeypatch.setitem(ckan_config, 'ckan.storage_path', str(tmpdir))
    monkeypatch.setattr(ckan.lib.uploader,
                        'get_storage_path',
                        lambda: str(tmpdir))

    user = factories.UserWithToken()
    user_obj = ckan.model.User.by_name(user["name"])
    monkeypatch.setattr(ckan.common,
                        'current_user',
                        user_obj)
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False,
                      'user': user['name'],
                      'api_version': 3}

    ds_dict, rs_dict = make_dataset_via_s3(
        create_context=create_context,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True,
    )

    bucket_name_old, resource_key = s3cc.get_s3_bucket_object_for_artifact(
        resource_id=rs_dict["id"],
        artifact="resource"
    )

    new_owner_org = factories.Organization(users=[{
        'name': ds_dict["creator_user_id"],
        'capacity': 'admin'
    }])

    bucket_name_new = bucket_name_old.replace(ds_dict["owner_org"],
                                              new_owner_org["id"])

    cli.invoke(ckan_cli, ["dcor-move-dataset-to-circle",
                          ds_dict["id"],
                          new_owner_org["id"]
                          ])

    context = {'ignore_auth': False,
               'user': ds_dict["creator_user_id"],
               'api_version': 3}

    ds_dict2 = helpers.call_action("package_show", context, id=ds_dict["id"])
    assert ds_dict2["owner_org"] != ds_dict["owner_org"]
    assert ds_dict2["owner_org"] == new_owner_org["id"]
    assert ds_dict2["resources"][0]["s3_url"].count(new_owner_org["id"])

    assert s3.object_exists(bucket_name=bucket_name_new,
                            object_name=resource_key)
    assert not s3.object_exists(bucket_name=bucket_name_old,
                                object_name=resource_key)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
@pytest.mark.parametrize("activate", [True, False])
def test_list_group_resources(create_with_upload, cli, activate):
    """Group resources include resources from draft and active datasets"""
    # create a dateset
    ds_dict, res_dict = make_dataset(
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=activate)
    org_id = ds_dict['organization']['id']
    result = cli.invoke(ckan_cli, ["list-group-resources", org_id])
    assert result.output.strip().split()[-1] == res_dict["id"]


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
@pytest.mark.parametrize("activate", [True, False])
def test_list_group_resources_delete_purge(create_with_upload, cli, activate):
    """ Group resources include resources from deleted (not pruned) datasets"""
    # create a dateset
    ds_dict, res_dict = make_dataset(
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=activate)
    org_id = ds_dict['organization']['id']

    admin = factories.Sysadmin()
    context = {'ignore_auth': True,
               'user': admin['name'],
               'api_version': 3}

    # Delete the dataset
    helpers.call_action("package_delete", context, id=ds_dict["id"])
    # It should still be listed
    result = cli.invoke(ckan_cli, ["list-group-resources", org_id])
    assert result.output.strip().split()[-1] == res_dict["id"]
    assert res_dict["id"] in result.output.strip().split()  # same test

    # Purge the dataset
    helpers.call_action("dataset_purge", context, id=ds_dict["id"])
    # It should not be there anymore
    result2 = cli.invoke(ckan_cli, ["list-group-resources", org_id])
    assert res_dict["id"] not in result2.output.strip().split()


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_list_zombie_users_basic_clean_db(cli):
    result = cli.invoke(ckan_cli, ["list-zombie-users"])
    for line in result.output.split("\n"):
        if not line.strip():
            continue
        elif line.count("INFO"):
            continue
        elif line.count("WARNI"):
            continue
        else:
            assert False, f"clean_db -> no users -> no output, got '{line}'"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_list_zombie_users_with_a_user(cli):
    factories.User(name=f"test_user_{uuid.uuid4()}")
    result = cli.invoke(ckan_cli,
                        ["list-zombie-users", "--last-activity-weeks", "0"])
    print(result)  # for debugging
    for line in result.output.split("\n"):
        if not line.strip():
            continue
        elif line.count("INFO"):
            continue
        elif line.count("WARNI"):
            continue
        elif line.count("test_user_"):
            break
        else:
            print(f"Encountered line {line}")
    else:
        assert False, "test_user should have been found"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_list_zombie_users_with_a_user_with_dataset(cli, create_with_upload):
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    make_dataset(
        create_context, owner_org,
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True)

    result = cli.invoke(ckan_cli,
                        ["list-zombie-users", "--last-activity-weeks", "0"])
    for line in result.output.split("\n"):
        if not line.strip():
            continue
        elif line.count("INFO"):
            continue
        elif line.count("WARNI"):
            continue
        else:
            assert False, "user with dataset should have been ignored"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_list_zombie_users_with_active_user(cli):
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    context = {'ignore_auth': False,
               'user': user['name'], 'model': model, 'api_version': 3}
    # create recent activity
    make_dataset(context, owner_org, activate=False)

    result = cli.invoke(ckan_cli,
                        ["list-zombie-users", "--last-activity-weeks", "12"])
    for line in result.output.split("\n"):
        if not line.strip():
            continue
        elif line.count("INFO"):
            continue
        elif line.count("WARNI"):
            continue
        else:
            assert False, f"active user should have been ignored, got '{line}'"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_list_zombie_users_with_admin(cli):
    factories.Sysadmin()
    result = cli.invoke(ckan_cli,
                        ["list-zombie-users", "--last-activity-weeks", "0"])
    for line in result.output.split("\n"):
        if not line.strip():
            continue
        elif line.count("INFO"):
            continue
        elif line.count("WARNI"):
            continue
        else:
            assert False, "sysadmin should have been ignored"
