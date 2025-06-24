import pathlib
from unittest import mock
import uuid

import pytest

from ckan.cli.cli import ckan as ckan_cli
from ckan import logic, model
import ckan.tests.helpers as helpers
import ckan.tests.factories as factories

from dcor_shared.testing import (
    make_dataset_via_s3, synchronous_enqueue_job
)
from dcor_shared import s3, s3cc


data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas dc_serve dc_view')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_dcor_move_dataset_to_circle(enqueue_job_mock, cli):
    user = factories.User()
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

    new_owner_org = factories.Organization(
        users=[{
            'name': user["id"],
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

    # Also make sure that the condensed and preview resources were moved
    for name in ["condensed", "preview"]:
        other_key = resource_key.replace("resource", name)
        assert s3.object_exists(bucket_name=bucket_name_new,
                                object_name=other_key)
        assert not s3.object_exists(bucket_name=bucket_name_old,
                                    object_name=other_key)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
@pytest.mark.parametrize("activate", [True, False])
def test_list_group_resources(cli, activate):
    """Group resources include resources from draft and active datasets"""
    # create a dateset
    ds_dict, res_dict = make_dataset_via_s3(
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=activate)
    org_id = ds_dict['organization']['id']
    result = cli.invoke(ckan_cli, ["list-group-resources", org_id])
    assert result.output.strip().split()[-1] == res_dict["id"]


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
@pytest.mark.parametrize("activate", [True, False])
def test_list_group_resources_delete_purge(cli, activate):
    """ Group resources include resources from deleted (not pruned) datasets"""
    # create a dateset
    ds_dict, res_dict = make_dataset_via_s3(
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
def test_list_zombie_users_with_a_user_with_dataset(cli):
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    make_dataset_via_s3(
        create_context, owner_org,
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
    make_dataset_via_s3(
        create_context=context,
        owner_org=owner_org,
        activate=False)

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


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dcor_prune_draft_datasets(cli):
    ds_dict, res_dict = make_dataset_via_s3(
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=False,
        private=False,
        authors="Peter Pan")

    # Check whether the dataset exists
    assert helpers.call_action("package_show", id=ds_dict["id"])

    # Remove older draft datasets, will not remove the current one
    cli.invoke(ckan_cli,
               ["dcor-prune-draft-datasets",
                "--older-than-days", "1"])
    assert helpers.call_action("package_show", id=ds_dict["id"])

    # Dry run
    cli.invoke(ckan_cli,
               ["dcor-prune-draft-datasets",
                "--older-than-days", "-1",
                "--dry-run"
                ])
    assert helpers.call_action("package_show", id=ds_dict["id"])

    # Actual run
    cli.invoke(ckan_cli,
               ["dcor-prune-draft-datasets",
                "--older-than-days", "-1",
                ])
    with pytest.raises(logic.NotFound):
        helpers.call_action("package_show", id=ds_dict["id"])


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dcor_prune_orphaned_s3_artifacts(cli):
    ds_dict, res_dict = make_dataset_via_s3(
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True,
        private=False,
        authors="Peter Pan")

    rid = res_dict["id"]

    bucket_name, object_name = s3cc.get_s3_bucket_object_for_artifact(rid)

    # Check whether the S3 resource exists
    assert s3.object_exists(bucket_name, object_name)
    # Check that the organization exists
    org_list = logic.get_action("organization_list")()
    assert ds_dict["organization"]["name"] in org_list

    # Attempt to remove objects from S3, the object should still be there
    # afterward.
    cli.invoke(ckan_cli,
               ["dcor-prune-orphaned-s3-artifacts",
                "--older-than-days", "-1"])
    assert s3.object_exists(bucket_name, object_name)

    # Delete the entire dataset
    helpers.call_action(action_name="package_delete",
                        context={'ignore_auth': True, 'user': 'default'},
                        id=ds_dict["id"]
                        )
    helpers.call_action(action_name="dataset_purge",
                        context={'ignore_auth': True, 'user': 'default'},
                        id=ds_dict["id"]
                        )

    # Make sure that the S3 object is still there
    assert s3.object_exists(bucket_name, object_name)

    # Perform a cleanup that does not take into account the new data
    cli.invoke(ckan_cli,
               ["dcor-prune-orphaned-s3-artifacts",
                "--older-than-days", "1"])
    # Make sure that the S3 object is still there
    assert s3.object_exists(bucket_name, object_name)

    # Perform a dry run
    cli.invoke(ckan_cli,
               ["dcor-prune-orphaned-s3-artifacts",
                "--older-than-days", "-1",
                "--dry-run"
                ])
    assert s3.object_exists(bucket_name, object_name)

    # Perform the actual cleanup
    res = cli.invoke(ckan_cli,
                     ["dcor-prune-orphaned-s3-artifacts",
                      "--older-than-days", "-1",
                      ])
    print(res)
    print(rid)
    print(ds_dict["id"])
    assert not s3.object_exists(bucket_name, object_name)
