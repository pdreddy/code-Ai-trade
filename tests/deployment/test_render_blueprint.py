from pathlib import Path

RENDER_BLUEPRINT = Path("render.yaml")


def test_render_blueprint_defines_required_platform_services() -> None:
    blueprint = RENDER_BLUEPRINT.read_text()

    assert "name: koc3-quant-backend" in blueprint
    assert "healthCheckPath: /api/v1/health" in blueprint
    assert "preDeployCommand: alembic upgrade head" in blueprint
    assert "name: koc3-quant-frontend" in blueprint
    assert "type: keyvalue" in blueprint
    assert "name: koc3-quant-postgres" in blueprint
    assert "fromDatabase:" in blueprint
    assert "fromService:" in blueprint
