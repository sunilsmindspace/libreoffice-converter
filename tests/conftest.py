import asyncio
import os
import tempfile
from pathlib import Path
from typing import Generator, AsyncGenerator
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
import yaml

# Add the src directory to the path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import app, config, converter

# Test configuration
TEST_CONFIG = {
    'converter': {
        'input_formats': ['docx', 'doc', 'odt', 'rtf', 'txt', 'xlsx', 'xls', 'ods', 'pptx', 'ppt', 'odp'],
        'output_format': 'pdf',
        'workers': 2,
        'temp_dir': '/tmp/converter_test',
        'max_file_size': 10,
        'conversion_timeout': 30
    },
    'server': {
        'host': '127.0.0.1',
        'port': 8001,
        'debug': True
    }
}

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration."""
    return TEST_CONFIG

@pytest.fixture(scope="session")
def test_temp_dir():
    """Create and provide a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

@pytest.fixture(scope="session")
def fixtures_dir():
    """Provide the fixtures directory path."""
    return Path(__file__).parent / "fixtures"

@pytest.fixture(scope="session")
def sample_docx(fixtures_dir):
    """Provide path to sample DOCX file."""
    return fixtures_dir / "test_document.docx"

@pytest.fixture(scope="session")
def sample_xlsx(fixtures_dir):
    """Provide path to sample XLSX file."""
    return fixtures_dir / "test_spreadsheet.xlsx"

@pytest.fixture(scope="session")
def sample_pptx(fixtures_dir):
    """Provide path to sample PPTX file."""
    return fixtures_dir / "test_presentation.pptx"

@pytest.fixture(scope="session")
def sample_txt(fixtures_dir):
    """Provide path to sample TXT file."""
    return fixtures_dir / "test_text.txt"

@pytest.fixture(scope="session")
def create_test_files(fixtures_dir):
    """Create test files if they don't exist."""
    fixtures_dir.mkdir(exist_ok=True)
    
    # Create a simple text file
    txt_file = fixtures_dir / "test_text.txt"
    if not txt_file.exists():
        txt_file.write_text("This is a test document for conversion testing.\nLine 2\nLine 3")
    
    # Create simple HTML file that can be converted
    html_file = fixtures_dir / "test_document.html"
    if not html_file.exists():
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Document</title>
</head>
<body>
    <h1>Test Document</h1>
    <p>This is a test document for conversion testing.</p>
    <p>Second paragraph with <strong>bold text</strong>.</p>
</body>
</html>
"""
        html_file.write_text(html_content)
    
    return fixtures_dir

@pytest.fixture
def client():
    """Provide a test client for the FastAPI application."""
    return TestClient(app)

@pytest_asyncio.fixture
async def async_client():
    """Provide an async test client for the FastAPI application."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def mock_converter(mocker):
    """Provide a mocked converter for testing."""
    mock_conv = mocker.patch('app.converter')
    mock_conv.convert_document.return_value = asyncio.coroutine(
        lambda: (True, "Conversion successful", "/tmp/test_output.pdf")
    )()
    return mock_conv

@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"Test content")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)

@pytest.fixture
def large_file_content():
    """Generate content for testing large file limits."""
    # Create content larger than test limit (10MB)
    return b"X" * (15 * 1024 * 1024)  # 15MB

@pytest.fixture
def small_file_content():
    """Generate content for testing normal file size."""
    return b"Small test content for document conversion"

@pytest.fixture(autouse=True)
def setup_test_environment(test_temp_dir, monkeypatch):
    """Setup test environment variables and directories."""
    # Ensure test temp directory exists
    os.makedirs(test_temp_dir, exist_ok=True)
    
    # Set environment variables for testing
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("TEMP_DIR", test_temp_dir)
    
    yield
    
    # Cleanup test temp directory
    import shutil
    if os.path.exists(test_temp_dir):
        shutil.rmtree(test_temp_dir, ignore_errors=True)

@pytest.fixture
def mock_subprocess_success(mocker):
    """Mock successful subprocess execution."""
    mock_result = mocker.MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = ""
    return mocker.patch('subprocess.run', return_value=mock_result)

@pytest.fixture
def mock_subprocess_failure(mocker):
    """Mock failed subprocess execution."""
    mock_result = mocker.MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "LibreOffice conversion failed"
    return mocker.patch('subprocess.run', return_value=mock_result)

@pytest.fixture
def mock_subprocess_timeout(mocker):
    """Mock subprocess timeout."""
    import subprocess
    return mocker.patch('subprocess.run', side_effect=subprocess.TimeoutExpired(
        cmd=['libreoffice'], timeout=30
    ))

class TestFileManager:
    """Helper class for managing test files."""
    
    def __init__(self, temp_dir: str):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
    
    def create_test_file(self, filename: str, content: bytes) -> Path:
        """Create a test file with given content."""
        file_path = self.temp_dir / filename
        file_path.write_bytes(content)
        return file_path
    
    def cleanup(self):
        """Clean up all test files."""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

@pytest.fixture
def file_manager(test_temp_dir):
    """Provide a test file manager."""
    manager = TestFileManager(test_temp_dir)
    yield manager
    manager.cleanup()

# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )

def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers."""
    for item in items:
        # Add unit marker to all tests by default
        if not any(marker.name in ['integration', 'slow'] for marker in item.iter_markers()):
            item.add_marker(pytest.mark.unit)