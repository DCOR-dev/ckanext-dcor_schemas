import pytest

from ckan import logic
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_action_resource_schema_supplements():
    """Just a general test, may fail if rss changes"""
    rss = helpers.call_action("resource_schema_supplements")
    for sec in ["general", "cells", "artificial"]:
        assert sec in rss
    assert len(rss["general"]["requires"]) == 0
    assert rss["general"]["items"][0]["key"] == "sample type"
    assert rss["general"]["items"][0]["type"] == "string"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_action_supported_resource_suffixes():
    """Just a general test, may fail if rss changes"""
    suffixes = helpers.call_action("supported_resource_suffixes")
    assert ".rtdc" in suffixes
    assert ".docx" not in suffixes, "please don't remove this assertion!"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_action_group_list_for_user():
    user = factories.User()
    other = factories.User()
    col_member = factories.Group(
        name="col-member",
        users=[{'name': other['id'], 'capacity': 'admin'},
               {'name': user['id'], 'capacity': 'member'}])
    col_editor = factories.Group(
        name="col-editor",
        users=[{'name': other['id'], 'capacity': 'admin'},
               {'name': user['id'], 'capacity': 'editor'}])
    col_admin = factories.Group(
        name="col-admin",
        users=[{'name': user['id'], 'capacity': 'admin'}])
    # not a member
    factories.Group(name="col-other",
                    users=[{'name': other['id'], 'capacity': 'admin'}])
    # deleted collection
    col_deleted = factories.Group(
        name="col-deleted",
        users=[{'name': user['id'], 'capacity': 'admin'}])
    helpers.call_action("group_delete",
                        {'ignore_auth': True, 'user': user['name']},
                        id=col_deleted["id"])
    # circles are not collections
    factories.Organization(name="circle-member",
                           users=[{'name': user['id'], 'capacity': 'member'}])

    context = {'ignore_auth': False, 'user': user['name']}
    groups = helpers.call_action("dcor_group_list_for_user", context)
    names = [g["name"] for g in groups]
    assert names == ["col-admin", "col-editor", "col-member"]
    assert {g["id"] for g in groups} == {
        col_member["id"], col_editor["id"], col_admin["id"]}
    for g in groups:
        assert not g["is_organization"]

    # CKAN's group_list_authz does not list the "member" collection
    authz_names = [g["name"] for g in helpers.call_action(
        "group_list_authz", context)]
    assert "col-member" not in authz_names


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_action_group_list_for_user_auth():
    user = factories.User()
    other = factories.User()
    admin = factories.Sysadmin()
    factories.Group(name="col-other",
                    users=[{'name': other['id'], 'capacity': 'member'}])

    # anonymous users are not allowed
    with pytest.raises(logic.NotAuthorized):
        helpers.call_action("dcor_group_list_for_user",
                            {'ignore_auth': False, 'user': ''})

    # users may list their own collections by name or ID
    for ref in [user["name"], user["id"]]:
        assert helpers.call_action(
            "dcor_group_list_for_user",
            {'ignore_auth': False, 'user': user['name']},
            id=ref) == []

    # but not the collections of other users
    with pytest.raises(logic.NotAuthorized):
        helpers.call_action("dcor_group_list_for_user",
                            {'ignore_auth': False, 'user': user['name']},
                            id=other["name"])

    # sysadmins may list the collections of other users
    groups = helpers.call_action("dcor_group_list_for_user",
                                 {'ignore_auth': False,
                                  'user': admin['name']},
                                 id=other["name"])
    assert [g["name"] for g in groups] == ["col-other"]

    # unknown users
    with pytest.raises(logic.NotFound):
        helpers.call_action("dcor_group_list_for_user",
                            {'ignore_auth': False, 'user': admin['name']},
                            id="does-not-exist")
