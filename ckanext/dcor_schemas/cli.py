import datetime
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

    nl = False  # new line character
    for dataset in datasets:
        nl = False
        click.echo(f"Checking dataset {dataset.id}\r", nl=False)
        for resource in dataset.resources:
            res_dict = resource.as_dict()
            if jobs.set_format_job(res_dict):
                if not nl:
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
