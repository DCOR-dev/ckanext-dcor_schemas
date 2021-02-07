import cgi
import pathlib

import pytest

import ckan.tests.factories as factories
import ckan.tests.helpers as helpers
import ckan.plugins.toolkit as toolkit

from .helper_methods import make_dataset

data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_create_same_name_forbidden():
    """a dataset cannot have two resources with the same name"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False, 'user': user['name']}
    dataset = make_dataset(create_context1, owner_org, with_resource=False,
                           activate=False)
    path = data_path / "calibration_beads_47.rtdc"
    # create the first resource
    with path.open('rb') as fd:
        upload = cgi.FieldStorage()
        upload.filename = path.name
        upload.file = fd
        helpers.call_action("resource_create", create_context1,
                            package_id=dataset["id"],
                            upload=upload,
                            url="upload",
                            name=path.name,
                            )
    # attempt creation of second resource with same name
    create_context2 = {'ignore_auth': False, 'user': user['name']}
    with path.open('rb') as fd:
        upload = cgi.FieldStorage()
        upload.filename = path.name
        upload.file = fd
        with pytest.raises(toolkit.Invalid):
            helpers.call_action("resource_create", create_context2,
                                package_id=dataset["id"],
                                upload=upload,
                                url="upload",
                                name=path.name,
                                )
