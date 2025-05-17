import pytest

from alembic_utils.exceptions import BadInputException
from alembic_utils.pg_function import PGFunction
from alembic_utils.pg_grant_table import PGGrantTable, PGGrantTableChoice
from alembic_utils.replaceable_entity import register_entities, registry
from alembic_utils.testbase import run_alembic_command


def to_upper():
    return PGFunction(
        schema="public",
        signature="to_upper(some_text text)",
        definition="""
        returns text
        as
        $$ select upper(some_text) || 'abc' $$ language SQL;
        """,
    )


def test_migration_create_function(engine) -> None:
    to_upper1 = to_upper()
    to_upper2 = to_upper()
    register_entities([to_upper1, to_upper2], entity_types=[PGFunction])

    entities = registry.entities()
    assert len(entities) == 1
    assert entities[0] == to_upper2

    run_alembic_command(
        engine=engine,
        command="revision",
        command_kwargs={"autogenerate": True, "rev_id": "1", "message": "raise"},
    )

def test_table_grant_to_table_and_column_raises(engine) -> None:
    table_grant = PGGrantTable(
        schema="public",
        table="account",
        role="anon_user",
        grant=PGGrantTableChoice.SELECT,
        with_grant_option=False,
    )

    column_grant = PGGrantTable(
        schema="public",
        table="account",
        columns=["id", "email"],
        role="anon_user",
        grant=PGGrantTableChoice.SELECT,
        with_grant_option=False,
    )

    with pytest.raises(BadInputException):
        register_entities([table_grant, column_grant], entity_types=[PGGrantTable])
