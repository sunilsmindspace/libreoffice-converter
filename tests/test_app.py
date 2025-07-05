import pytest
import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient
import io

from app import app, DocumentConverter, Config

class TestConfig:
    """Test configuration loading and validation."""
    
    def test_config_loading(self, test_config):
        """Test configuration loading from dict."""
        with patch('yaml.safe_load', return_value=test_config):
            with patch('builtins.open', return_value=io.StringIO()):
                config = Config()
                assert config.workers == 2
                assert config.output_format == "pdf"
                assert "docx" in config.input_formats
    
    def test_config_file_size_conversion(self, test_config):
        """Test file size conversion from MB to bytes."""
        with patch('yaml.safe_load', return_value=test_config):
            with patch('builtins.open', return_value=io.StringIO()):
                config = Config()
                assert config.max_file_size == 10 * 1024 * 1024  # 10MB in bytes

class TestDocumentConverter:
    """Test document converter functionality."""
    
    @pytest.fixture
    def config(self, test_config):
        """Provide test configuration."""
        with patch('yaml.safe_load', return_value=test_config):
            with patch('builtins.open', return_value=io.StringIO()):
                return Config()
    
    @pytest.fixture
    def converter(self, config):
        """Provide document converter instance."""
        return DocumentConverter(config)
    
    def test_converter_initialization(self, converter):
        """Test converter initialization."""
        assert converter.config is not None
        assert converter.executor is not None
        assert converter.config.workers == 2
    
    def test_get_file_extension(self, converter):
        """Test file extension extraction."""
        assert converter._get_file_extension("test.docx") == "docx"
        assert converter._get_file_extension("test.PDF") == "pdf"
        assert converter._get_file_extension("document.xlsx") == "xlsx"
        assert converter._get_file_extension("no_extension") == ""
    
    def test_validate_input_format(self, converter):
        """Test input format validation."""
        assert converter._validate_input_format("test.docx") == True
        assert converter._validate_input_format("test.xlsx") == True
        assert converter._validate_input_format("test.exe") == False
        assert converter._validate_input_format("test.unknown") == False
    
    @pytest.mark.asyncio
    async def test_convert_document_invalid_format(self, converter):
        """Test conversion with invalid format."""
        content = b"test content"
        filename = "test.exe"
        
        success, message, output_file = await converter.convert_document(content, filename)
        
        assert success == False
        assert "Unsupported input format" in message
        assert output_file is None
    
    @pytest.mark.asyncio
    async def test_convert_document_success(self, converter, mock_subprocess_success, temp_file):
        """Test successful document conversion."""
        content = b"test content"
        filename = "test.docx"
        
        # Mock the output file creation
        with patch('pathlib.Path.glob') as mock_glob:
            mock_glob.return_value = [Path(temp_file)]
            
            success, message, output_file = await converter.convert_document(content, filename)
            
            assert success == True
            assert message == "Conversion successful"
            assert output_file == temp_file
    
    @pytest.mark.asyncio
    async def test_convert_document_failure(self, converter, mock_subprocess_failure):
        """Test failed document conversion."""
        content = b"test content"
        filename = "test.docx"
        
        success, message, output_file = await converter.convert_document(content, filename)
        
        assert success == False
        assert "LibreOffice error" in message
        assert output_file is None
    
    @pytest.mark.asyncio
    async def test_convert_document_timeout(self, converter, mock_subprocess_timeout):
        """Test conversion timeout."""
        content = b"test content"
        filename = "test.docx"
        
        success, message, output_file = await converter.convert_document(content, filename)
        
        assert success == False
        assert "timeout" in message.lower()
        assert output_file is None
    
    def test_run_libreoffice_conversion_success(self, converter, mock_subprocess_success, temp_file):
        """Test LibreOffice conversion command execution."""
        input_path = "/tmp/test_input.docx"
        output_dir = "/tmp/test_output"
        
        with patch('pathlib.Path.glob') as mock_glob:
            mock_glob.return_value = [Path(temp_file)]
            
            success, message, output_file = converter._run_libreoffice_conversion(input_path, output_dir)
            
            assert success == True
            assert message == "Conversion successful"
            assert output_file == temp_file
    
    def test_run_libreoffice_conversion_failure(self, converter, mock_subprocess_failure):
        """Test LibreOffice conversion command failure."""
        input_path = "/tmp/test_input.docx"
        output_dir = "/tmp/test_output"
        
        success, message, output_file = converter._run_libreoffice_conversion(input_path, output_dir)
        
        assert success == False
        assert "LibreOffice error" in message
        assert output_file is None

class TestAPIEndpoints:
    """Test FastAPI endpoints."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        assert "LibreOffice Document Converter API" in response.json()["message"]
    
    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "workers" in data
        assert data["status"] == "healthy"
    
    def test_formats_endpoint(self, client):
        """Test formats endpoint."""
        response = client.get("/formats")
        assert response.status_code == 200
        data = response.json()
        assert "input_formats" in data
        assert "output_format" in data
        assert isinstance(data["input_formats"], list)
        assert "docx" in data["input_formats"]
    
    def test_convert_no_file(self, client):
        """Test conversion without file."""
        response = client.post("/convert")
        assert response.status_code == 422  # Validation error
    
    def test_convert_large_file(self, client, large_file_content):
        """Test conversion with file too large."""
        response = client.post(
            "/convert",
            files={"file": ("large_file.docx", large_file_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
        assert response.status_code == 413  # File too large
        assert "too large" in response.json()["detail"]
    
    def test_convert_no_filename(self, client, small_file_content):
        """Test conversion without filename."""
        response = client.post(
            "/convert",
            files={"file": (None, small_file_content, "application/octet-stream")}
        )
        assert response.status_code == 400
        assert "filename" in response.json()["detail"]
    
    @patch('app.converter.convert_document')
    def test_convert_success(self, mock_convert, client, small_file_content, temp_file):
        """Test successful conversion."""
        # Mock successful conversion
        mock_convert.return_value = asyncio.coroutine(
            lambda: (True, "Conversion successful", temp_file)
        )()
        
        # Create temp file with content
        with open(temp_file, 'wb') as f:
            f.write(b"converted content")
        
        response = client.post(
            "/convert",
            files={"file": ("test.docx", small_file_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"
        assert "attachment" in response.headers["content-disposition"]
    
    @patch('app.converter.convert_document')
    def test_convert_failure(self, mock_convert, client, small_file_content):
        """Test failed conversion."""
        # Mock failed conversion
        mock_convert.return_value = asyncio.coroutine(
            lambda: (False, "Conversion failed", None)
        )()
        
        response = client.post(
            "/convert",
            files={"file": ("test.docx", small_file_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
        
        assert response.status_code == 400
        assert "failed" in response.json()["detail"]
    
    def test_convert_batch_too_many_files(self, client, small_file_content):
        """Test batch conversion with too many files."""
        files = [
            ("files", ("test1.docx", small_file_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("test2.docx", small_file_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("test3.docx", small_file_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("test4.docx", small_file_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("test5.docx", small_file_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
        ]
        
        response = client.post("/convert/batch", files=files)
        assert response.status_code == 400
        assert "Too many files" in response.json()["detail"]
    
    @patch('app.converter.convert_document')
    def test_convert_batch_success(self, mock_convert, client, small_file_content):
        """Test successful batch conversion."""
        # Mock successful conversion
        mock_convert.return_value = asyncio.coroutine(
            lambda: (True, "Conversion successful", "/tmp/output.pdf")
        )()
        
        files = [
            ("files", ("test1.docx", small_file_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("test2.docx", small_file_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
        ]
        
        response = client.post("/convert/batch", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 2
        assert all(result["success"] for result in data["results"])
    
    @patch('app.converter.convert_document')
    def test_convert_batch_mixed_results(self, mock_convert, client, small_file_content):
        """Test batch conversion with mixed results."""
        # Mock mixed results
        results = [
            (True, "Conversion successful", "/tmp/output1.pdf"),
            (False, "Conversion failed", None),
        ]
        
        mock_convert.side_effect = [
            asyncio.coroutine(lambda: results[0])(),
            asyncio.coroutine(lambda: results[1])(),
        ]
        
        files = [
            ("files", ("test1.docx", small_file_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("test2.docx", small_file_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
        ]
        
        response = client.post("/convert/batch", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 2
        assert data["results"][0]["success"] == True
        assert data["results"][1]["success"] == False

class TestUtilityFunctions:
    """Test utility functions."""
    
    @pytest.mark.asyncio
    async def test_cleanup_file(self, temp_file):
        """Test file cleanup function."""
        from app import cleanup_file
        
        # Ensure file exists
        assert os.path.exists(temp_file)
        
        # Cleanup file
        await cleanup_file(temp_file)
        
        # File should be removed
        assert not os.path.exists(temp_file)
    
    @pytest.mark.asyncio
    async def test_cleanup_file_nonexistent(self):
        """Test cleanup of non-existent file."""
        from app import cleanup_file
        
        # Try to cleanup non-existent file (should not raise error)
        await cleanup_file("/tmp/nonexistent_file.txt")
    
    @pytest.mark.asyncio
    async def test_cleanup_dir(self, test_temp_dir):
        """Test directory cleanup function."""
        from app import cleanup_dir
        
        # Create empty directory
        test_dir = os.path.join(test_temp_dir, "test_cleanup")
        os.makedirs(test_dir, exist_ok=True)
        
        # Ensure directory exists and is empty
        assert os.path.exists(test_dir)
        assert os.path.isdir(test_dir)
        assert len(os.listdir(test_dir)) == 0
        
        # Cleanup directory
        await cleanup_dir(test_dir)
        
        # Directory should be removed
        assert not os.path.exists(test_dir)
    
    @pytest.mark.asyncio
    async def test_cleanup_dir_with_files(self, test_temp_dir):
        """Test directory cleanup with files (should not remove)."""
        from app import cleanup_dir
        
        # Create directory with file
        test_dir = os.path.join(test_temp_dir, "test_cleanup_with_files")
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        
        # Ensure directory exists and has files
        assert os.path.exists(test_dir)
        assert len(os.listdir(test_dir)) == 1
        
        # Try to cleanup directory (should not remove because it has files)
        await cleanup_dir(test_dir)
        
        # Directory should still exist
        assert os.path.exists(test_dir)

class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_conversion_exception_handling(self, converter):
        """Test handling of unexpected exceptions during conversion."""
        content = b"test content"
        filename = "test.docx"
        
        with patch('aiofiles.open', side_effect=Exception("Disk full")):
            success, message, output_file = await converter.convert_document(content, filename)
            
            assert success == False
            assert "Conversion failed" in message
            assert "Disk full" in message
            assert output_file is None
    
    def test_libreoffice_command_construction(self, converter):
        """Test LibreOffice command construction."""
        input_path = "/tmp/test.docx"
        output_dir = "/tmp/output"
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stderr = ""
            
            converter._run_libreoffice_conversion(input_path, output_dir)
            
            # Check that subprocess.run was called with correct arguments
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            
            assert 'libreoffice' in args
            assert '--headless' in args
            assert '--invisible' in args
            assert '--nodefault' in args
            assert '--nolockcheck' in args
            assert '--nologo' in args
            assert '--norestore' in args
            assert '--convert-to' in args
            assert '--outdir' in args
            assert input_path in args
            assert output_dir in args
    
    def test_environment_variables_in_subprocess(self, converter):
        """Test that environment variables are set correctly in subprocess."""
        input_path = "/tmp/test.docx"
        output_dir = "/tmp/output"
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stderr = ""
            
            converter._run_libreoffice_conversion(input_path, output_dir)
            
            # Check environment variables
            call_kwargs = mock_run.call_args[1]
            env = call_kwargs['env']
            
            assert env['DISPLAY'] == ''
            assert env['SAL_USE_VCLPLUGIN'] == 'svp'

class TestPerformance:
    """Test performance-related functionality."""
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_concurrent_conversions(self, converter):
        """Test multiple concurrent conversions."""
        content = b"test content"
        filenames = [f"test{i}.docx" for i in range(5)]
        
        with patch.object(converter, '_run_libreoffice_conversion') as mock_convert:
            mock_convert.return_value = (True, "Conversion successful", "/tmp/output.pdf")
            
            # Run concurrent conversions
            tasks = [
                converter.convert_document(content, filename)
                for filename in filenames
            ]
            
            results = await asyncio.gather(*tasks)
            
            # All conversions should succeed
            assert all(result[0] for result in results)
            assert len(results) == 5
    
    def test_thread_pool_initialization(self, converter):
        """Test that thread pool is initialized correctly."""
        assert converter.executor is not None
        assert converter.executor._max_workers == converter.config.workers

class TestConfigValidation:
    """Test configuration validation and edge cases."""
    
    def test_config_with_missing_keys(self):
        """Test configuration with missing required keys."""
        incomplete_config = {
            'converter': {
                'input_formats': ['docx'],
                # Missing other required keys
            }
        }
        
        with patch('yaml.safe_load', return_value=incomplete_config):
            with patch('builtins.open', return_value=io.StringIO()):
                with pytest.raises(KeyError):
                    Config()
    
    def test_config_file_not_found(self):
        """Test handling of missing config file."""
        with pytest.raises(FileNotFoundError):
            Config("nonexistent_config.yaml")
    
    def test_config_invalid_yaml(self):
        """Test handling of invalid YAML."""
        invalid_yaml = "invalid: yaml: content: ["
        
        with patch('builtins.open', return_value=io.StringIO(invalid_yaml)):
            with pytest.raises(Exception):  # YAML parsing error
                Config()

class TestFileHandling:
    """Test file handling edge cases."""
    
    @pytest.mark.asyncio
    async def test_file_with_special_characters(self, converter):
        """Test handling files with special characters in names."""
        content = b"test content"
        filename = "test file with spaces & symbols!.docx"
        
        with patch.object(converter, '_run_libreoffice_conversion') as mock_convert:
            mock_convert.return_value = (True, "Conversion successful", "/tmp/output.pdf")
            
            success, message, output_file = await converter.convert_document(content, filename)
            
            assert success == True
    
    @pytest.mark.asyncio
    async def test_file_with_no_extension(self, converter):
        """Test handling files with no extension."""
        content = b"test content"
        filename = "document_without_extension"
        
        success, message, output_file = await converter.convert_document(content, filename)
        
        assert success == False
        assert "Unsupported input format" in message
    
    @pytest.mark.asyncio
    async def test_empty_file(self, converter):
        """Test handling empty files."""
        content = b""
        filename = "empty.docx"
        
        with patch.object(converter, '_run_libreoffice_conversion') as mock_convert:
            mock_convert.return_value = (False, "Empty file", None)
            
            success, message, output_file = await converter.convert_document(content, filename)
            
            assert success == False

@pytest.mark.unit
class TestUnitIsolation:
    """Test that units are properly isolated."""
    
    def test_converter_instance_isolation(self, test_config):
        """Test that converter instances don't interfere with each other."""
        with patch('yaml.safe_load', return_value=test_config):
            with patch('builtins.open', return_value=io.StringIO()):
                config1 = Config()
                config2 = Config()
                
                converter1 = DocumentConverter(config1)
                converter2 = DocumentConverter(config2)
                
                assert converter1 is not converter2
                assert converter1.executor is not converter2.executor