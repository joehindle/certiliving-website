import psycopg
from psycopg.rows import dict_row

import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    if 'db' not in g:
        g.db = psycopg.connect(
            current_app.config['DATABASE_URL'],
            row_factory=dict_row,
            autocommit=False,
        )

    return g.db


def close_db(_error=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()


def init_db():
    db = get_db()

    with current_app.open_resource('schema.sql') as f:
        db.execute(f.read().decode('utf8'))
        db.commit()


@click.command('init-db')
@with_appcontext
def init_db_command():
    init_db()
    click.echo('Database initialized (non-destructive).')


@click.command('reset-db')
@click.option(
    '--yes',
    is_flag=True,
    help='Confirm destructive reset (drops existing tables).',
)
@with_appcontext
def reset_db_command(yes):
    if not yes:
        raise click.UsageError(
            "Refusing to reset database without --yes. "
            "This command is destructive and will drop all data."
        )

    if not click.confirm(
        'This will permanently delete all listings and enquiries. Continue?'
    ):
        click.echo('Reset cancelled.')
        return

    db = get_db()
    db.execute('DROP TABLE IF EXISTS enquiries')
    db.execute('DROP TABLE IF EXISTS listings')
    db.commit()

    init_db()
    click.echo('Database reset and re-initialized.')


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(reset_db_command)
