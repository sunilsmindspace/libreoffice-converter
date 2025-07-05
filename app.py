import asyncio
import os
import subprocess
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional
import yaml
import logging
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import aiofiles

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Config:
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.input_formats = self.config['converter']['input_formats']
        self.output_format = self.config['converter']['output_format']
        self.workers = self.config['converter']['workers']
        self.temp_dir = self.config['converter']['temp_dir']
        self.max_file_size = self.config['converter']['max_file_size'] * 1024 * 1024  # Convert to bytes
        self.conversion_timeout = self.config['converter']['conversion_timeout']
        self.host = self.config['server']['host']
        self.port = self.config['server']['port']
        self.debug = self.config['server']['debug']

class ConversionResult(BaseModel):
    success: bool
    message: str
    file_id: Optional[str] = None

class DocumentConverter:
    def __init__(self, config: Config):
        self.config = config
        self.executor = ThreadPoolExecutor(max_workers=config.workers)
        
        # Ensure temp directory exists
        os.makedirs(config.temp_dir, exist_ok=True)
    
    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename"""
        return Path(filename).suffix.lower().lstrip('.')
    
    def _validate_input_format(self, filename: str) -> bool:
        """Validate if input format is supported"""
        ext = self._get_file_extension(filename)
        return ext in self.config.input_formats
    
    async def convert_document(self, file_content: bytes, filename: str) -> tuple[bool, str, Optional[str]]:
        """Convert document using LibreOffice"""
        if not self._validate_input_format(filename):
            return False, f"Unsupported input format: {self._get_file_extension(filename)}", None
        
        file_id = str(uuid.uuid4())
        input_path = os.path.join(self.config.temp_dir, f"{file_id}_input.{self._get_file_extension(filename)}")
        output_dir = os.path.join(self.config.temp_dir, file_id)
        
        try:
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Write input file
            async with aiofiles.open(input_path, 'wb') as f:
                await f.write(file_content)
            
            # Run conversion in thread pool
            loop = asyncio.get_event_loop()
            success, message, output_file = await loop.run_in_executor(
                self.executor, 
                self._run_libreoffice_conversion, 
                input_path, 
                output_dir
            )
            
            if success:
                return True, "Conversion successful", output_file
            else:
                return False, message, None
                
        except Exception as e:
            logger.error(f"Conversion error for {filename}: {str(e)}")
            return False, f"Conversion failed: {str(e)}", None
        finally:
            # Clean up input file
            if os.path.exists(input_path):
                os.remove(input_path)
    
    def _run_libreoffice_conversion(self, input_path: str, output_dir: str) -> tuple[bool, str, Optional[str]]:
        """Run LibreOffice conversion command"""
        try:
            # LibreOffice command with additional headless flags
            cmd = [
                'libreoffice',
                '--headless',
                '--invisible',
                '--nodefault',
                '--nolockcheck',
                '--nologo',
                '--norestore',
                '--convert-to', self.config.output_format,
                '--outdir', output_dir,
                input_path
            ]
            
            # Run conversion with environment variables for headless mode
            env = os.environ.copy()
            env['DISPLAY'] = ''
            env['SAL_USE_VCLPLUGIN'] = 'svp'
            
            result = subprocess.run(
                cmd,
                timeout=self.config.conversion_timeout,
                capture_output=True,
                text=True,
                env=env
            )
            
            if result.returncode == 0:
                # Find the output file
                output_files = list(Path(output_dir).glob(f"*.{self.config.output_format}"))
                if output_files:
                    return True, "Conversion successful", str(output_files[0])
                else:
                    return False, "No output file generated", None
            else:
                return False, f"LibreOffice error: {result.stderr}", None
                
        except subprocess.TimeoutExpired:
            return False, "Conversion timeout", None
        except Exception as e:
            return False, f"Conversion error: {str(e)}", None

# Initialize config and converter
config = Config()
converter = DocumentConverter(config)
app = FastAPI(title="LibreOffice Document Converter", version="1.0.0")

@app.get("/")
async def root():
    return {"message": "LibreOffice Document Converter API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "workers": config.workers}

@app.get("/formats")
async def supported_formats():
    return {
        "input_formats": config.input_formats,
        "output_format": config.output_format
    }

@app.post("/convert")
async def convert_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Convert uploaded document"""
    
    # Validate file size
    file_content = await file.read()
    if len(file_content) > config.max_file_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {config.max_file_size / (1024*1024):.1f}MB"
        )
    
    # Validate filename
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    try:
        # Convert document
        success, message, output_file = await converter.convert_document(file_content, file.filename)
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        if not output_file or not os.path.exists(output_file):
            raise HTTPException(status_code=500, detail="Conversion failed - no output file")
        
        # Stream the converted file
        async def stream_file():
            try:
                async with aiofiles.open(output_file, 'rb') as f:
                    while chunk := await f.read(8192):
                        yield chunk
            finally:
                # Clean up output file in background
                background_tasks.add_task(cleanup_file, output_file)
                background_tasks.add_task(cleanup_dir, os.path.dirname(output_file))
        
        # Generate output filename
        base_name = Path(file.filename).stem
        output_filename = f"{base_name}.{config.output_format}"
        
        return StreamingResponse(
            stream_file(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/convert/batch")
async def convert_batch(background_tasks: BackgroundTasks, files: list[UploadFile] = File(...)):
    """Convert multiple documents in parallel"""
    
    if len(files) > config.workers * 2:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum: {config.workers * 2}"
        )
    
    results = []
    tasks = []
    
    # Create conversion tasks
    for file in files:
        file_content = await file.read()
        
        if len(file_content) > config.max_file_size:
            results.append({
                "filename": file.filename,
                "success": False,
                "message": f"File too large. Maximum size: {config.max_file_size / (1024*1024):.1f}MB"
            })
            continue
        
        if not file.filename:
            results.append({
                "filename": "unknown",
                "success": False,
                "message": "No filename provided"
            })
            continue
        
        task = converter.convert_document(file_content, file.filename)
        tasks.append((file.filename, task))
    
    # Execute conversions in parallel
    for filename, task in tasks:
        try:
            success, message, output_file = await task
            
            result = {
                "filename": filename,
                "success": success,
                "message": message
            }
            
            if output_file:
                # Schedule cleanup
                background_tasks.add_task(cleanup_file, output_file)
                background_tasks.add_task(cleanup_dir, os.path.dirname(output_file))
            
            results.append(result)
            
        except Exception as e:
            logger.error(f"Batch conversion error for {filename}: {str(e)}")
            results.append({
                "filename": filename,
                "success": False,
                "message": f"Conversion failed: {str(e)}"
            })
    
    return {"results": results}

async def cleanup_file(file_path: str):
    """Clean up temporary file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logger.warning(f"Failed to cleanup file {file_path}: {str(e)}")

async def cleanup_dir(dir_path: str):
    """Clean up temporary directory"""
    try:
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            # Only remove if empty
            if not os.listdir(dir_path):
                os.rmdir(dir_path)
    except Exception as e:
        logger.warning(f"Failed to cleanup directory {dir_path}: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.host, port=config.port, debug=config.debug)