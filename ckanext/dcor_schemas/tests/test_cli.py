import pytest

from ckan.cli.cli import ckan
import ckan.tests.factories as factories

from .helper_methods import make_dataset


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_zombies_basic_clean_db(cli):
    result = cli.invoke(ckan, ["list-zombie-users"])
    for line in result.output.split("\n"):
        if not line.strip():
            continue
        elif line.count("INFO"):
            continue
        else:
            assert False, "clean_db -> no users -> no output"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_zombies_with_a_user(cli):
    factories.User()
    result = cli.invoke(ckan, ["list-zombie-users", "--last-activity-weeks",
                               "0"])
    for line in result.output.split("\n"):
        if not line.strip():
            continue
        elif line.count("INFO"):
            continue
        elif line.count("test_user_"):
            break
    else:
        assert False, "test_user should have been found"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_zombies_with_a_user_with_dataset(cli):
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    make_dataset(create_context, owner_org, with_resource=True,
                 activate=True)

    result = cli.invoke(ckan, ["list-zombie-users", "--last-activity-weeks",
                               "0"])
    for line in result.output.split("\n"):
        if not line.strip():
            continue
        elif line.count("INFO"):
            continue
        else:
            assert False, "user with dataset should have been ignored"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_zombies_with_active_user(cli):
    factories.User()
    result = cli.invoke(ckan, ["list-zombie-users", "--last-activity-weeks",
                               "12"])
    for line in result.output.split("\n"):
        if not line.strip():
            continue
        elif line.count("INFO"):
            continue
        else:
            assert False, "active user should have been ignored"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_zombies_with_admin(cli):
    factories.Sysadmin()
    result = cli.invoke(ckan, ["list-zombie-users", "--last-activity-weeks",
                               "0"])
    for line in result.output.split("\n"):
        if not line.strip():
            continue
        elif line.count("INFO"):
            continue
        else:
            assert False, "sysadmin should have been ignored"
