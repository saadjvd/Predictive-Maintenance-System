import pytest
from app import create_app
from app.extensions import db


@pytest.fixture
def app():
    """Create and configure a Flask app for testing."""
    test_app = create_app("testing")

    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client fixture."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """CLI runner fixture."""
    return app.test_cli_runner()

