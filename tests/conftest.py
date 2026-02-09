import pytest

def pytest_addoption(parser):
    """Add CLI options for integration tests."""
    parser.addoption(
        "--run-live", action="store_true", default=False, help="Run live integration tests against broker"
    )

def pytest_configure(config):
    """Register markers."""
    config.addinivalue_line("markers", "live: mark test as requiring live broker connection")

def pytest_collection_modifyitems(config, items):
    """Skip live tests unless --run-live is specified."""
    if config.getoption("--run-live"):
        return
    
    skip_live = pytest.mark.skip(reason="need --run-live option to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
