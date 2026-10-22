import datetime
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

    res = cli.invoke(ckan_cli, ["dcor-move-dataset-to-circle",
                                ds_dict["id"],
                                new_owner_org["id"]
                                ])
    assert res.exit_code == 0

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
    assert result.exit_code == 0
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
    assert result.exit_code == 0
    assert result.output.strip().split()[-1] == res_dict["id"]
    assert res_dict["id"] in result.output.strip().split()  # same test

    # Purge the dataset
    helpers.call_action("dataset_purge", context, id=ds_dict["id"])
    # It should not be there anymore
    result2 = cli.invoke(ckan_cli, ["list-group-resources", org_id])
    assert result2.exit_code == 0
    assert res_dict["id"] not in result2.output.strip().split()


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_list_zombie_users_basic_clean_db(cli):
    result = cli.invoke(ckan_cli, ["list-zombie-users"])
    assert result.exit_code == 0
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
    assert result.exit_code == 0
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
    assert result.exit_code == 0
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
    assert result.exit_code == 0
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
    assert result.exit_code == 0
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
    res = cli.invoke(ckan_cli,
                     ["dcor-prune-draft-datasets",
                      "--older-than-days", "1"])
    print(res.output)
    assert res.exit_code == 0
    assert helpers.call_action("package_show", id=ds_dict["id"])

    # Dry run
    res = cli.invoke(ckan_cli,
                     ["dcor-prune-draft-datasets",
                      "--older-than-days", "-1",
                      "--dry-run"
                      ])
    assert res.exit_code == 0
    assert helpers.call_action("package_show", id=ds_dict["id"])

    # Actual run
    res = cli.invoke(ckan_cli,
                     ["dcor-prune-draft-datasets",
                      "--older-than-days", "-1",
                      ])
    assert res.exit_code == 0
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
    res = cli.invoke(ckan_cli,
                     ["dcor-prune-orphaned-s3-artifacts",
                      "--older-than-days", "-1"])
    assert res.exit_code == 0
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
    res = cli.invoke(ckan_cli,
                     ["dcor-prune-orphaned-s3-artifacts",
                      "--older-than-days", "1"])
    assert res.exit_code == 0
    # Make sure that the S3 object is still there
    assert s3.object_exists(bucket_name, object_name)

    # Perform a dry run
    res = cli.invoke(ckan_cli,
                     ["dcor-prune-orphaned-s3-artifacts",
                      "--older-than-days", "-1",
                      "--dry-run"
                      ])
    assert res.exit_code == 0
    assert s3.object_exists(bucket_name, object_name)

    # Perform the actual cleanup
    res = cli.invoke(ckan_cli,
                     ["dcor-prune-orphaned-s3-artifacts",
                      "--older-than-days", "-1",
                      ])
    assert res.exit_code == 0
    print(res)
    print(rid)
    print(ds_dict["id"])
    assert not s3.object_exists(bucket_name, object_name)


def set_last_active(user_name, days_ago):
    """Set the time of the last activity of a user"""
    user_obj = model.User.by_name(user_name)
    user_obj.last_active = (datetime.datetime.utcnow()
                            - datetime.timedelta(days=days_ago))
    model.Session.commit()


def user_state(user_name):
    return model.User.by_name(user_name).state


def make_purge_all_scenario():
    """Create users, datasets, collections, and circles for dcor-purge-all

    Returns a dictionary with all relevant objects.
    """
    # users
    user_active = factories.User()  # has datasets and was active recently
    user_inactive = factories.User()  # has datasets, not active recently
    user_no_data = factories.User()  # no datasets, but active recently
    admin = factories.Sysadmin()
    set_last_active(user_active["name"], days_ago=1)
    set_last_active(user_inactive["name"], days_ago=10)
    set_last_active(user_no_data["name"], days_ago=0)

    context_active = {'ignore_auth': False,
                      'user': user_active['name'],
                      'api_version': 3}
    context_inactive = {'ignore_auth': False,
                        'user': user_inactive['name'],
                        'api_version': 3}

    # circles
    circle_keep = factories.Organization(
        name=f"figshare-import-{uuid.uuid4()}",
        users=[{'name': user_inactive['id'], 'capacity': 'admin'}])
    circle_other = factories.Organization(
        users=[{'name': user_active['id'], 'capacity': 'admin'}])

    # datasets
    ds_keep, _ = make_dataset_via_s3(
        create_context=context_inactive,
        owner_org=circle_keep,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True,
        private=False)
    ds_other, _ = make_dataset_via_s3(
        create_context=context_active,
        owner_org=circle_other,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True)
    # without resource, only the dataset dictionary is returned
    ds_draft = make_dataset_via_s3(
        create_context=context_active,
        owner_org=circle_other,
        activate=False)

    # collection containing a dataset that is kept
    collection = factories.Group(
        users=[{'name': user_active['id'], 'capacity': 'admin'}])
    helpers.call_action("member_create",
                        context_active,
                        id=collection["id"],
                        object=ds_keep["id"],
                        object_type="package",
                        capacity="member",
                        )
    # empty collection
    collection_empty = factories.Group(
        users=[{'name': user_no_data['id'], 'capacity': 'admin'}])

    return {
        "user_active": user_active,
        "user_inactive": user_inactive,
        "user_no_data": user_no_data,
        "admin": admin,
        "circle_keep": circle_keep,
        "circle_other": circle_other,
        "ds_keep": ds_keep,
        "ds_other": ds_other,
        "ds_draft": ds_draft,
        "collection": collection,
        "collection_empty": collection_empty,
    }


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.ckan_config('ckanext.dcor_schemas.allow_purge_all', "true")
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dcor_purge_all(cli):
    sc = make_purge_all_scenario()

    res = cli.invoke(ckan_cli,
                     ["dcor-purge-all",
                      "--keep-circle", sc["circle_keep"]["name"],
                      "--yes"])
    print(res.output)
    assert res.exit_code == 0

    # users: only the admin and the recently active user with datasets
    assert user_state(sc["admin"]["name"]) == "active"
    assert user_state(sc["user_active"]["name"]) == "active"
    assert user_state(sc["user_inactive"]["name"]) == "deleted"
    assert user_state(sc["user_no_data"]["name"]) == "deleted"

    # datasets: only the dataset in the kept circle
    assert model.Package.get(sc["ds_keep"]["id"]) is not None
    assert model.Package.get(sc["ds_other"]["id"]) is None
    assert model.Package.get(sc["ds_draft"]["id"]) is None

    # collections: all purged (also the one with a kept dataset)
    assert model.Group.get(sc["collection"]["id"]) is None
    assert model.Group.get(sc["collection_empty"]["id"]) is None

    # circles: only the kept circle
    assert model.Group.get(sc["circle_keep"]["id"]) is not None
    assert model.Group.get(sc["circle_other"]["id"]) is None


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.ckan_config('ckanext.dcor_schemas.allow_purge_all', "true")
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dcor_purge_all_next_week(cli):
    """Users with datasets are removed when they become inactive"""
    sc = make_purge_all_scenario()
    res = cli.invoke(ckan_cli, ["dcor-purge-all", "--yes"])
    assert res.exit_code == 0
    # without a kept circle, all datasets are gone
    assert model.Package.get(sc["ds_keep"]["id"]) is None
    assert model.Group.get(sc["circle_keep"]["id"]) is None
    # The active user had datasets (when users were evaluated) and stays.
    assert user_state(sc["user_active"]["name"]) == "active"
    # In the next run, the active user does not have datasets anymore.
    res = cli.invoke(ckan_cli, ["dcor-purge-all", "--yes"])
    assert res.exit_code == 0
    assert user_state(sc["user_active"]["name"]) == "deleted"
    assert user_state(sc["admin"]["name"]) == "active"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.ckan_config('ckanext.dcor_schemas.allow_purge_all', "true")
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
@pytest.mark.parametrize("args,user_input", [
    [["--dry-run", "--yes"], None],  # dry run
    [[], "n\n"],  # user does not confirm
])
def test_dcor_purge_all_nothing_removed(cli, args, user_input):
    sc = make_purge_all_scenario()
    res = cli.invoke(ckan_cli, ["dcor-purge-all"] + args, input=user_input)
    print(res.output)
    for key in ["user_active", "user_inactive", "user_no_data", "admin"]:
        assert user_state(sc[key]["name"]) == "active"
    for key in ["ds_keep", "ds_other", "ds_draft"]:
        assert model.Package.get(sc[key]["id"]) is not None
    for key in ["circle_keep", "circle_other", "collection",
                "collection_empty"]:
        assert model.Group.get(sc[key]["id"]) is not None


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dcor_purge_all_not_allowed(cli):
    """By default, dcor-purge-all must not do anything"""
    sc = make_purge_all_scenario()
    res = cli.invoke(ckan_cli, ["dcor-purge-all", "--yes"])
    assert res.exit_code != 0
    assert "not allowed" in res.output
    assert user_state(sc["user_no_data"]["name"]) == "active"
    assert model.Package.get(sc["ds_other"]["id"]) is not None
    assert model.Group.get(sc["circle_other"]["id"]) is not None


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.ckan_config('ckanext.dcor_schemas.allow_purge_all', "true")
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dcor_purge_all_dataset_added_during_purge(cli):
    """A dataset created while purging must not prevent purging its circle

    This simulates e.g. a test suite that creates datasets on a
    development instance while `dcor-purge-all` is running.
    """
    sc = make_purge_all_scenario()
    context_active = {'ignore_auth': False,
                      'user': sc["user_active"]['name'],
                      'api_version': 3}
    created = []
    get_action_orig = logic.get_action

    def get_action(name):
        action = get_action_orig(name)
        if name != "dataset_purge":
            return action

        def dataset_purge(context, data_dict):
            result = action(context, data_dict)
            if not created:
                # Create a new dataset in a circle that is about to be
                # purged, after the list of datasets to purge was compiled.
                created.append(make_dataset_via_s3(
                    create_context=context_active,
                    owner_org=sc["circle_other"],
                    activate=False))
            return result
        return dataset_purge

    with mock.patch("ckanext.dcor_schemas.cli.logic.get_action",
                    side_effect=get_action):
        res = cli.invoke(ckan_cli,
                         ["dcor-purge-all",
                          "--keep-circle", sc["circle_keep"]["name"],
                          "--yes"])
    print(res.output)
    assert created, "sanity check: the dataset was created during purging"
    assert res.exit_code == 0
    assert model.Package.get(created[0]["id"]) is None
    assert model.Group.get(sc["circle_other"]["id"]) is None
    assert model.Package.get(sc["ds_keep"]["id"]) is not None


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.ckan_config('ckanext.dcor_schemas.allow_purge_all', "true")
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dcor_purge_all_continue_on_error(cli):
    """If one item cannot be purged, continue and exit with an error"""
    sc = make_purge_all_scenario()
    get_action_orig = logic.get_action

    def get_action(name):
        action = get_action_orig(name)
        if name != "group_purge":
            return action

        def group_purge(context, data_dict):
            if data_dict["id"] == sc["collection"]["id"]:
                raise logic.ValidationError({"message": "simulated error"})
            return action(context, data_dict)
        return group_purge

    with mock.patch("ckanext.dcor_schemas.cli.logic.get_action",
                    side_effect=get_action):
        res = cli.invoke(ckan_cli,
                         ["dcor-purge-all",
                          "--keep-circle", sc["circle_keep"]["name"],
                          "--yes"])
    print(res.output)
    assert res.exit_code == 1
    assert "Encountered 1 errors" in res.output
    assert "simulated error" in res.output
    assert f"purge collection {sc['collection']['id']}" in res.output
    # the collection that failed is still there
    assert model.Group.get(sc["collection"]["id"]) is not None
    # everything else was purged nevertheless
    assert model.Group.get(sc["collection_empty"]["id"]) is None
    assert model.Group.get(sc["circle_other"]["id"]) is None
    assert model.Package.get(sc["ds_other"]["id"]) is None
    assert user_state(sc["user_no_data"]["name"]) == "deleted"
