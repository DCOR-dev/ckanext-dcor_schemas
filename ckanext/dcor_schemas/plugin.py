import hashlib
import pathlib
import time

from ckan.lib.plugins import DefaultPermissionLabels
import ckan.lib.uploader as uploader
from ckan import logic
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit

import dclab
from dcor_shared import DC_MIME_TYPES, wait_for_resource


from . import auth as dcor_auth
from . import validate as dcor_validate
from . import helpers as dcor_helpers


#: ignored schema fields (see default_create_package_schema in
#: https://github.com/ckan/ckan/blob/master/ckan/logic/schema.py)
REMOVE_PACKAGE_FIELDS = [
    "author",
    "author_email",
    "maintainer",
    "maintainer_email",
    "url",
    "version",
]


def get_dataset_path(context, resource):
    resource_id = resource["id"]
    rsc = toolkit.get_action('resource_show')(context, {'id': resource_id})
    upload = uploader.ResourceUpload(rsc)
    filepath = upload.get_path(rsc['id'])
    return filepath


def patch_resource(data_dict):
    resource_patch = logic.get_action("resource_patch")
    resource_show = logic.get_action("resource_show")

    while True:
        # https://github.com/ckan/ckan/issues/2017
        resource_patch(context={}, data_dict=data_dict)
        rs = resource_show({}, {"id": data_dict["id"]})
        for key in data_dict:
            # do it again
            if data_dict[key] != rs[key]:
                time.sleep(0.01)
                break
        else:
            # everything matches up
            break


def set_dc_config_job(path, resource):
    """Store all DC config metadata"""
    path = pathlib.Path(path)
    wait_for_resource(path)
    mtype = resource.get('mimetype', '')
    if mtype in DC_MIME_TYPES:
        data_dict = {"id": resource["id"]}
        with dclab.new_dataset(path) as ds:
            for sec in dclab.dfn.CFG_METADATA:
                if sec in ds.config:
                    for key in dclab.dfn.config_keys[sec]:
                        if key in ds.config[sec]:
                            dckey = 'dc:{}:{}'.format(sec, key)
                            value = ds.config[sec][key]
                            data_dict[dckey] = value
        patch_resource(data_dict=data_dict)


def set_sha256_job(path, resource):
    """Computes the sha256 hash and writes it to the resource metadata"""
    if not resource.get("sha256", "").strip():  # only compute if necessary
        file_hash = hashlib.sha256()
        with open(path, "rb") as fd:
            while True:
                data = fd.read(2**20)
                if not data:
                    break
                file_hash.update(data)
        sha256sum = file_hash.hexdigest()
        patch_resource(data_dict={"id": resource["id"],
                                  "sha256": sha256sum})


class DCORDatasetFormPlugin(plugins.SingletonPlugin,
                            toolkit.DefaultDatasetForm,
                            DefaultPermissionLabels):
    '''This plugin makes views of DC data'''
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IConfigurer, inherit=True)
    plugins.implements(plugins.IDatasetForm)
    plugins.implements(plugins.IPermissionLabels)
    plugins.implements(plugins.IResourceController, inherit=True)
    plugins.implements(plugins.ITemplateHelpers)

    # IAuthfunctions
    def get_auth_functions(self):
        # `*_patch` has same authorization as `*_update`
        return {
            'bulk_update_delete': dcor_auth.deny,
            'dataset_purge': dcor_auth.dataset_purge,
            'group_create': dcor_auth.login_user,
            'organization_create': dcor_auth.login_user,
            'package_create': dcor_auth.package_create,
            'package_delete': dcor_auth.package_delete,
            'package_update': dcor_auth.package_update,
            'resource_create': dcor_auth.resource_create,
            'resource_delete': dcor_auth.deny,
            'resource_update': dcor_auth.resource_update,
        }

    # IConfigurer
    def update_config(self, config):
        # Add this plugin's templates dir to CKAN's extra_template_paths, so
        # that CKAN will use this plugin's custom templates.
        toolkit.add_template_directory(config, 'templates')
        toolkit.add_resource('assets', 'dcor_schemas')
        toolkit.add_public_directory(config, 'public')

    # IDatasetForm
    def _modify_package_schema(self, schema):
        # remove default fields
        for key in REMOVE_PACKAGE_FIELDS:
            if key in schema:
                schema.pop(key)
        schema.pop("state")
        schema.update({
            'authors': [
                toolkit.get_validator('unicode_safe'),
                dcor_validate.authors,
                toolkit.get_validator('not_empty'),
                toolkit.get_converter('convert_to_extras'),
            ],
            'doi': [
                toolkit.get_validator('ignore_missing'),
                dcor_validate.doi,
                toolkit.get_validator('unicode_safe'),
                toolkit.get_converter('convert_to_extras'),
            ],
            'references': [
                toolkit.get_validator('ignore_missing'),
                dcor_validate.references,
                toolkit.get_validator('unicode_safe'),
                toolkit.get_converter('convert_to_extras'),
            ],
            'state': [
                toolkit.get_validator('ignore_missing'),
                dcor_validate.state,
            ],
            'license_id': [
                dcor_validate.license_id,
            ],
        })
        schema['resources'].update({
            'sha256': [
                toolkit.get_validator('ignore_missing'),
            ],
            'name': [
                toolkit.get_validator('ignore_missing'),
                toolkit.get_validator('unicode_safe'),
                dcor_validate.resource_name,
            ],
        })
        # Add dclab configuration parameters
        for sec in dclab.dfn.CFG_METADATA:
            for key in dclab.dfn.config_keys[sec]:
                schema['resources'].update({
                    'dc:{}:{}'.format(sec, key): [
                        toolkit.get_validator('ignore_missing'),
                        dcor_validate.resource_dc_config,
                    ]})
        return schema

    def create_package_schema(self):
        schema = super(DCORDatasetFormPlugin, self).create_package_schema()
        schema = self._modify_package_schema(schema)
        schema.update({
            'name': [
                toolkit.get_validator('unicode_safe'),
                dcor_validate.name_create,
            ],
        })

        return schema

    def update_package_schema(self):
        schema = super(DCORDatasetFormPlugin, self).update_package_schema()
        schema = self._modify_package_schema(schema)
        schema.update({
            'private': [
                # boolean validator has to come first ('False' -> False)
                toolkit.get_validator('boolean_validator'),
                dcor_validate.private_update,
            ]
        })
        return schema

    def show_package_schema(self):
        schema = super(DCORDatasetFormPlugin, self).show_package_schema()
        # remove default fields
        for key in REMOVE_PACKAGE_FIELDS:
            if key in schema:
                schema.pop(key)
        schema.update({
            'authors': [
                toolkit.get_converter('convert_from_extras'),
                toolkit.get_validator('ignore_missing'),
                toolkit.get_validator('unicode_safe'),
            ],
            'doi': [
                toolkit.get_converter('convert_from_extras'),
                toolkit.get_validator('ignore_missing'),
                toolkit.get_validator('unicode_safe'),
            ],
            'references': [
                toolkit.get_converter('convert_from_extras'),
                toolkit.get_validator('ignore_missing'),
                toolkit.get_validator('unicode_safe'),
            ],
        })
        schema['resources'].update({
            'sha256': [
                toolkit.get_validator('ignore_missing'),
            ],
        })
        # Add dclab configuration parameters
        for sec in dclab.dfn.CFG_METADATA:
            for key in dclab.dfn.config_keys[sec]:
                schema['resources'].update({
                    'dc:{}:{}'.format(sec, key): [
                        toolkit.get_validator('ignore_missing'),
                    ]})
        return schema

    def is_fallback(self):
        # Return True to register this plugin as the default handler for
        # package types not handled by any other IDatasetForm plugin.
        return True

    def package_types(self):
        # This plugin doesn't handle any special package types, it just
        # registers itself as the default (above).
        return []

    # IPermissionLabels
    def get_dataset_labels(self, dataset_obj):
        u'''
        Add labels according to groups the dataset is part of.
        '''
        labels = super(DCORDatasetFormPlugin, self).get_dataset_labels(
            dataset_obj)
        groups = dataset_obj.get_groups()
        labels += [u'group-%s' % grp.id for grp in groups]
        return labels

    def get_user_dataset_labels(self, user_obj):
        u'''
        Include group labels (If user is part of a group, then he
        should be able to see all private datasets therein).
        '''
        labels = super(DCORDatasetFormPlugin, self
                       ).get_user_dataset_labels(user_obj)
        if user_obj:
            grps = logic.get_action("group_list_authz")(
                {u'user': user_obj.id}, {})
            labels.extend(u'group-%s' % o['id'] for o in grps)
        return labels

    # IResourceController
    def after_create(self, context, resource):
        """Generate sha256 hash"""
        path = get_dataset_path(context, resource)
        toolkit.enqueue_job(set_sha256_job, [path, resource])
        toolkit.enqueue_job(set_dc_config_job, [path, resource])

    def before_create(self, context, resource):
        # set the filename
        if "upload" in resource:
            filename = resource["upload"].filename
            resource["name"] = filename

    def before_update(self, context, current, resource):
        """We have to do this to protect our resource metadata"""
        for key in ["sha256"]:
            if key in current:
                resource[key] = current[key]

    # ITemaplateHelpers
    def get_helpers(self):
        # Template helper function names should begin with the name of the
        # extension they belong to, to avoid clashing with functions from
        # other extensions.
        hlps = {
            'dcor_schemas_get_user_name': dcor_helpers.get_user_name,
            'dcor_schemas_get_reference_dict': dcor_helpers.get_reference_dict,
            'dcor_schemas_license_options': dcor_helpers.license_options,
        }
        return hlps
