import time

import ckan.model as model

import click


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
                # dont't delete users that did things
                continue
        click.echo(user.name)


def get_commands():
    return [list_zombie_users]
