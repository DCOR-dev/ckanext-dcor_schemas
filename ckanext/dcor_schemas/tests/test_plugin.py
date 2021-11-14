import pytest

import ckan.logic as logic
import ckan.model as model
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers

from .helper_methods import make_dataset


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

    dataset, _ = make_dataset(context_a, owner_org,
                              create_with_upload=create_with_upload,
                              activate=True,
                              groups=[{"id": owner_group["id"]}],
                              private=True)

    success = helpers.call_auth("package_show", context_b,
                                id=dataset["id"]
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

    dataset, _ = make_dataset(context_a, owner_org,
                              create_with_upload=create_with_upload,
                              activate=True,
                              groups=[{"id": owner_group["id"]}],
                              private=True)

    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_show", context_b,
                          id=dataset["id"]
                          )
