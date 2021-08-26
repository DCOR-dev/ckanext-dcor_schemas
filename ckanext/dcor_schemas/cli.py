import time

import ckan.model as model

import click


from . import jobs


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
            # don't delete users with datasets
            continue
        # user has activities?
        activity_objects = model.activity.user_activity_list(
            user.id, limit=1, offset=0)
        if activity_objects:
            stamp = activity_objects[0].timestamp.timestamp()
            if stamp >= (time.time() - 60*60*24*7*last_activity_weeks):
                # don't delete users that did things
                continue
        click.echo(user.name)


@click.command()
def run_jobs_dcor_schemas():
    """Set SHA256 sums for all resources (including draft datasets)"""
    # go through all datasets
    datasets = model.Session.query(model.Package)
    nl = False  # new line character
    for dataset in datasets:
        click.echo(f"Checking dataset {dataset.id}\r", nl=False)
        for resource in dataset.resources:
            res_dict = resource.as_dict()
            if jobs.set_format_job(res_dict):
                click.echo("")
                nl = True
                click.echo(f"Updated format for {resource.name}")
            if jobs.set_sha256_job(res_dict):
                if not nl:
                    click.echo("")
                    nl = True
                click.echo(f"Updated SHA256 for {resource.name}")
            if jobs.set_dc_config_job(res_dict):
                if not nl:
                    click.echo("")
                click.echo(f"Updated config for {resource.name}")
    if not nl:
        click.echo("")
    click.echo("Done!")


def get_commands():
    return [list_zombie_users,
            run_jobs_dcor_schemas]
