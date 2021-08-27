import uuid

import ckan.authz as authz
import ckan.lib.navl.dictization_functions as df
import ckan.logic as logic
import ckan.model as model
import ckan.plugins.toolkit as toolkit

import dclab
from slugify import slugify

from . import resource_schema_supplements as rss


RESOURCE_CHARS = "abcdefghijklmnopqrstuvwxyz" \
                 + "ABCDEFGHIJKLMNOPQRSTUVWXYZ" \
                 + "0123456789" \
                 + ".,-_+()[]"

RESOURCE_EXTS = [
    # data
    ".rtdc",
    # metadata
    ".ini",
    # tables
    ".csv",
    ".tsv",
    # notes
    ".pdf",
    ".txt",
    # images
    ".jpg",
    ".png",
    ".tif",
    # analysis
    ".py",
    ".ipynb",
    # dclab/Shape-Out filter files
    ".poly",
    ".sof",
    # Shape-Out sessions
    ".so2",
]


def dataset_authors(value):
    authors = [a.strip() for a in value.split(",") if a.strip()]
    return ", ".join(authors)


def dataset_doi(value):
    if value.count("://"):
        value = value.split("://")[1].split("/", 1)[1]
    value = value.strip(" /")
    return value


def dataset_license_id(key, data, errors, context):
    """Restrict to licenses.json (except sysadmins)"""
    user = context.get('user')
    ignore_auth = context.get('ignore_auth')
    if ignore_auth or (user and authz.is_sysadmin(user)):
        return

    value = data[key]
    register = model.Package.get_license_register()
    sorted_licenses = sorted(register.values(), key=lambda x: x.title)
    license_ids = [ll.id for ll in sorted_licenses if ll.id != "none"]
    if value not in license_ids:
        raise toolkit.Invalid(
            "Please choose a license_id: {}".format(license_ids))


def dataset_name_create(key, data, errors, context):
    """Generate a unique name for the dataset

    This takes into account the ideas of "name_validator"
    and "package_name_validator" in CKAN logic.validators.

    Admins are allowed to set the name.
    """
    user = context.get('user')
    ignore_auth = context.get('ignore_auth')
    if ignore_auth or (user and authz.is_sysadmin(user)):
        # Admins know what they are doing (e.g. figshare import)
        return

    # preparations
    model = context['model']
    session = context['session']
    package = context.get('package')

    if package:
        package_id = package.id
        package_title = package.title
    else:
        package_id = data.get(key[:-1] + ('id',))
        package_title = data.get(key[:-1] + ('title',))

    if package_id and package_id is not df.missing:
        rand = package_id
    else:
        rand = uuid.uuid4().hex

    # convert title to slug
    title_slug = slugify(package_title)
    slug = title_slug

    for ii in range(len(rand)):
        # Update slug
        if ii == 0:
            if len(slug) == 0:  # start with a random character
                slug += rand[:model.PACKAGE_NAME_MIN_LENGTH]
            elif len(slug) < model.PACKAGE_NAME_MIN_LENGTH:
                slug += "-" + rand[ii]
        elif ii == 1:
            if len(title_slug) != 0:  # add a dash if a title was given
                slug += "-" + rand[ii]
        else:  # add random character
            slug += rand[ii]

        # Do not allow any of those slugs
        if slug in ["edit", "new", "search"]:
            if ii == 0:
                slug += "-"
            slug += rand[ii]

        # Honor model restrictions
        if len(slug) < model.PACKAGE_NAME_MIN_LENGTH:
            slug += rand[:(model.PACKAGE_NAME_MIN_LENGTH - len(slug))]
        elif len(slug) > model.PACKAGE_NAME_MAX_LENGTH:
            # change the last character to have more options
            slug = slug[:model.PACKAGE_NAME_MAX_LENGTH-10] + "-" + rand[ii]

        # Check if the slug/name exists
        query = session.query(model.Package.state).filter_by(name=slug)
        if package_id and package_id is not df.missing:
            # remove the current package id, if we have one
            query = query.filter(model.Package.id != package_id)

        result = query.first()
        if result and result.state != model.core.State.DELETED:
            # the slug already exists
            continue
        else:
            # we have our slug!
            break
    else:
        errors[key].append('Could not slugify title: {}'.format(slug))

    data[key] = slug


def dataset_references(value):
    refs = []
    for r in value.split(","):
        r = r.strip()
        if r:
            if r.count("doi.org/"):
                r = "doi:" + r.split("doi.org/", 1)[1]
            elif r.count("arxiv.org/"):
                r = "arXiv:" + r.split("/")[-1]
            if r.lower().startswith("arxiv:"):
                r = "arXiv:" + r.split(":", 1)[1]
            elif r.count("biorxiv.org/"):
                r = "bioRxiv:" + r.split("biorxiv.org/content/")[-1]
                r = r.replace(".full.pdf+html", "")
                r = r.replace(".full.pdf", "")
            if r.lower().startswith("biorxiv:"):
                r = "bioRxiv:" + r.split(":", 1)[1]
            refs.append(r)
    return ", ".join(refs)


def dataset_state(key, data, errors, context):
    """If a dataset does not have any resources, it must be a draft"""
    data_dict = df.unflatten(data)

    if (data[key] == "active"
        and ("resources" not in data_dict
             or len(data_dict["resources"]) == 0)):
        # The user wants to activate the dataset although it does not
        # contain any resources. This is not possible!
        raise toolkit.Invalid(
            "Cannot set state of dataset to 'active', because it does not "
            "contain any resources!")


def resource_dc_config(key, data, errors, context):
    """Parse configuration parameters"""
    value = data[key]
    _, sec, val = key[-1].split(":")
    func = dclab.dfn.config_funcs[sec][val]
    try:
        value = func(value)
    except BaseException:
        raise toolkit.Invalid("Invalid value for '{}': '{}'!".format(key[-1],
                                                                     value))
    data[key] = value


def resource_dc_supplement(key, data, errors, context):
    """Parse user-defined supplementary parameters"""
    value = data[key]
    # send them through the loop
    try:
        si = rss.SupplementItem.from_composite(composite_key=key[-1],
                                               composite_value=value)
        _, composite_value = si.to_composite()
    except BaseException:
        raise toolkit.Invalid(
            "Invalid value for '{}': '{}'!".format(key[-1], value)
        )
    data[key] = composite_value


def resource_name(key, data, errors, context):
    """Check resource names

    - no weird characters
    - only allowed file extensions
    """
    assert key[0] == "resources"
    assert key[2] == "name"
    user = context.get('user')
    ignore_auth = context.get('ignore_auth')
    if ignore_auth or (user and authz.is_sysadmin(user)):
        # Admins know what they are doing (e.g. figshare import)
        return

    name = data[key]

    # check suffix
    if name.count("."):
        suffix = "." + name.rsplit(".", 1)[1]
    else:
        suffix = None
    if suffix not in RESOURCE_EXTS:
        raise toolkit.Invalid(
            "Unsupported file extension '{}'. ".format(suffix)
            + "Allowed file extensions are {}.".format(RESOURCE_EXTS))

    # check that filename contains valid characters
    invalid_chars = []
    for char in name:
        if char not in RESOURCE_CHARS:
            invalid_chars.append(char)
    if invalid_chars:
        raise toolkit.Invalid(u"Invalid characters in file name: {}".format(
            u"".join(invalid_chars)))

    # do not allow adding resources that exist already
    package = context.get('package')
    if package:
        package_id = package.id
    else:
        package_id = data.get(key[:-1] + ('id',))
    pkg_dict = logic.get_action('package_show')(
        dict(context, return_type='dict'),
        {'id': package_id})

    ress = pkg_dict.get("resources", [])
    if ress:
        # check name
        for item in ress:
            # Since this function is called for each and every
            # resource all the time, we have to make sure that
            # the positions are not matching.
            if key[1] != item["position"] and item["name"] == name:
                raise toolkit.Invalid(
                    "Resource with name '{}' already exists!".format(name))
