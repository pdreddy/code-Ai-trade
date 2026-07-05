from backend.app.core.database_url import normalize_sqlalchemy_database_url


def test_normalize_render_postgres_url_to_psycopg_dialect() -> None:
    assert (
        normalize_sqlalchemy_database_url("postgresql://user:pass@host:5432/db")
        == "postgresql+psycopg://user:pass@host:5432/db"
    )


def test_preserve_explicit_sqlalchemy_driver_url() -> None:
    url = "postgresql+psycopg://user:pass@host:5432/db"

    assert normalize_sqlalchemy_database_url(url) == url
