from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--pdf-dir", action="store", help="optional directory to store generated PDFs"
    )

@pytest.fixture
def pdf_dir(request):
    value = request.config.getoption("--pdf-dir")
    return Path(value) if value else None