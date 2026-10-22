import datetime
import pathlib
import sys
import time
import traceback

from ckan import logic
from ckan.lib import mailer
import ckan.model as model
import ckan.plugins.toolkit as toolkit
import click
from dcor_shared import s3, s3cc, get_ckan_config_option
from dcor_shared import RQJob  # noqa: F401

from . import jobs


def admin_context():
    return {'ignore_auth': True, 'user': 'default'}


def iter_group_resources(group_id):
    # print the list of resources of that group
    query = model.meta.Session.query(model.package.Package). \
        filter(model.group.group_table.c["id"] == group_id)
    # copy-pasted from CKAN's model.group.Group.packages()
    query = query.join(
        model.group.member_table,
        model.group.member_table.c["table_id"] == model.package.Package.id)
    query = query.join(
        model.group.group_table,
        model.group.group_table.c["id"]
        == model.group.member_table.c["group_id"])

    for dataset in query.all():
        for resource in dataset.resources:
            yield resource


@click.command()
@click.argument("dataset")
@click.argument("circle")
def dcor_move_dataset_to_circle(dataset, circle):
    """Move a dataset to a different circle

    Moving a dataset to a new circle implies:
    - copying the resource files from the old S3 bucket to the new
      S3 bucket (verifying SHA256sum)
    - setting the public flag (if applicable)
    - setting the "owner_org" of the dataset to the new circle ID
    - updating the "s3_url" metadata of each resource to the new S3 URL
    - deleting the resource files in the old S3 bucket

    Notes
    -----
    There is an issue in CKAN where the resources of the dataset still
    show up in the old organization when calling `package_owner_org_update`:
    https://github.com/ckan/ckan/issues/8249
    """
    ds_dict = toolkit.get_action("package_show")(
        admin_context(), {"id": dataset})
    cr_old = toolkit.get_action("organization_show")(
        admin_context(), {"id": ds_dict["owner_org"]})
    cr_new = toolkit.get_action("organization_show")(
        admin_context(), {"id": circle})

    if cr_old["id"] == cr_new["id"]:
        print(f"Dataset already in {cr_new['id']}")
        return

    s3_client, _, _ = s3.get_s3()

    # Copy resource files to new bucket
    to_delete = []
    for rs_dict in ds_dict["resources"]:
        rid = rs_dict["id"]
        rsha = rs_dict["sha256"]
        for art in ["condensed", "preview", "resource"]:
            if not s3cc.artifact_exists(rid, art):
                continue
            bucket_old, obj = s3cc.get_s3_bucket_object_for_artifact(rid, art)
            bucket_new = bucket_old.replace(cr_old["id"], cr_new["id"])
            assert bucket_old != bucket_new, "sanity check"
            # copy the resource to the destination bucket
            s3.require_bucket(bucket_new)
            copy_source = {'Bucket': bucket_old, 'Key': obj}
            s3_client.copy(copy_source, bucket_new, obj)
            # verify checksum
            if art == "resource":
                assert s3.compute_checksum(bucket_new, obj) == rsha
            else:
                assert s3.compute_checksum(bucket_new, obj) \
                    == s3.compute_checksum(bucket_old, obj)
            # set to public if applicable
            if not ds_dict["private"]:
                s3.make_object_public(bucket_name=bucket_new,
                                      object_name=obj,
                                      missing_ok=False)
            print(f"...copied S3 object {rid}:{art}")
            to_delete.append([bucket_old, obj])

    # Set owner org of dataset to new circle ID
    toolkit.get_action("package_owner_org_update")(
        admin_context(), {"id": ds_dict["id"],
                          "organization_id": cr_new["id"]
                          }
    )
    print("...updated owner_org")

    # Update the "s3_url" for all resources
    res_update = []
    for rs_dict in ds_dict["resources"]:
        url_old = rs_dict["s3_url"]
        url_new = url_old.replace(cr_old["id"], cr_new["id"])
        res_update.append({"s3_url": url_new})

    toolkit.get_action("package_revise")(
        admin_context(),
        {"match": {"id": ds_dict["id"]}, "update": {"resources": res_update}}
    )
    print("...updated s3_urls")

    # make sure editing the database worked
    ds_dict_new = toolkit.get_action("package_show")(
        admin_context(), {"id": dataset})
    assert ds_dict_new["owner_org"] == cr_new["id"]
    for res in ds_dict_new["resources"]:
        assert res["s3_url"].count(cr_new["id"])

    # Delete the resource files in the old S3 bucket
    for bucket, key in to_delete:
        s3_client.delete_object(Bucket=bucket, Key=key)
    print("...deleted old S3 objects")


@click.command()
@click.option('--older-than-days', default=21,
              help='Only prune datasets that were created before a given '
                   + 'number of days (set to -1 to prune all)')
@click.option('--dry-run', is_flag=True,
              help='Do not actually remove anything')
def dcor_prune_draft_datasets(older_than_days=21, dry_run=False):
    """Remove draft datasets from the CKAN database"""
    # Iterate over all packages
    # data_dict will be overridden each time it is used
    query = (
        model.meta.Session.query(model.package.Package)
        # all inactive datasets
        .filter(model.package.Package.state != model.core.State.ACTIVE)
    )

    ds_found = 0
    ds_ignored = 0

    package_delete = logic.get_action('package_delete')
    dataset_purge = logic.get_action('dataset_purge')

    for dataset in query.all():
        if not dataset.state == "draft":
            ds_ignored += 1
            continue
        threshold = (datetime.datetime.now()
                     - datetime.timedelta(days=older_than_days))
        if dataset.metadata_modified < threshold:
            ds_found += 1
            click.secho(f"Found dataset {dataset.name}")
            if not dry_run:
                package_delete(context=admin_context(),
                               data_dict={'id': dataset.id})
                dataset_purge(context=admin_context(),
                              data_dict={'id': dataset.id})
        else:
            ds_ignored += 1

    click.secho(f"Number of draft datasets found:   {ds_found}")
    click.secho(f"Number of draft datasets ignored: {ds_ignored}")
    click.secho("Done!")


@click.command()
@click.option('--older-than-days', default=21,
              help='Only prune artifacts that were created before a given '
                   + 'number of days (set to -1 to prune all)')
@click.option('--keep-orphan-buckets', is_flag=True,
              help='Keep buckets that do not represent a circle')
@click.option('--dry-run', is_flag=True,
              help='Do not actually remove anything')
def dcor_prune_orphaned_s3_artifacts(older_than_days=21,
                                     keep_orphan_buckets=False,
                                     dry_run=False):
    """Remove resources from S3 that are not in the CKAN database"""
    s3_client, _, _ = s3.get_s3()
    buckets_exist = sorted(s3.iter_buckets())
    buckets_used = []
    obj_found = 0
    for grp in model.Group.all():
        if grp.is_organization:
            org_bucket = get_ckan_config_option(
                "dcor_object_store.bucket_name").format(organization_id=grp.id)
            buckets_used.append(org_bucket)
            # List of resources in that circle
            resources = [r.id for r in iter_group_resources(grp.id)]
            # Iterate over present objects and remove when necessary
            for obj in s3.iter_bucket_objects(
                    bucket_name=org_bucket,
                    older_than_days=older_than_days):
                rid = "".join(obj.split("/")[1:])
                if rid not in resources:
                    obj_found += 1
                    click.secho(f"Found object {org_bucket}:{obj}")
                    if not dry_run:
                        s3_client.delete_object(Bucket=org_bucket,
                                                Key=obj)

    # Remove orphaned buckets
    if not keep_orphan_buckets:
        for bucket_name in buckets_exist:
            if bucket_name not in buckets_used:
                click.secho(f"Found bucket {bucket_name}")
                if not dry_run:
                    for obj in s3.iter_bucket_objects(bucket_name):
                        s3_client.delete_object(Bucket=bucket_name,
                                                Key=obj)
                    try:
                        s3_client.delete_bucket(Bucket=bucket_name)
                    except s3_client.exceptions.NoSuchBucket:
                        # bucket has been deleted in the meantime
                        pass
    click.secho(f"Number of orphaned objects found: {obj_found}")
    click.secho("Done!")


@click.command()
@click.option('--keep-circle', multiple=True,
              help='Name or ID of a circle that should be kept together '
                   'with its datasets (may be specified multiple times)')
@click.option('--user-inactive-days', default=7, type=int,
              help='Remove users with datasets that were not active within '
                   'this number of days (users without datasets are always '
                   'removed)')
@click.option('--dry-run', is_flag=True,
              help='Do not actually remove anything')
@click.confirmation_option(
    prompt="This removes all users, datasets, collections, and circles. "
           "Are you certain?")
@click.pass_context
def dcor_purge_all(ctx,
                   keep_circle: tuple[str] = (),
                   user_inactive_days: int = 7,
                   dry_run: bool = False):
    """Purge users, datasets, collections, and circles

    This command is meant for resetting development instances such as
    DCOR-dev. It only runs if the configuration option
    `ckanext.dcor_schemas.allow_purge_all` is set to true.

    1. Remove all users that are not sysadmins and that either have
       no datasets or that have datasets but were not active within
       `--user-inactive-days` days. Users are evaluated before the
       datasets are purged.
    2. Purge all datasets (active, draft, and deleted), except for those
       in the circles specified via `--keep-circle`.
    3. Purge all collections.
    4. Purge all circles, except for those specified via `--keep-circle`.
    """
    if not toolkit.asbool(get_ckan_config_option(
            "ckanext.dcor_schemas.allow_purge_all")):
        click.secho("Purging everything is not allowed on this instance. "
                    "Set `ckanext.dcor_schemas.allow_purge_all = true` in "
                    "the CKAN configuration (development instances only).",
                    fg="red")
        return sys.exit(1)

    site_user = logic.get_action("get_site_user")({"ignore_auth": True}, {})
    context = {"ignore_auth": True, "user": site_user["name"]}

    # circles to keep
    keep_ids = []
    for name in keep_circle:
        grp = model.Group.get(name)
        if grp is None or not grp.is_organization:
            click.secho(f"Circle '{name}' does not exist", fg="yellow")
        else:
            keep_ids.append(grp.id)

    # 1. users
    threshold = (datetime.datetime.utcnow()
                 - datetime.timedelta(days=user_inactive_days))
    user_names = []
    for user in model.User.all():
        if user.sysadmin or user.state == model.core.State.DELETED:
            continue
        has_datasets = user.number_created_packages(
            include_private_and_draft=True) > 0
        inactive = user.last_active is None or user.last_active < threshold
        if not has_datasets or inactive:
            user_names.append(user.name)
    with ctx.meta["flask_app"].test_request_context():
        for name in user_names:
            click.echo(f"Remove user {name}")
            if not dry_run:
                logic.get_action("user_delete")(dict(context), {"id": name})

    # 2. datasets
    dataset_ids = [ds.id for ds in model.Session.query(model.Package)
                   if ds.owner_org not in keep_ids]
    package_delete = logic.get_action("package_delete")
    dataset_purge = logic.get_action("dataset_purge")
    for ds_id in dataset_ids:
        click.echo(f"Purge dataset {ds_id}")
        if not dry_run:
            if model.Package.get(ds_id).state != model.core.State.DELETED:
                package_delete(dict(context), {"id": ds_id})
            dataset_purge(dict(context), {"id": ds_id})

    # 3. collections and 4. circles (including deleted ones)
    groups = [(grp.id, grp.is_organization)
              for grp in model.Session.query(model.Group)
              if grp.id not in keep_ids]
    for group_id, is_org in sorted(groups, key=lambda x: x[1]):
        if is_org:
            click.echo(f"Purge circle {group_id}")
            purge_method = logic.get_action("organization_purge")
        else:
            click.echo(f"Purge collection {group_id}")
            purge_method = logic.get_action("group_purge")
        if not dry_run:
            purge_method(dict(context), {"id": group_id})

    click.secho(f"Users removed: {len(user_names)}, "
                f"datasets purged: {len(dataset_ids)}, "
                f"collections purged: {len([g for g in groups if not g[1]])}, "
                f"circles purged: {len([g for g in groups if g[1]])}"
                + (" (dry run)" if dry_run else ""))
    click.secho("Done!")


@click.command()
def list_circles():
    """List all circles/organizations"""
    groups = model.Group.all()
    for grp in groups:
        if grp.is_organization:
            click.echo(f"{grp.id}\t{grp.name}\t({grp.title})")


@click.command()
def list_collections():
    """List all collections/groups"""
    groups = model.Group.all()
    for grp in groups:
        if not grp.is_organization:
            click.echo(f"{grp.id}\t{grp.name}\t({grp.title})")


@click.command()
@click.argument("group_id_or_name")
def list_group_resources(group_id_or_name):
    """List all resources (active/draft/deleted) for a circle or collection"""
    # We cannot just use model.group.Group.packages(), because this does
    # not include resources from draft or deleted datasets.
    group = model.Group.get(group_id_or_name)
    if group is None:
        click.secho(f"Group '{group_id_or_name}' not found", fg="red")
        return sys.exit(1)
    else:
        for resource in iter_group_resources(group.id):
            click.echo(resource.id)


@click.option('--last-activity-weeks', default=12,
              help='Only list users with no activity for X weeks')
@click.command()
def list_zombie_users(last_activity_weeks=12):
    """List zombie users (no activity, no datasets)"""
    users = model.User.all()
    for user in users:
        # user is admin?
        if user.sysadmin:
            continue
        # user has datasets?
        if user.number_created_packages(include_private_and_draft=True) != 0:
            # don't list users with datasets
            continue
        # user has been active?
        if (user.last_active is not None
                and user.last_active.timestamp() >= (
                    time.time() - 60*60*24*7*last_activity_weeks)):
            # don't delete users that did things
            continue
        click.echo(user.name)


@click.command()
@click.option('--modified-days', default=-1,
              help='Only run for datasets modified within this number of days '
                   + 'in the past. Set to -1 to apply to all datasets.')
def run_jobs_dcor_schemas(modified_days=-1):
    """Set .rtdc metadata and SHA256 sums and for all resources

    This also happens for draft datasets.
    """
    datasets = model.Session.query(model.Package)

    if modified_days >= 0:
        # Search only the last `days` days.
        past = datetime.date.today() - datetime.timedelta(days=modified_days)
        past_str = time.strftime("%Y-%m-%d", past.timetuple())
        datasets = datasets.filter(model.Package.metadata_modified >= past_str)

    job_list = jobs.RQJob.get_all_job_methods_in_order(
        ckanext="dcor_schemas")

    nl = False  # new line character
    for dataset in datasets:
        nl = False
        click.echo(f"Checking dataset {dataset.id}\r", nl=False)

        for resource in dataset.resources:
            res_dict = resource.as_dict()
            try:
                for job in job_list:
                    if job.method(res_dict):
                        if not nl:
                            click.echo("")
                            nl = True
                        click.echo(f"OK: {job.title} for {resource.name}")
            except KeyboardInterrupt:
                raise
            except BaseException as e:
                click.echo(
                    f"\n{e.__class__.__name__} for {res_dict['name']}!",
                    err=True)
                click.echo(traceback.format_exc(), err=True)
                nl = True
    if not nl:
        click.echo("")
    click.echo("Done!")


@click.command()
@click.option('--recipient', type=str)
@click.option('--subject', type=str, default="DCOR Email")
@click.option('--file_body',
              type=click.Path(exists=True,
                              dir_okay=False,
                              resolve_path=True,
                              path_type=pathlib.Path),
              default=None,
              )
def send_mail(recipient, subject=None, file_body=None):
    """Send email to `recipient` with `subject` with content of `file_body`

    The SMTP settings of the CKAN instance are used to send the email.
    """
    if not recipient:
        raise ValueError("No recipient specified")
    click.echo(f"Sending mail to {recipient} with subject {subject}")
    mailer.mail_recipient(
        recipient_name=recipient,
        recipient_email=recipient,
        subject=subject,
        body=file_body.read_text(errors="ignore"),
    )
    click.echo("Done!")


def get_commands():
    return [
        dcor_move_dataset_to_circle,
        dcor_prune_draft_datasets,
        dcor_prune_orphaned_s3_artifacts,
        dcor_purge_all,
        list_circles,
        list_collections,
        list_group_resources,
        list_zombie_users,
        run_jobs_dcor_schemas,
        send_mail,
    ]
