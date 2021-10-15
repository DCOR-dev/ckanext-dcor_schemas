import cgi
import pathlib

import pytest

import ckan.logic as logic
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers
from ckan import model

from .helper_methods import make_dataset, make_resource

data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_add_resources_only_to_drafts():
    """do not allow adding resources to non-draft datasets"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    dataset, _ = make_dataset(create_context, owner_org, with_resource=True,
                              activate=True)
    # assert: adding resources to active datasets forbidden
    path = data_path / "calibration_beads_47.rtdc"
    with path.open('rb') as fd:
        upload = cgi.FieldStorage()
        upload.filename = path.name
        upload.file = fd
        with pytest.raises(logic.NotAuthorized):
            helpers.call_auth("resource_create", test_context,
                              package_id=dataset["id"],
                              upload=upload,
                              url="upload",
                              name=path.name,
                              )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_add_resources_only_to_drafts_package_revise():
    """do not allow adding resources to non-draft datasets"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    dataset, _ = make_dataset(create_context, owner_org, with_resource=True,
                              activate=True)
    # assert: adding resources to active datasets forbidden
    path = data_path / "calibration_beads_47.rtdc"
    with path.open('rb') as fd:
        upload = cgi.FieldStorage()
        upload.filename = path.name
        upload.file = fd
        with pytest.raises(logic.NotAuthorized):
            helpers.call_auth(
                "package_revise", test_context,
                **{"update": {
                       "id": dataset["id"],
                       "resources": {
                           "extend": [{"name": "peter.rtdc"}],
                           "-1": {"upload": ("peter.rtdc", fd)}
                       }},
                   })


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_create_anonymous():
    """anonymous cannot create dataset"""
    # Note: `call_action` bypasses authorization!
    context = {'ignore_auth': False, 'user': None, "model": model}
    # create a dataset
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_create", context)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_create_missing_org():
    """cannot create dataset in non-existent circle"""
    user = factories.User()
    # Note: `call_action` bypasses authorization!
    context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_create", context,
                          state="draft",
                          authors="Peter Pan",
                          license_id="CC-BY-4.0",
                          title="test",
                          owner_org="notthere"
                          )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_create_bad_collection():
    """cannot create dataset in other user's collection"""
    user_a = factories.User()
    user_b = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user_a['id'],
        'capacity': 'admin'
    }])
    owner_group = factories.Group(users=[
        {'name': user_a['id'], 'capacity': 'admin'},
    ])
    context_b = {'ignore_auth': False, 'user': user_b['name'], "model": model}

    with pytest.raises(logic.NotAuthorized):
        make_dataset(context_b, owner_org, with_resource=True,
                     activate=True,
                     groups=[{"id": owner_group["id"]}])


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_delete_only_drafts():
    """do not allow deleting datasets unless they are drafts"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    dataset = make_dataset(create_context, owner_org, with_resource=False)
    assert dataset["state"] == "draft", "dataset without res must be draft"
    # assert: draft datasets may be deleted
    assert helpers.call_auth("package_delete", test_context,
                             id=dataset["id"])
    # upload resource
    make_resource(create_context, dataset_id=dataset["id"])
    # set dataset state to active
    helpers.call_action("package_patch", create_context,
                        id=dataset["id"],
                        state="active")
    # check dataset state
    dataset2 = helpers.call_action("package_show", create_context,
                                   id=dataset["id"])
    assert dataset2["state"] == "active"
    # assert: active datasets may not be deleted
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_delete", test_context,
                          id=dataset["id"])


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_delete_other_user():
    """other users cannot delete your drafts"""
    user_a = factories.User()
    user_b = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user_a['id'],
        'capacity': 'admin'
    }])
    context_a = {'ignore_auth': False, 'user': user_a['name'], "model": model}
    context_b = {'ignore_auth': False, 'user': user_b['name'], "model": model}

    dataset = make_dataset(context_a, owner_org, with_resource=False,
                           activate=False)
    # assert: other users cannot delete your drafts
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_delete", context_b,
                          id=dataset["id"])


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_delete_anonymous():
    """anonymous cannot edit dataset"""
    user_a = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user_a['id'],
        'capacity': 'admin'
    }])
    context_a = {'ignore_auth': False, 'user': user_a['name'], "model": model}
    context_b = {'ignore_auth': False, 'user': None, "model": model}

    dataset = make_dataset(context_a, owner_org, with_resource=False,
                           activate=False)
    # assert: other users cannot delete your drafts
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_delete", context_b,
                          id=dataset["id"])


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_edit_anonymous():
    """anonymous cannot edit dataset"""
    user_a = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user_a['id'],
        'capacity': 'admin'
    }])
    context_a = {'ignore_auth': False, 'user': user_a['name'], "model": model}
    context_b = {'ignore_auth': False, 'user': None, "model": model}

    dataset = make_dataset(context_a, owner_org, with_resource=False,
                           activate=False)
    # assert: other users cannot delete your drafts
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_update", context_b,
                          id=dataset["id"],
                          title="Hans Peter")


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_license_more_restrictive_forbidden():
    """do not allow switching to a more restrictive license"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    dataset, res = make_dataset(create_context, owner_org, with_resource=True,
                                activate=True, license_id="CC0-1.0")
    # assert: cannot set license id to something less restrictive
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_patch", test_context,
                          id=dataset["id"],
                          license_id="CC-BY-4.0")


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_purge_anonymous():
    """anonymous cannot purge datasets"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': None, "model": model}
    # create a dataset
    dataset = make_dataset(create_context, owner_org, with_resource=False)
    # delete a dataset
    helpers.call_action("package_delete", create_context,
                        id=dataset["id"]
                        )
    # assert: check that anonymous cannot purge it
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("dataset_purge", test_context,
                          id=dataset["id"])


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_purge_draft():
    """do not allow purging of a non-deleted dataset"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    dataset = make_dataset(create_context, owner_org, with_resource=False,
                           activate=False)
    with pytest.raises(logic.NotAuthorized):
        # assert: cannot purge a draft
        helpers.call_auth("dataset_purge", test_context,
                          id=dataset["id"])


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_purge_deleted():
    """allow purging of deleted datasets"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    dataset = make_dataset(create_context, owner_org, with_resource=False)
    # delete a dataset
    helpers.call_action("package_delete", create_context,
                        id=dataset["id"]
                        )
    # assert: check that we can purge it
    assert helpers.call_auth("dataset_purge", test_context,
                             id=dataset["id"])


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_slug_editing_forbidden():
    """do not allow changing the name (slug)"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    dataset, res = make_dataset(create_context, owner_org, with_resource=True,
                                activate=True)
    assert dataset["state"] == "active"
    # assert: cannot set state back to draft
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_patch", test_context,
                          id=dataset["id"],
                          name="peterpan1234")


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_state_from_active_to_draft_forbidden():
    """do not allow setting the dataset state from active to draft"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    dataset, res = make_dataset(create_context, owner_org, with_resource=True,
                                activate=True)
    assert dataset["state"] == "active"
    # assert: cannot set state back to draft
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_patch", test_context,
                          id=dataset["id"],
                          state="draft")


@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_user_anonymous():
    """anonymous users cannot do much"""
    user_a = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user_a['id'],
        'capacity': 'admin'
    }])
    context_a = {'ignore_auth': False, 'user': user_a["name"], "model": model}
    context_b = {'ignore_auth': False, 'user': None, "model": model}

    with pytest.raises(logic.NotAuthorized):
        make_dataset(context_b, owner_org, with_resource=False,
                     activate=False)

    ds = make_dataset(context_a, owner_org, with_resource=False,
                      activate=False)

    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_update", context_b,
                          id=ds["id"])

    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_delete", context_b,
                          id=ds["id"])


@pytest.mark.ckan_config('ckanext.dcor_schemas.allow_public_datasets', "false")
@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_visibility_create_public_if_not_allowed():
    """do not allow creating public datasets if disallowed via config"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_create", test_context,
                          authors="Peter Pan",
                          license_id="CC-BY-4.0",
                          title="test",
                          owner_org=owner_org["name"],
                          private=False,
                          )


@pytest.mark.ckan_config('ckanext.dcor_schemas.allow_public_datasets', "true")
@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_visibility_create_public_if_not_allowed_control():
    """allow creating public datasets if allowed via config"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    assert helpers.call_auth("package_create", test_context,
                             authors="Peter Pan",
                             license_id="CC-BY-4.0",
                             title="test",
                             owner_org=owner_org["name"],
                             private=False,
                             )


@pytest.mark.ckan_config('ckanext.dcor_schemas.allow_public_datasets', "true")
@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_visibility_update_1_private2public_allowed():
    """allow changing visibility from private to public"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    dataset, res = make_dataset(create_context, owner_org, with_resource=True,
                                activate=True, private=True)
    # assert: user should be able to make private dataset public
    assert helpers.call_auth("package_patch", test_context,
                             id=dataset["id"],
                             private=False)


@pytest.mark.ckan_config('ckanext.dcor_schemas.allow_public_datasets', "true")
@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_visibility_update_1_public2private_not_allowed():
    """do not allow to set the visibility of a public dataset to private"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    dataset, res = make_dataset(create_context, owner_org, with_resource=True,
                                activate=True, private=False)
    # assert: cannot set private to True for active datasets
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_patch", test_context,
                          id=dataset["id"],
                          private=True)


@pytest.mark.ckan_config('ckanext.dcor_schemas.allow_public_datasets', "false")
@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_visibility_update_2_private2public_not_allowed():
    """
    do not allow to change visibility from private to public if
    ckanext.dcor_schemas.allow_public_datasets is false
    """
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset (no auth check done during testing, so we can create
    # a public dataset)
    dataset, res = make_dataset(create_context, owner_org, with_resource=True,
                                activate=True, private=True)
    # assert: changing private to public should not work
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_patch", test_context,
                          id=dataset["id"],
                          private=False)


@pytest.mark.ckan_config('ckanext.dcor_schemas.allow_public_datasets', "false")
@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_visibility_update_2_public2private_allowed():
    """
    allow to change visibility from public to private if
    ckanext.dcor_schemas.allow_public_datasets is false
    """
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': True, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset (no auth check done during testing, so we can create
    # a public dataset)
    dataset, res = make_dataset(create_context, owner_org, with_resource=True,
                                activate=True, private=False, name="test")
    # assert: changing public to private should work
    assert helpers.call_auth("package_patch", test_context,
                             id=dataset["id"],
                             private=True)
