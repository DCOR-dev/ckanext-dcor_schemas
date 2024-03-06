import copy
import pathlib
import uuid

import pytest

import ckan.logic as logic
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers
from ckan import model

from dcor_shared.testing import make_dataset

data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_add_resources_only_to_drafts_package_revise(
        create_with_upload):
    """do not allow adding resources to non-draft datasets"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    test_context = {'ignore_auth': False,
                    'user': user['name'], 'model': model, 'api_version': 3}
    # create a dataset
    ds_dict, _ = make_dataset(
        create_context, owner_org,
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True)
    # assert: adding resources to active datasets forbidden
    resources = copy.deepcopy(ds_dict["resources"])
    resources.append({"name": "peter.rtdc",
                      "url": "upload",
                      "package_id": ds_dict["id"]})
    with pytest.raises(
            logic.NotAuthorized,
            match="Changing 'resources' not allowed for non-draft datasets"):
        helpers.call_auth(
            "package_revise", test_context,
            **{"update": {
                "id": ds_dict["id"],
                "resources": resources}
               })


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_add_resources_only_to_drafts_package_revise_control(
        create_with_upload):
    """do not allow adding resources to non-draft datasets"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    test_context = {'ignore_auth': False,
                    'user': user['name'], 'model': model, 'api_version': 3}
    # create a dataset
    ds_dict, _ = make_dataset(
        create_context, owner_org,
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=False)
    # assert: adding resources to draft datasets allowed
    resources = copy.deepcopy(ds_dict["resources"])
    resources.append({"name": "peter.rtdc",
                      "url": "upload",
                      "sp:chip:channel width": 21.0,  # this must be supported
                      "package_id": ds_dict["id"]})
    helpers.call_auth(
        "package_revise", test_context,
        **{"update": {
            "id": ds_dict["id"],
            "resources": resources}
           })


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_add_resources_set_id_not_allowed_package_revise(
        create_with_upload):
    """do not allow adding resources to non-draft datasets"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    test_context = {'ignore_auth': False,
                    'user': user['name'], 'model': model, 'api_version': 3}
    # create a dataset
    ds_dict, _ = make_dataset(
        create_context, owner_org,
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=False)
    # assert: if resource is not on S3, cannot add it to the dataset
    resources = copy.deepcopy(ds_dict["resources"])
    resources.append({"name": "peter.rtdc",
                      "url": "upload",
                      "package_id": ds_dict["id"],
                      "id": str(uuid.uuid4())})
    with pytest.raises(logic.NotAuthorized, match="not available on S3"):
        helpers.call_auth(
            "package_revise", test_context,
            **{"update": {
                "id": ds_dict["id"],
                "resources": resources,
            }},
        )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_update_resources_only_for_drafts_package_revise(
        create_with_upload):
    """do not allow editing resources (except description)"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    test_context = {'ignore_auth': False,
                    'user': user['name'], 'model': model, 'api_version': 3}

    # create a dataset
    ds_dict, _ = make_dataset(
        create_context, owner_org,
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=False)
    # modifying the description should work
    helpers.call_auth(
        "package_revise", test_context,
        **{"update": {
            "id": ds_dict["id"],
            "resources": [{
                "id": ds_dict["resources"][0]["id"],
                "description": "A new description",
                "sp:chip:channel width": 21.0,  # this must be supported
            }
            ],
        }})
    helpers.call_action(
        "package_revise", test_context,
        **{"match__id": ds_dict["id"],
           "update__resources__0": {"description": "A new description",
                                    "sp:chip:channel width": 21.0}
           })
    # make sure that worked
    dataset2 = helpers.call_action("package_show", create_context,
                                   id=ds_dict["id"])
    assert dataset2["resources"][-1]["description"] == "A new description"
    assert dataset2["resources"][-1]["sp:chip:channel width"] == 21.0

    # modifying anything else should *not* work
    with pytest.raises(
            logic.NotAuthorized,
            match="Editing not allowed: dc:experiment:date=2017-02-09"):
        helpers.call_auth(
            "package_revise", test_context,
            **{"update": {
                "id": ds_dict["id"],
                "resources": [{
                    "id": ds_dict["resources"][0]["id"],
                    "dc:experiment:date": "2017-02-09"}],
            }})


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_update_resources_only_for_drafts_package_revise_2(
        create_with_upload):
    """do not allow editing resources (except description)"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    test_context = {'ignore_auth': False,
                    'user': user['name'], 'model': model, 'api_version': 3}

    # create a dataset
    ds_dict, _ = make_dataset(
        create_context, owner_org,
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True)

    # modifying the description should not work for active datasets
    with pytest.raises(
            logic.NotAuthorized,
            match="Changing 'resources' not allowed for non-draft datasets"):
        helpers.call_auth(
            "package_revise", test_context,
            **{"update": {
                "id": ds_dict["id"],
                "resources": [{
                    "id": ds_dict["resources"][0]["id"],
                    "description": "A new description",
                }
                ],
            }})

    # modifying the RSS should not work for active datasets
    with pytest.raises(
            logic.NotAuthorized,
            match="Changing 'resources' not allowed for non-draft datasets"):
        helpers.call_auth(
            "package_revise", test_context,
            **{"update": {
                "id": ds_dict["id"],
                "resources": [{
                    "id": ds_dict["resources"][0]["id"],
                    "sp:chip:channel width": 21.0,
                }
                ],
            }})
