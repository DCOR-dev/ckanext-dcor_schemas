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
def test_group_dataset_create():
    """Only admins and editors of a group are allowed to add datasets"""
    user1 = factories.User()
    user2 = factories.User()
    user3 = factories.User()
    user4 = factories.User()
    owner_org = factories.Organization(users=[
        {'name': user1['id'], 'capacity': 'editor'},
        {'name': user2['id'], 'capacity': 'member'},
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

    # create group for user1
    group_dict = helpers.call_action(
        "group_create",
        name=f"test_group-{uuid.uuid4()}",
        title="Tests for group permissions",
        packages=[ds_dict_1],
        context=create_context1,
        )

    # add users 2 and 3 to the group in different capacities
    for user, capacity in [
        [user2, "editor"],
        [user3, "member"],
    ]:
        helpers.call_action("member_create",
                            id=group_dict["id"],
                            object=user["id"],
                            object_type='user',
                            capacity=capacity)

    # admin and editor of the group should be able to create a dataset
    for user in [user1, user2]:
        helpers.call_auth("member_create",
                          {'ignore_auth': False,
                           'user': user['name'],
                           'api_version': 3},
                          object_type="package",
                          id=group_dict["id"])

        # This must also be reflected in group_list_authz
        groups = helpers.call_action("group_list_authz")
        assert len(groups) == 1
        assert groups[0]["id"] == group_dict["id"]

    # A member, random user, or anon may not add dataset
    for user in [user3, user4, {"name": None}]:
        with pytest.raises(logic.NotAuthorized):
            helpers.call_auth("member_create",
                              {'ignore_auth': False,
                               'user': user['name'],
                               'api_version': 3},
                              object_type="package",
                              id=group_dict["id"])

        # This must also be reflected in group_list_authz
        groups = helpers.call_action("group_list_authz")
        assert len(groups) == 0


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


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.ckan_config('ckanext.dcor_schemas.allow_content_listing_for_anon',
                         'false')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_group_show_by_user():
    """
    Only members of a group are allowed to show it
    """
    user1 = factories.User()
    user2 = factories.User()
    user3 = factories.User()
    user4 = factories.User()
    owner_org = factories.Organization(users=[
        {'name': user1['id'], 'capacity': 'editor'},
        {'name': user2['id'], 'capacity': 'member'},
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

    # create group for user1
    group_dict = helpers.call_action(
        "group_create",
        name=f"test_group-{uuid.uuid4()}",
        title="Tests for group permissions",
        packages=[ds_dict_1],
        context=create_context1,
        )

    # add users 2 and 3 to the group in different capacities
    for user, capacity in [
        [user2, "editor"],
        [user3, "member"],
    ]:
        helpers.call_action("member_create",
                            id=group_dict["id"],
                            object=user["id"],
                            object_type='user',
                            capacity=capacity)

    # The admin, editor, and member should be able to view the group
    for user in [user1, user2, user3]:
        helpers.call_auth("group_show",
                          {'ignore_auth': False,
                           'user': user['name'],
                           'api_version': 3},
                          id=group_dict["id"])

    # A random user is allowed to view it. But we need this
    # functionality so that users can list all groups!
    helpers.call_auth("group_show",
                      {'ignore_auth': False,
                       'user': user4['name'],
                       'api_version': 3},
                      id=group_dict["id"])

    # An anonymous user is also not allowed
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("group_show",
                          {'ignore_auth': False,
                           'user': None,
                           'api_version': 3},
                          id=group_dict["id"])


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_group_user_add():
    """Only admins of a group are allowed to add users to it"""
    user1 = factories.User()
    user2 = factories.User()
    user3 = factories.User()
    user4 = factories.User()
    owner_org = factories.Organization(users=[
        {'name': user1['id'], 'capacity': 'editor'},
        {'name': user2['id'], 'capacity': 'member'},
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

    # create group for user1
    group_dict = helpers.call_action(
        "group_create",
        name=f"test_group-{uuid.uuid4()}",
        title="Tests for group permissions",
        packages=[ds_dict_1],
        context=create_context1,
        )

    # add users 2 and 3 to the group in different capacities
    for user, capacity in [
        [user2, "editor"],
        [user3, "member"],
    ]:
        helpers.call_action("member_create",
                            id=group_dict["id"],
                            object=user["id"],
                            object_type='user',
                            capacity=capacity)

    # The admin of the group should be able to add a user
    helpers.call_auth("member_create",
                      {'ignore_auth': False,
                       'user': user1['name'],
                       'api_version': 3},
                      object_type="user",
                      id=group_dict["id"])

    # An editor of a group should not be able to add a user
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("member_create",
                          {'ignore_auth': False,
                           'user': user2['name'],
                           'api_version': 3},
                          object_type="user",
                          id=group_dict["id"])

    # A simple member of a group is not allowed to add another member
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("member_create",
                          {'ignore_auth': False,
                           'user': user3['name'],
                           'api_version': 3},
                          object_type="user",
                          id=group_dict["id"])

    # A random user is not allowed to add another member
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("member_create",
                          {'ignore_auth': False,
                           'user': user4['name'],
                           'api_version': 3},
                          object_type="user",
                          id=group_dict["id"])

    # An anonymous user is also not allowed
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("member_create",
                          {'ignore_auth': False,
                           'user': None,
                           'api_version': 3},
                          object_type="package",
                          id=group_dict["id"])
