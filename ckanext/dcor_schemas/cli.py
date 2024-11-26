import datetime
import sys
import time
import traceback

import ckan.model as model
import ckan.plugins.toolkit as toolkit
import click
from dcor_shared import s3, s3cc
from dcor_shared import RQJob  # noqa: F401

from . import jobs


def admin_context():
    return {'ignore_auth': True, 'user': 'default'}


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
        # print the list of resources of that group
        query = model.meta.Session.query(model.package.Package).\
            filter(model.group.group_table.c["id"] == group.id)
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


@click.option('--modified-days', default=-1,
              help='Only run for datasets modified within this number of days '
                   + 'in the past. Set to -1 to apply to all datasets.')
@click.command()
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


def get_commands():
    return [
        dcor_move_dataset_to_circle,
        list_circles,
        list_collections,
        list_group_resources,
        list_zombie_users,
        run_jobs_dcor_schemas]
