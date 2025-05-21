from alembic_utils.pg_function import PGFunction
from alembic_utils.replaceable_entity import register_entities
from alembic_utils.testbase import TEST_VERSIONS_ROOT, run_alembic_command

TO_UPPER = PGFunction(
    schema="public",
    signature="to_upper(some_text text)",
    definition="""
        returns text
        as
        $$ select upper(some_text) || 'abc' $$ language SQL;
        """,
)


def test_migration_create_function(engine) -> None:
    register_entities([TO_UPPER], entity_types=[PGFunction])
    output = run_alembic_command(
        engine=engine,
        command="revision",
        command_kwargs={"autogenerate": True, "rev_id": "1", "message": "create"},
    )

    migration_create_path = TEST_VERSIONS_ROOT / "1_create.py"

    with migration_create_path.open() as migration_file:
        migration_contents = migration_file.read()

    expected_create_call = f"op.execute(sql_text({TO_UPPER.to_sql_statement_create()!r}))"
    expected_drop_call = f"op.execute(sql_text({TO_UPPER.to_sql_statement_drop()!r}))"

    assert expected_create_call in migration_contents
    assert expected_drop_call in migration_contents
    assert "from alembic_utils.pg_function import PGFunction" not in migration_contents
    assert "from sqlalchemy import text as sql_text" in migration_contents
