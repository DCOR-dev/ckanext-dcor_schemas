import pytest

from ckan import logic
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers
from ckan import model


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_auth_group_show_list_users():
    """Anonymous user not allowed to list group with users"""
    user = factories.User()
    group = factories.Group(user=user)
    admin = factories.Sysadmin()
    # valid user
    assert helpers.call_auth(
        "group_show",
        context={'ignore_auth': False,
                 'user': user['name'],
                 'model': model,
                 'api_version': 3},
        id=group["name"],
        include_users=True,
    )
    # anonymous user
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth(
            "group_show",
            context={'ignore_auth': False,
                     'user': None,
                     'model': model,
                     'api_version': 3},
            id=group["name"],
            include_users=True,
        )
    # admin
    assert helpers.call_auth(
        "group_show",
        context={'ignore_auth': False,
                 'user': admin['name'],
                 'model': model,
                 'api_version': 3},
        id=group["name"],
        include_users=True,
    )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_auth_user_show():
    """Anonymous user not allowed to list users"""
    user = factories.User()
    user2 = factories.User()
    admin = factories.Sysadmin()
    # valid user
    assert helpers.call_auth(
        "user_show",
        context={'ignore_auth': False,
                 'user': user['name'],
                 'model': model,
                 'api_version': 3},
        id=user["name"])
    # other user
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth(
            "user_show",
            context={'ignore_auth': False,
                     'user': user2['name'],
                     'model': model,
                     'api_version': 3},
            id=user["name"])
    # anonymous user
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth(
            "user_show",
            context={'ignore_auth': False,
                     'user': None,
                     'model': model,
                     'api_version': 3},
            id=user["name"])
    # admin
    assert helpers.call_auth(
        "user_show",
        context={'ignore_auth': False,
                 'user': admin['name'],
                 'model': model,
                 'api_version': 3},
        id=user["name"])


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_auth_user_list():
    """Nobody is allowed to list users except admins"""
    user = factories.User()
    admin = factories.Sysadmin()
    # valid user
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth(
            "user_list",
            context={'ignore_auth': False,
                     'user': user['name'],
                     'model': model,
                     'api_version': 3},
        )
    # anonymous user
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth(
            "user_list",
            context={'ignore_auth': False,
                     'user': None,
                     'model': model,
                     'api_version': 3},
            )
    # admin
    assert helpers.call_auth(
        "user_list",
        context={'ignore_auth': False,
                 'user': admin['name'],
                 'model': model,
                 'api_version': 3},
        )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_login_user_create_datasets():
    """allow all logged-in users to create datasets"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    context = {'ignore_auth': False,
               'user': user['name'], 'model': model, 'api_version': 3}
    success = helpers.call_auth("package_create", context,
                                title="test-group",
                                authors="Peter Pan",
                                license_id="CC-BY-4.0",
                                owner_org=owner_org["id"],
                                )
    assert success


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_login_user_create_circles():
    """allow all logged-in users to create circles"""
    user = factories.User()
    context = {'ignore_auth': False,
               'user': user['name'], 'model': model, 'api_version': 3}
    success = helpers.call_auth("organization_create", context,
                                name="test-org")
    assert success


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_login_user_create_collections():
    """allow all logged-in users to create collections"""
    user = factories.User()
    context = {'ignore_auth': False,
               'user': user['name'], 'model': model, 'api_version': 3}
    success = helpers.call_auth("group_create", context, name="test-group")
    assert success
