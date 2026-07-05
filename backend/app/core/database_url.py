"""Database URL helpers shared by runtime and migration code."""

POSTGRESQL_SCHEME = "postgresql://"
PSYCOPG_SCHEME = "postgresql+psycopg://"


def normalize_sqlalchemy_database_url(database_url: str) -> str:
    """Force Render/Postgres URLs onto SQLAlchemy's psycopg v3 dialect.

    Render-managed PostgreSQL exposes standard `postgresql://` connection strings.
    The backend depends on `psycopg[binary]`, so SQLAlchemy should use the
    explicit `postgresql+psycopg://` dialect when the provider does not include
    a driver name.
    """

    if database_url.startswith(POSTGRESQL_SCHEME):
        return database_url.replace(POSTGRESQL_SCHEME, PSYCOPG_SCHEME, 1)
    return database_url
