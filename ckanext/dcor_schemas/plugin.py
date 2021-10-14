import copy
import mimetypes
import pathlib
import sys

from ckan.common import config
from ckan.lib.plugins import DefaultPermissionLabels
from ckan import common, logic
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit

import dclab
from dcor_shared import DC_MIME_TYPES

from . import actions
from . import auth as dcor_auth
from .cli import get_commands
from . import jobs
from . import helpers as dcor_helpers
from . import resource_schema_supplements as rss
from . import validate as dcor_validate


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


class DCORDatasetFormPlugin(plugins.SingletonPlugin,
                            toolkit.DefaultDatasetForm,
                            DefaultPermissionLabels):
    """This plugin makes views of DC data"""
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IClick)
    plugins.implements(plugins.IConfigurer, inherit=True)
    plugins.implements(plugins.IDatasetForm)
    plugins.implements(plugins.IPermissionLabels)
    plugins.implements(plugins.IResourceController, inherit=True)
    plugins.implements(plugins.ITemplateHelpers)

    # IActions
    def get_actions(self):
        return {
            "resource_schema_supplements":
                actions.get_resource_schema_supplements,
            "supported_resource_suffixes":
                actions.get_supported_resource_suffixes,
        }

    # IAuthfunctions
    def get_auth_functions(self):
        # - `*_patch` has same authorization as `*_update`
        # - If you are wondering why group_create and organization_create
        #   are not here, it's because authz.py always checks whether
        #   anonymous access is allowed via the auth_allow_anonymous_access
        #   flag. So we just leave it at the defaults.
        return {
            'bulk_update_delete': dcor_auth.deny,
            'dataset_purge': dcor_auth.dataset_purge,
            'package_create': dcor_auth.package_create,
            'package_delete': dcor_auth.package_delete,
            'package_update': dcor_auth.package_update,
            'resource_create': dcor_auth.resource_create,
            'resource_delete': dcor_auth.deny,
            'resource_update': dcor_auth.resource_update,
        }

    # IClick
    def get_commands(self):
        return get_commands()

    # IConfigurer
    def update_config(self, config):
        # Add this plugin's templates dir to CKAN's extra_template_paths, so
        # that CKAN will use this plugin's custom templates.
        toolkit.add_template_directory(config, 'templates')
        toolkit.add_resource('assets', 'dcor_schemas')
        # Add RT-DC mime types
        for key in DC_MIME_TYPES:
            mimetypes.add_type(key, DC_MIME_TYPES[key])
        # Set licenses path if no licenses_group_url was given
        if not common.config.get("licenses_group_url", ""):
            # Workaround for https://github.com/ckan/ckan/issues/5580
            # Only update the configuration options when we are not
            # trying to do anything with the database (e.g. `ckan db clean`).
            if not sys.argv.count("db"):
                # use default license location from dcor_schemas
                here = pathlib.Path(__file__).parent
                license_loc = "file://{}".format(here / "licenses.json")
                toolkit.get_action('config_option_update')(
                    context={'ignore_auth': True, 'user': None},
                    data_dict={'licenses_group_url': license_loc}
                )

    def update_config_schema(self, schema):
        ignore_missing = toolkit.get_validator('ignore_missing')
        if not common.config.get("licenses_group_url", ""):
            # Only update the schema if no licenses_group_url was given
            schema.update({
                # This is an existing CKAN core configuration option, we are
                # just making it available to be editable at runtime
                'licenses_group_url': [ignore_missing],
            })
        return schema

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
                dcor_validate.dataset_authors,
                toolkit.get_validator('not_empty'),
                toolkit.get_converter('convert_to_extras'),
            ],
            'doi': [
                toolkit.get_validator('ignore_missing'),
                dcor_validate.dataset_doi,
                toolkit.get_validator('unicode_safe'),
                toolkit.get_converter('convert_to_extras'),
            ],
            'license_id': [
                dcor_validate.dataset_license_id,
            ],
            'references': [
                toolkit.get_validator('ignore_missing'),
                dcor_validate.dataset_references,
                toolkit.get_validator('unicode_safe'),
                toolkit.get_converter('convert_to_extras'),
            ],
            'state': [
                toolkit.get_validator('ignore_missing'),
                dcor_validate.dataset_state,
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
        # Add supplementary resource schemas
        for composite_key in rss.get_composite_item_list():
            schema['resources'].update({
                composite_key: [
                    toolkit.get_validator('ignore_missing'),
                    dcor_validate.resource_dc_supplement,
                ]})

        return schema

    def create_package_schema(self):
        schema = super(DCORDatasetFormPlugin, self).create_package_schema()
        schema = self._modify_package_schema(schema)
        schema.update({
            'name': [
                toolkit.get_validator('unicode_safe'),
                dcor_validate.dataset_name_create,
            ],
        })

        return schema

    def update_package_schema(self):
        schema = super(DCORDatasetFormPlugin, self).update_package_schema()
        schema = self._modify_package_schema(schema)
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
        # Add supplementary resource schemas
        for composite_key in rss.get_composite_item_list():
            schema['resources'].update({
                composite_key: [
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
        """
        Add labels according to groups the dataset is part of.
        """
        labels = super(DCORDatasetFormPlugin, self).get_dataset_labels(
            dataset_obj)
        groups = dataset_obj.get_groups()
        labels += [u'group-%s' % grp.id for grp in groups]
        return labels

    def get_user_dataset_labels(self, user_obj):
        """
        Include group labels (If user is part of a group, then he
        should be able to see all private datasets therein).
        """
        labels = super(DCORDatasetFormPlugin, self
                       ).get_user_dataset_labels(user_obj)
        if user_obj:
            grps = logic.get_action("group_list_authz")(
                {u'user': user_obj.id}, {})
            labels.extend(u'group-%s' % o['id'] for o in grps)
        return labels

    # IResourceController
    def after_create(self, context, resource):
        """Add custom jobs"""
        # It turns out that package_revise might not be as atomic as I
        # thought (because it also calls package_show). Therefore, we
        # make all the jobs that interact with the database sequential.
        depends_on = []
        extensions = [config.get("ckan.plugins")]

        for ii in range(resource['position']):
            # depend on completion of previous resources
            depends_on.append(f"{resource['package_id']}_{ii}_sha256")

        package_job_id = f"{resource['package_id']}_{resource['position']}_"

        # Are we waiting for symlinking (ckanext-dcor_depot)?
        # (This makes wait_for_resource really fast ;)
        if "dcor_depot" in extensions:
            # Wait for the resource to be moved to the depot.
            jid_sl = package_job_id + "symlink"
            depends_on.append(jid_sl)

        # Add the fast jobs first.
        if resource.get('mimetype') in DC_MIME_TYPES:
            jid_form = package_job_id + "format"
            toolkit.enqueue_job(jobs.set_format_job,
                                [resource],
                                title="Set mimetype for resource",
                                queue="dcor-short",
                                rq_kwargs={
                                    "timeout": 500,
                                    "job_id": jid_form,
                                    "depends_on": copy.copy(depends_on)})
            depends_on.append(jid_form)

            jid_par = package_job_id + "dcparms"
            toolkit.enqueue_job(jobs.set_dc_config_job,
                                [resource],
                                title="Set DC parameters for resource",
                                queue="dcor-normal",
                                rq_kwargs={
                                    "timeout": 500,
                                    "job_id": jid_par,
                                    "depends_on": copy.copy(depends_on)})
            depends_on.append(jid_par)

        # The SHA256 job comes last.
        toolkit.enqueue_job(jobs.set_sha256_job,
                            [resource],
                            title="Set SHA256 hash for resource",
                            queue="dcor-normal",
                            rq_kwargs={"timeout": 3600,
                                       "job_id": package_job_id + "sha256",
                                       "depends_on": copy.copy(depends_on)})

    def before_create(self, context, resource):
        if "upload" in resource:
            # set/override the filename
            upload = resource["upload"]
            if hasattr(upload, "filename"):
                filename = upload.filename
            elif hasattr(upload, "name"):
                filename = pathlib.Path(upload.name).name
            resource["name"] = filename

    # ITemplateHelpers
    def get_helpers(self):
        # Template helper function names should begin with the name of the
        # extension they belong to, to avoid clashing with functions from
        # other extensions.
        hlps = {
            'dcor_schemas_get_user_name': dcor_helpers.get_user_name,
            'dcor_schemas_get_reference_dict': dcor_helpers.get_reference_dict,
            'dcor_schemas_license_options': dcor_helpers.license_options,
            'dcor_schemas_get_composite_section_item_list':
            rss.get_composite_section_item_list
        }
        return hlps
