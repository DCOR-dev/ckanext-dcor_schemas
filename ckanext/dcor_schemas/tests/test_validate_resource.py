import cgi
import pathlib
import shutil
import tempfile

import pytest

import ckan.logic as logic
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers

from .helper_methods import make_dataset

data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_create_custom_upload_name_overridden():
    """custom resource name is overridden during upload"""
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
        res = helpers.call_action("resource_create", create_context1,
                                  package_id=dataset["id"],
                                  upload=upload,
                                  url="upload",
                                  name=path.name + "something_else.rtdc",
                                  )
        assert res["name"] == path.name


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_create_same_name_forbidden():
    """do not allow uploading resources with the same name"""
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
        with pytest.raises(logic.ValidationError):
            helpers.call_action("resource_create", create_context2,
                                package_id=dataset["id"],
                                upload=upload,
                                url="upload",
                                name=path.name,
                                )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_create_restrict_extensions():
    """restrict upload data extensions"""
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
    tdir = tempfile.mkdtemp(prefix="test_dcor_schemas_")
    path = pathlib.Path(tdir) / "bad_extension.docx"
    path.write_text("lorem ipsum doesn't want Word in data repositories")
    # create the first resource
    with path.open('rb') as fd:
        upload = cgi.FieldStorage()
        upload.filename = path.name
        upload.file = fd
        with pytest.raises(logic.ValidationError):
            helpers.call_action("resource_create", create_context1,
                                package_id=dataset["id"],
                                upload=upload,
                                url="upload",
                                name=path.name,
                                )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_create_weird_characters():
    """do not allow weird characters in resource names"""
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
    tdir = tempfile.mkdtemp(prefix="test_dcor_schemas_")
    path2 = pathlib.Path(tdir) / "µæsdqow.rtdc"
    shutil.copy2(path, path2)
    # create the first resource
    with path2.open('rb') as fd:
        upload = cgi.FieldStorage()
        upload.filename = path2.name
        upload.file = fd
        with pytest.raises(logic.ValidationError):
            helpers.call_action("resource_create", create_context1,
                                package_id=dataset["id"],
                                upload=upload,
                                url="upload",
                                name=path2.name,
                                )
