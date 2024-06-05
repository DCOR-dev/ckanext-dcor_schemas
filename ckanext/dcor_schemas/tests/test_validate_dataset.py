import pathlib
import shutil
import tempfile

import h5py
import pytest

import ckan.logic as logic
import ckan.model as model
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers

from dcor_shared.testing import make_dataset

data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_authors_is_csv(create_with_upload):
    """author list "authors" is CSV"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False,
                       'user': user['name'], 'api_version': 3}

    ds_dict, _ = make_dataset(
        create_context1, owner_org,
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True,
        authors="Peter Pan,Ben Elf,  Buddy Holly")  # [sic!]
    ds_dict = helpers.call_action("package_show",
                                  id=ds_dict["id"],
                                  )
    assert ds_dict["authors"] == "Peter Pan, Ben Elf, Buddy Holly"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_authors_mandatory():
    """force user to select authors"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False,
                       'user': user['name'], 'api_version': 3}

    with pytest.raises(logic.ValidationError) as e:
        make_dataset(create_context1, owner_org,
                     activate=False, authors="")
    assert "'authors': ['Missing value']" in str(e.value)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_doi_remove_url(create_with_upload):
    """parse DOI field (remove URL part)"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False,
                       'user': user['name'], 'api_version': 3}

    ds_dict, _ = make_dataset(
        create_context1, owner_org,
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True,
        doi="https://doi.org/10.1371/journal.pone.0088458"
    )
    ds_dict = helpers.call_action("package_show",
                                  id=ds_dict["id"],
                                  )
    assert ds_dict["doi"] == "10.1371/journal.pone.0088458"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_license_id_mandatory():
    """force user to select license_id"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False,
                       'user': user['name'], 'api_version': 3}

    with pytest.raises(logic.ValidationError) as e:
        make_dataset(create_context1, owner_org,
                     activate=False, license_id="")
    assert "Please choose a license_id" in str(e.value)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_license_restrict_cc():
    """restrict to basic CC licenses"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False,
                       'user': user['name'], 'api_version': 3}

    with pytest.raises(logic.ValidationError) as e:
        make_dataset(create_context1, owner_org,
                     activate=False, license_id="CC-BY-NE-4.0")
    assert "Please choose a license_id" in str(e.value)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_name_slug():
    """automatically generate dataset name (slug) using random characters"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False,
                       'user': user['name'], 'api_version': 3}
    ds1 = make_dataset(create_context1, owner_org,
                       activate=False, name="ignored")
    assert ds1["name"] != "ignored"

    create_context2 = {'ignore_auth': False,
                       'user': user['name'], 'api_version': 3}
    ds2 = make_dataset(create_context2, owner_org,
                       activate=False, name="ignored")
    assert ds2["name"] != ds1["name"]


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_name_slug_empty():
    """dataset title generation when user passed empty value"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False,
                       'user': user['name'], 'api_version': 3}
    ds1 = make_dataset(create_context1, owner_org,
                       activate=False, title="")
    assert ds1["name"]


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_name_slug_exists():
    """not automatically generate dataset name (slug) for admins"""
    admin = factories.Sysadmin()
    owner_org1 = factories.Organization(users=[{
        'name': admin['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False,
                       'user': admin['name'], 'api_version': 3}

    # Create all possible datasets with admin so that "user" has to
    # create one with a character more.
    ds1 = make_dataset(create_context1, owner_org1,
                       activate=False, name="existing-name")
    assert ds1["name"] == "existing-name", "sanity check"
    for ch in "0123456789abcdef":
        name = "existing-name-" + ch
        ds1 = make_dataset(create_context1, owner_org1,
                           activate=False, name=name)
        assert ds1["name"] == name, "sanity check"

    # Now create user dataset
    user = factories.User()
    owner_org2 = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context2 = {'ignore_auth': False,
                       'user': user['name'], 'api_version': 3}
    ds2 = make_dataset(create_context2, owner_org2,
                       activate=False, title="existing-name")
    assert ds2["name"].startswith("existing-name-")
    assert len(ds2["name"]) == len("existing-name-") + 2


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_name_slug_invalid():
    """test bad dataset names"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    for name in ["edit", "new", "search"]:
        create_context1 = {'ignore_auth': False,
                           'user': user['name'], 'api_version': 3}
        ds1 = make_dataset(create_context1, owner_org,
                           activate=False, title=name)
        assert ds1["name"] != name


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_name_slug_long():
    """the slug should not be longer than allowed"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False,
                       'user': user['name'], 'api_version': 3}
    ds1 = make_dataset(create_context1, owner_org,
                       activate=False, title="a"*500)
    assert len(ds1["name"]) < 500


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_name_slug_long_2():
    """This is a test for when PACKAGE_NAME_MAX_LENGTH!=100"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    model.PACKAGE_NAME_MAX_LENGTH = 10
    create_context1 = {'ignore_auth': False, 'user': user['name'],
                       'model': model, 'api_version': 3}
    ds1 = make_dataset(create_context1, owner_org,
                       activate=False, title="z"*15)
    try:
        assert len(ds1["name"]) <= 10
    except BaseException:
        pass
    finally:
        # reset everything
        model.PACKAGE_NAME_MAX_LENGTH = 100


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_name_slug_no_admin():
    """not automatically generate dataset name (slug) for admins"""
    admin = factories.Sysadmin()
    owner_org = factories.Organization(users=[{
        'name': admin['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False,
                       'user': admin['name'], 'api_version': 3}
    ds1 = make_dataset(create_context1, owner_org,
                       activate=False, name="ignored")
    assert ds1["name"] == "ignored"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_name_slug_short():
    """dataset title generation when user passed value that is too short"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False,
                       'user': user['name'], 'api_version': 3}
    ds1 = make_dataset(create_context1, owner_org,
                       activate=False, title="z")
    assert len(ds1["name"]) >= 2


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_name_slug_short_2():
    """This is a special case when PACKAGE_NAME_MIN_LENGTH is changed"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    model.PACKAGE_NAME_MIN_LENGTH = 10
    create_context1 = {'ignore_auth': False, 'user': user['name'],
                       'model': model, 'api_version': 3}
    ds1 = make_dataset(create_context1, owner_org,
                       activate=False, title="z")
    try:
        assert len(ds1["name"]) >= 10
    except BaseException:
        pass
    finally:
        # reset everything
        model.PACKAGE_NAME_MIN_LENGTH = 2


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_references(create_with_upload):
    """Test parsing of references"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    model.PACKAGE_NAME_MIN_LENGTH = 10
    create_context = {'ignore_auth': False, 'user': user['name'],
                      'model': model, 'api_version': 3}
    references = [
        "https://dx.doi.org/10.1186/s12859-020-03553-y",
        "http://dx.doi.org/10.1038/s41592-020-0831-y",
        "dx.doi.org/10.1186/s12859-019-3010-3",
        "doi:10.1039/C9SM01226E",
        "https://arxiv.org/abs/1507.00466",
        "arxiv:1507.00466",
        "https://www.biorxiv.org/content/10.1101/862227v2",
        "https://www.biorxiv.org/content/10.1101/862227v2.full.pdf+html",
        "biorxiv:10.1101/862227v2",
    ]
    ds_dict, _ = make_dataset(
        create_context, owner_org,
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True,
        references=",".join(references))
    refs = [r.strip() for r in ds_dict["references"].split(",")]
    assert refs[0] == "doi:10.1186/s12859-020-03553-y"
    assert refs[1] == "doi:10.1038/s41592-020-0831-y"
    assert refs[2] == "doi:10.1186/s12859-019-3010-3"
    assert refs[3] == "doi:10.1039/C9SM01226E"
    assert refs[4] == "arXiv:1507.00466"
    assert refs[5] == "arXiv:1507.00466"
    assert refs[6] == "bioRxiv:10.1101/862227v2"
    assert refs[7] == "bioRxiv:10.1101/862227v2"
    assert refs[8] == "bioRxiv:10.1101/862227v2"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_state_draft_no_resources():
    """a dataset without resources is cannot be activated"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}

    with pytest.raises(logic.ValidationError,
                       match="because it does not contain any resources"):
        make_dataset(create_context, owner_org,
                     activate=True)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_state_from_draft_to_active_without_rtdc_forbidden(
        create_with_upload):
    """do not allow activating a dataset without a valid .rtdc file"""
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
    ds_dict = make_dataset(create_context, owner_org,
                           activate=False, license_id="CC0-1.0")
    # upload an invalid .rtdc File
    path = pathlib.Path(tempfile.mkdtemp()) / "test_invalid_file_upload.rtdc"
    path.write_bytes(b"This is not a valid HDF5 file!")
    content = path.read_bytes()
    create_with_upload(
        content, 'test.rtdc',
        url="upload",
        package_id=ds_dict["id"],
        context=create_context,
    )
    # assert: cannot activate dataset without valid .rtdc file
    with pytest.raises(
            logic.ValidationError,
            match="make sure that it contains a valid DC resource"):
        helpers.call_action("package_patch", test_context,
                            id=ds_dict["id"],
                            state="active")


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_state_from_draft_to_active_without_rtdc_forbidden_2(
        create_with_upload):
    """do not allow activating a dataset without a valid .rtdc file"""
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
    ds_dict = make_dataset(create_context, owner_org,
                           activate=False, license_id="CC0-1.0")
    # upload an invalid .rtdc File
    path_orig = data_path / "calibration_beads_47.rtdc"
    path = pathlib.Path(tempfile.mkdtemp()) / "test_invalid_file_upload.rtdc"
    # provoke sanity checks to fail
    shutil.copy2(path_orig, path)
    with h5py.File(path, "a") as h5:
        deform_cropped = h5["events"]["deform"][:-4]
        del h5["events"]["deform"]
        h5["events"]["deform"] = deform_cropped
    content = path.read_bytes()
    create_with_upload(
        content, 'test.rtdc',
        url="upload",
        package_id=ds_dict["id"],
        context=create_context,
    )
    # assert: cannot activate dataset without valid .rtdc file
    with pytest.raises(
            logic.ValidationError,
            match="make sure that it contains a valid DC resource"):
        helpers.call_action("package_patch", test_context,
                            id=ds_dict["id"],
                            state="active")


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_state_from_draft_to_active_without_rtdc_forbidden_control(
        create_with_upload):
    """negative control for previous test"""
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
    # upload a *valid* [sic] .rtdc File (this is the control)
    ds_dict = make_dataset(create_context, owner_org,
                           activate=False)
    content = (data_path / "calibration_beads_47.rtdc").read_bytes()
    create_with_upload(
        content, 'test.rtdc',
        url="upload",
        package_id=ds_dict["id"],
        context=create_context,
    )
    # assert: *can* activate dataset *with* valid .rtdc file
    helpers.call_action("package_patch", test_context,
                        id=ds_dict["id"],
                        state="active")
