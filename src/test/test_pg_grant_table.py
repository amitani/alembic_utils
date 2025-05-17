import pytest
from sqlalchemy import text

from alembic_utils.exceptions import BadInputException
from alembic_utils.pg_grant_table import PGGrantTable, PGGrantTableChoice
from alembic_utils.replaceable_entity import register_entities
from alembic_utils.testbase import TEST_VERSIONS_ROOT, run_alembic_command


@pytest.fixture(scope="function")
def sql_setup(engine):
    with engine.begin() as connection:
        connection.execute(
            text(
                """
        create table public.account (
            id serial primary key,
            email text not null
        );
        create role anon_user
        """
            )
        )

    yield
    with engine.begin() as connection:
        connection.execute(text("drop table public.account cascade"))


def _pg_grant_table(
    schema: str = "public",
    table: str = "account",
    role: str = "anon_user",
    grant: PGGrantTableChoice = PGGrantTableChoice.SELECT,
    columns: list[str] | None = None,
    with_grant_option: bool = False,
) -> PGGrantTable:
    """Helper function to create a PGGrantTable object with defaults."""
    return PGGrantTable(
        schema=schema,
        table=table,
        role=role,
        grant=grant,
        columns=columns,
        with_grant_option=with_grant_option,
    )


def test_repr():
    go = PGGrantTableChoice("TRUNCATE")
    assert go.__repr__() == "'TRUNCATE'"


def test_bad_input():

    with pytest.raises(BadInputException):
        PGGrantTable(
            schema="public",
            table="account",
            role="anon_user",
            grant=PGGrantTableChoice.DELETE,
            columns=["id"],  # columns not allowed for delete
        )

@pytest.mark.parametrize("role", ["anon_user", "PUBLIC"])
def test_create_revision(sql_setup, engine, role) -> None:
    register_entities([_pg_grant_table(role=role)], entity_types=[PGGrantTable])
    run_alembic_command(
        engine=engine,
        command="revision",
        command_kwargs={"autogenerate": True, "rev_id": "1", "message": "create"},
    )

    migration_create_path = TEST_VERSIONS_ROOT / "1_create.py"

    with migration_create_path.open() as migration_file:
        migration_contents = migration_file.read()

    assert migration_contents.count("op.create_entity") == 1
    assert migration_contents.count("op.drop_entity") == 1
    assert "op.replace_entity" not in migration_contents
    assert "from alembic_utils.pg_grant_table import PGGrantTable" in migration_contents

    # Execute upgrade
    run_alembic_command(engine=engine, command="upgrade", command_kwargs={"revision": "head"})
    # Execute Downgrade
    run_alembic_command(engine=engine, command="downgrade", command_kwargs={"revision": "base"})


@pytest.mark.parametrize("role", ["anon_user", "PUBLIC"])
def test_replace_revision(sql_setup, engine, role) -> None:
    with engine.begin() as connection:
        connection.execute(_pg_grant_table(role=role).to_sql_statement_create())

    register_entities([_pg_grant_table(role=role, columns=["id"])], entity_types=[PGGrantTable])
    run_alembic_command(
        engine=engine,
        command="revision",
        command_kwargs={"autogenerate": True, "rev_id": "2", "message": "update"},
    )

    migration_create_path = TEST_VERSIONS_ROOT / "2_update.py"

    with migration_create_path.open() as migration_file:
        migration_contents = migration_file.read()

    # Granting can not be done in place.
    assert migration_contents.count("op.replace_entity") == 2
    assert "op.create_entity" not in migration_contents
    assert "op.drop_entity" not in migration_contents
    assert "from alembic_utils.pg_grant_table import PGGrantTable" in migration_contents

    # Execute upgrade
    run_alembic_command(engine=engine, command="upgrade", command_kwargs={"revision": "head"})
    # Execute Downgrade
    run_alembic_command(engine=engine, command="downgrade", command_kwargs={"revision": "base"})

@pytest.mark.parametrize("role", ["anon_user", "PUBLIC"])
def test_create_revision_with_grant_option(sql_setup, engine, role) -> None:
    test_grant = _pg_grant_table(role=role)
    # Create the view outside of a revision
    with engine.begin() as connection:
        connection.execute(test_grant.to_sql_statement_create())

    register_entities([test_grant], entity_types=[PGGrantTable])

    # Create a third migration without making changes.
    # This should result in no create, drop or replace statements
    run_alembic_command(engine=engine, command="upgrade", command_kwargs={"revision": "head"})

    output = run_alembic_command(
        engine=engine,
        command="revision",
        command_kwargs={"autogenerate": True, "rev_id": "3", "message": "do_nothing"},
    )
    migration_do_nothing_path = TEST_VERSIONS_ROOT / "3_do_nothing.py"

    with migration_do_nothing_path.open() as migration_file:
        migration_contents = migration_file.read()

    assert "op.create_entity" not in migration_contents
    assert "op.drop_entity" not in migration_contents
    assert "op.replace_entity" not in migration_contents
    assert "from alembic_utils" not in migration_contents

    # Execute upgrade
    run_alembic_command(engine=engine, command="upgrade", command_kwargs={"revision": "head"})
    # Execute Downgrade
    run_alembic_command(engine=engine, command="downgrade", command_kwargs={"revision": "base"})

@pytest.mark.parametrize("role", ["anon_user", "PUBLIC"])
def test_drop_revision(sql_setup, engine, role) -> None:

    # Register no functions locally
    register_entities([], schemas=["public"], entity_types=[PGGrantTable])

    # Manually create a SQL function
    with engine.begin() as connection:
        connection.execute(_pg_grant_table(role=role).to_sql_statement_create())

    output = run_alembic_command(
        engine=engine,
        command="revision",
        command_kwargs={"autogenerate": True, "rev_id": "1", "message": "drop"},
    )

    migration_create_path = TEST_VERSIONS_ROOT / "1_drop.py"

    with migration_create_path.open() as migration_file:
        migration_contents = migration_file.read()

    # import pdb; pdb.set_trace()

    assert migration_contents.count("op.drop_entity") == 1
    assert migration_contents.count("op.create_entity") == 1
    assert "from alembic_utils" in migration_contents
    assert migration_contents.index("op.drop_entity") < migration_contents.index("op.create_entity")

    # Execute upgrade
    run_alembic_command(engine=engine, command="upgrade", command_kwargs={"revision": "head"})
    # Execute Downgrade
    run_alembic_command(engine=engine, command="downgrade", command_kwargs={"revision": "base"})
