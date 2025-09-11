import pathlib
import uuid

import pytest

import ckan.logic as logic
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers

from dcor_shared.testing import make_dataset_via_s3

data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_group_delete():
    """Make sure users can delete their groups"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # create a datasets
    create_context1 = {'ignore_auth': False,
                       'user': user['name'],
                       'api_version': 3}
    ds_dict_1, _ = make_dataset_via_s3(
        create_context=create_context1,
        owner_org=owner_org,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True)

    # create group for this user
    group_dict = helpers.call_action(
        "group_create",
        name=f"deleteme-{uuid.uuid4()}",
        title="This is a group that will be deleted",
        packages=[ds_dict_1],
        context=create_context1,
        )

    test_context = {'ignore_auth': False,
                    'user': user['name'],
                    'api_version': 3}

    helpers.call_auth("group_delete",
                      test_context,
                      id=group_dict["id"])


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_group_no_delete_from_other_users():
    """Make sure users cannot delete groups of other users"""
    user1 = factories.User()
    user2 = factories.User()
    owner_org = factories.Organization(users=[
        {'name': user1['id'], 'capacity': 'admin'},
        {'name': user2['id'], 'capacity': 'admin'}
    ])

    # create a datasets
    create_context1 = {'ignore_auth': False,
                       'user': user1['name'],
                       'api_version': 3}
    ds_dict_1, _ = make_dataset_via_s3(
        create_context=create_context1,
        owner_org=owner_org,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True)

    # create group for this user
    group_dict = helpers.call_action(
        "group_create",
        name=f"deleteme-{uuid.uuid4()}",
        title="This is a group that can only be deleted by its owner",
        packages=[ds_dict_1],
        context=create_context1,
        )

    test_context2 = {'ignore_auth': False,
                     'user': user2['name'],
                     'api_version': 3}

    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("group_delete",
                          test_context2,
                          id=group_dict["id"])


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_group_no_delete_from_other_users_even_if_member():
    """Make sure users cannot delete groups they are a "Member" of"""
    user1 = factories.User()
    user2 = factories.User()
    owner_org = factories.Organization(users=[
        {'name': user1['id'], 'capacity': 'admin'},
        {'name': user2['id'], 'capacity': 'admin'}
    ])

    # create a datasets
    create_context1 = {'ignore_auth': False,
                       'user': user1['name'],
                       'api_version': 3}
    ds_dict_1, _ = make_dataset_via_s3(
        create_context=create_context1,
        owner_org=owner_org,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True)

    # create group for this user
    group_dict = helpers.call_action(
        "group_create",
        name=f"deleteme-{uuid.uuid4()}",
        title="This is a group that can only be deleted by its owner",
        packages=[ds_dict_1],
        users=[{"name": user2['name']}],
        context=create_context1,
        )

    test_context2 = {'ignore_auth': False,
                     'user': user2['name'],
                     'api_version': 3}

    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("group_delete",
                          test_context2,
                          id=group_dict["id"])
