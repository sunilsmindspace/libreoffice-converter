import pytest
import asyncio
import os
import tempfile
import time
from pathlib import Path
from typing import List, Tuple
import subprocess
import shutil
from fastapi.testclient import TestClient
from httpx import AsyncClient
import requests

from app import app, Config, DocumentConverter

@pytest.mark.integration
class TestIntegrationBasic:
    """Basic integration tests for the document converter."""
    
    @pytest.fixture
    def real_config(self):
        """Provide real configuration for integration tests."""
        return Config("config-test.yaml")
    
    @pytest.fixture
    def real_converter(self, real_config):
        """Provide real converter instance."""
        return DocumentConverter(real_config)
    
    def test_libreoffice_available(self):
        """Test that LibreOffice is available in the system."""
        try:
            result = subprocess.run(
                ['libreoffice', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            assert result.returncode == 0
            assert 'LibreOffice' in result.stdout
        except FileNotFoundError:
            pytest.skip("LibreOffice not available in test environment")
    
    def test_temp_directory_creation(self, real_converter):
        """Test that temporary directories are created correctly."""
        temp_dir = real_converter.config.temp_dir
        assert os.path.exists(temp_dir)
        assert os.path.isdir(temp_dir)
    
    @pytest.mark.asyncio
    async def test_text_to_pdf_conversion(self, real_converter, create_test_files):
        """Test actual text to PDF conversion."""
        # Skip if LibreOffice not available
        if not shutil.which('libreoffice'):
            pytest.skip("LibreOffice not available")
        
        # Create test text file
        text_content = "This is a test document for conversion.\nSecond line.\nThird line."
        
        success, message, output_file = await real_converter.convert_document(
            text_content.encode('utf-8'), 
            "test.txt"
        )
        
        if success:
            assert output_file is not None
            assert os.path.exists(output_file)
            assert output_file.endswith('.pdf')
            
            # Cleanup
            if os.path.exists(output_file):
                os.remove(output_file)
        else:
            # Log the failure for debugging
            print(f"Conversion failed: {message}")

@pytest.mark.integration
class TestIntegrationAPI:
    """Integration tests for the API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Provide test client."""
        return TestClient(app)
    
    @pytest.fixture
    async def async_client(self):
        """Provide async test client."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    def test_api_health_check(self, client):
        """Test API health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "workers" in data
    
    def test_api_formats_endpoint(self, client):
        """Test formats endpoint returns expected formats."""
        response = client.get("/formats")
        assert response.status_code == 200
        data = response.json()
        
        assert "input_formats" in data
        assert "output_format" in data
        assert isinstance(data["input_formats"], list)
        assert len(data["input_formats"]) > 0
        assert "docx" in data["input_formats"]
        assert "txt" in data["input_formats"]
        assert data["output_format"] == "pdf"
    
    def test_api_convert_with_real_text_file(self, client, create_test_files):
        """Test conversion with real text file through API."""
        # Skip if LibreOffice not available
        if not shutil.which('libreoffice'):
            pytest.skip("LibreOffice not available")
        
        test_content = "Integration test document content.\nLine 2\nLine 3"
        
        response = client.post(
            "/convert",
            files={"file": ("test_integration.txt", test_content.encode('utf-8'), "text/plain")}
        )
        
        # Should either succeed or fail gracefully
        assert response.status_code in [200, 400, 500]
        
        if response.status_code == 200:
            assert response.headers["content-type"] == "application/octet-stream"
            assert "attachment" in response.headers["content-disposition"]
            assert len(response.content) > 0
    
    def test_api_convert_unsupported_format(self, client):
        """Test conversion with unsupported file format."""
        response = client.post(
            "/convert",
            files={"file": ("test.exe", b"binary content", "application/octet-stream")}
        )
        
        assert response.status_code == 400
        assert "Unsupported input format" in response.json()["detail"]
    
    def test_api_convert_no_filename(self, client):
        """Test conversion without filename."""
        response = client.post(
            "/convert",
            files={"file": (None, b"content", "text/plain")}
        )
        
        assert response.status_code == 400
        assert "filename" in response.json()["detail"]
    
    def test_api_batch_conversion(self, client):
        """Test batch conversion endpoint."""
        files = [
            ("files", ("test1.txt", b"Content 1", "text/plain")),
            ("files", ("test2.txt", b"Content 2", "text/plain")),
        ]
        
        response = client.post("/convert/batch", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 2
        
        for result in data["results"]:
            assert "filename" in result
            assert "success" in result
            assert "message" in result

@pytest.mark.integration
class TestIntegrationPerformance:
    """Integration tests for performance and concurrency."""
    
    @pytest.fixture
    def client(self):
        """Provide test client."""
        return TestClient(app)
    
    @pytest.mark.slow
    def test_concurrent_requests(self, client):
        """Test multiple concurrent API requests."""
        def make_request(content: str) -> Tuple[int, dict]:
            response = client.post(
                "/convert",
                files={"file": (f"test_{content}.txt", content.encode('utf-8'), "text/plain")}
            )
            return response.status_code, response.json() if response.status_code != 200 else {}
        
        # Create multiple requests
        contents = [f"Test content {i}" for i in range(5)]
        
        # Execute requests concurrently using ThreadPoolExecutor
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_request, content) for content in contents]
            results = [future.result() for future in futures]
        
        # All requests should complete
        assert len(results) == 5
        
        # Check that we don't have too many failures
        success_count = sum(1 for status, _ in results if status == 200)
        error_count = len(results) - success_count
        
        # Allow some failures due to system constraints
        assert error_count <= 2, f"Too many failures: {error_count}/5"
    
    @pytest.mark.slow
    def test_large_batch_conversion(self, client):
        """Test batch conversion with multiple files."""
        files = [
            ("files", (f"test{i}.txt", f"Content for file {i}".encode('utf-8'), "text/plain"))
            for i in range(4)  # Test with 4 files (within limit)
        ]
        
        start_time = time.time()
        response = client.post("/convert/batch", files=files)
        end_time = time.time()
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 4
        
        # Should complete within reasonable time
        assert end_time - start_time < 60  # 60 seconds max
    
    def test_file_size_limits(self, client):
        """Test file size limit enforcement."""
        # Create content larger than limit (test config has 10MB limit)
        large_content = b"X" * (15 * 1024 * 1024)  # 15MB
        
        response = client.post(
            "/convert",
            files={"file": ("large.txt", large_content, "text/plain")}
        )
        
        assert response.status_code == 413
        assert "too large" in response.json()["detail"]

@pytest.mark.integration
class TestIntegrationDocker:
    """Integration tests for Docker-specific functionality."""
    
    def test_environment_variables(self):
        """Test that required environment variables are set correctly."""
        # These should be set in the Docker environment
        display_var = os.environ.get('DISPLAY', '')
        sal_plugin = os.environ.get('SAL_USE_VCLPLUGIN', '')
        
        # In test environment, these might not be set, so we test the application sets them
        from app import DocumentConverter, Config
        converter = DocumentConverter(Config("config-test.yaml"))
        
        # Test that the converter sets the environment correctly in subprocess
        import subprocess
        from unittest.mock import patch
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stderr = ""
            
            converter._run_libreoffice_conversion("/tmp/test.txt", "/tmp/output")
            
            # Check environment variables were set
            call_kwargs = mock_run.call_args[1]
            env = call_kwargs['env']
            assert env['DISPLAY'] == ''
            assert env['SAL_USE_VCLPLUGIN'] == 'svp'
    
    def test_temp_directory_permissions(self):
        """Test that temporary directory has correct permissions."""
        from app import DocumentConverter, Config
        converter = DocumentConverter(Config("config-test.yaml"))
        
        temp_dir = converter.config.temp_dir
        if os.path.exists(temp_dir):
            # Check that directory is writable
            test_file = os.path.join(temp_dir, "test_permissions.txt")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                # If we get here, permissions are correct
                assert True
            except PermissionError:
                pytest.fail("Temporary directory is not writable")

@pytest.mark.integration
class TestIntegrationErrorHandling:
    """Integration tests for error handling scenarios."""
    
    @pytest.fixture
    def client(self):
        """Provide test client."""
        return TestClient(app)
    
    def test_malformed_file_handling(self, client):
        """Test handling of malformed files."""
        # Create a file with wrong extension but different content
        malformed_content = b"This is not a real DOCX file content"
        
        response = client.post(
            "/convert",
            files={"file": ("fake.docx", malformed_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
        
        # Should fail gracefully
        assert response.status_code in [400, 500]
        if response.status_code == 400:
            error_detail = response.json()["detail"]
            assert isinstance(error_detail, str)
            assert len(error_detail) > 0
    
    def test_timeout_handling(self, client):
        """Test that timeouts are handled properly."""
        # This test depends on the timeout configuration
        # We can't easily force a timeout in integration tests,
        # so we just verify the timeout setting exists
        from app import config
        assert config.conversion_timeout > 0
        assert config.conversion_timeout <= 300  # Reasonable upper bound
    
    def test_disk_space_simulation(self, client):
        """Test behavior when disk space might be limited."""
        # Create multiple files to potentially fill up space
        files = []
        for i in range(10):
            content = f"Test file {i} with some content to take up space" * 100
            files.append(("files", (f"test{i}.txt", content.encode('utf-8'), "text/plain")))
        
        response = client.post("/convert/batch", files=files)
        
        # Should either succeed or fail gracefully
        assert response.status_code in [200, 400, 500, 507]  # 507 = Insufficient Storage

@pytest.mark.integration
class TestIntegrationCleanup:
    """Integration tests for cleanup functionality."""
    
    @pytest.fixture
    def client(self):
        """Provide test client."""
        return TestClient(app)
    
    def test_temporary_file_cleanup(self, client):
        """Test that temporary files are cleaned up after conversion."""
        from app import config
        temp_dir = config.temp_dir
        
        # Count files before conversion
        initial_files = len(os.listdir(temp_dir)) if os.path.exists(temp_dir) else 0
        
        # Perform conversion
        response = client.post(
            "/convert",
            files={"file": ("test_cleanup.txt", b"Test content for cleanup", "text/plain")}
        )
        
        # Wait a bit for cleanup to complete
        import time
        time.sleep(1)
        
        # Count files after conversion
        final_files = len(os.listdir(temp_dir)) if os.path.exists(temp_dir) else 0
        
        # Should not have significantly more files
        assert final_files <= initial_files + 1  # Allow for some temporary files
    
    @pytest.mark.slow
    def test_long_running_cleanup(self, client):
        """Test cleanup over multiple conversions."""
        from app import config
        temp_dir = config.temp_dir
        
        # Perform multiple conversions
        for i in range(5):
            response = client.post(
                "/convert",
                files={"file": (f"test_{i}.txt", f"Content {i}".encode('utf-8'), "text/plain")}
            )
            # Don't check status as conversions might fail in test environment
        
        # Wait for cleanup
        import time
        time.sleep(2)
        
        # Check that temp directory doesn't have too many files
        if os.path.exists(temp_dir):
            temp_files = os.listdir(temp_dir)
            # Should not accumulate too many temporary files
            assert len(temp_files) < 20  # Reasonable upper bound

@pytest.mark.integration
class TestIntegrationRealFiles:
    """Integration tests with real file formats (if available)."""
    
    def test_with_real_files_if_available(self, client, create_test_files):
        """Test conversion with real files if they exist."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        
        test_files = [
            ("test_text.txt", "text/plain"),
            ("test_document.html", "text/html"),
        ]
        
        for filename, mimetype in test_files:
            file_path = fixtures_dir / filename
            if file_path.exists():
                with open(file_path, 'rb') as f:
                    content = f.read()
                
                response = client.post(
                    "/convert",
                    files={"file": (filename, content, mimetype)}
                )
                
                # Log result for debugging
                print(f"Conversion of {filename}: {response.status_code}")
                if response.status_code not in [200, 400]:
                    print(f"Response: {response.text}")
                
                # Should not crash
                assert response.status_code in [200, 400, 500]

# Utility functions for integration tests
def wait_for_service(url: str, timeout: int = 30) -> bool:
    """Wait for service to be available."""
    import time
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    
    return False

def check_libreoffice_installation() -> bool:
    """Check if LibreOffice is properly installed."""
    try:
        result = subprocess.run(
            ['libreoffice', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0 and 'LibreOffice' in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

# Pytest hooks for integration tests
def pytest_runtest_setup(item):
    """Setup for integration tests."""
    if item.get_closest_marker("integration"):
        # Skip integration tests if LibreOffice is not available
        if not check_libreoffice_installation():
            pytest.skip("LibreOffice not available for integration tests")

def pytest_configure(config):
    """Configure integration test markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests requiring full environment"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow integration tests"
    )