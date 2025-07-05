#!/bin/bash

# Setup script for LibreOffice Document Converter
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

print_header() {
    echo
    print_status $BLUE "=================================================="
    print_status $BLUE "$1"
    print_status $BLUE "=================================================="
    echo
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

print_header "LibreOffice Document Converter Setup"

# Check operating system
OS="$(uname -s)"
case "${OS}" in
    Linux*)     MACHINE=Linux;;
    Darwin*)    MACHINE=Mac;;
    CYGWIN*)    MACHINE=Cygwin;;
    MINGW*)     MACHINE=MinGw;;
    *)          MACHINE="UNKNOWN:${OS}"
esac

print_status $YELLOW "Detected OS: $MACHINE"

# Install system dependencies
print_status $YELLOW "Installing system dependencies..."

case $MACHINE in
    "Linux")
        if command_exists apt-get; then
            print_status $YELLOW "Using apt-get package manager..."
            sudo apt-get update
            sudo apt-get install -y \
                python3 \
                python3-pip \
                python3-venv \
                libreoffice \
                libreoffice-writer \
                libreoffice-calc \
                libreoffice-impress \
                curl \
                wget
        elif command_exists yum; then
            print_status $YELLOW "Using yum package manager..."
            sudo yum update -y
            sudo yum install -y \
                python3 \
                python3-pip \
                libreoffice \
                curl \
                wget
        elif command_exists dnf; then
            print_status $YELLOW "Using dnf package manager..."
            sudo dnf update -y
            sudo dnf install -y \
                python3 \
                python3-pip \
                python3-devel \
                libreoffice \
                curl \
                wget
        else
            print_status $RED "❌ Unsupported Linux distribution"
            exit 1
        fi
        ;;
    "Mac")
        if command_exists brew; then
            print_status $YELLOW "Using Homebrew..."
            brew update
            # Install specific Python version if needed
            brew install python@3.13 libreoffice
            # Ensure python3 points to the right version
            if ! command_exists python3 || [ "$(python3 -c 'import sys; print(sys.version_info.minor)')" -lt "11" ]; then
                brew link --force python@3.13
            fi
        else
            print_status $RED "❌ Homebrew not found. Please install Homebrew first:"
            print_status $YELLOW "/bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            exit 1
        fi
        ;;
    *)
        print_status $RED "❌ Unsupported operating system: $MACHINE"
        exit 1
        ;;
esac

# Verify installations
print_status $YELLOW "Verifying installations..."

if ! command_exists python3; then
    print_status $RED "❌ Python3 installation failed"
    exit 1
fi

if ! command_exists pip3; then
    print_status $RED "❌ pip3 installation failed"
    exit 1
fi

if ! command_exists libreoffice; then
    print_status $RED "❌ LibreOffice installation failed"
    exit 1
fi

print_status $GREEN "✅ System dependencies installed successfully"

# Test LibreOffice headless mode
print_status $YELLOW "Testing LibreOffice headless mode..."
if libreoffice --headless --version >/dev/null 2>&1; then
    print_status $GREEN "✅ LibreOffice headless mode working"
else
    print_status $RED "❌ LibreOffice headless mode test failed"
    exit 1
fi

# Create virtual environment
print_status $YELLOW "Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_status $GREEN "✅ Virtual environment created"
else
    print_status $YELLOW "⚠️  Virtual environment already exists"
fi

# Activate virtual environment
print_status $YELLOW "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_status $YELLOW "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
print_status $YELLOW "Installing Python dependencies..."
pip install -r requirements.txt

# Install development dependencies
print_status $YELLOW "Installing development dependencies..."
pip install -r requirements-dev.txt

# Create necessary directories
print_status $YELLOW "Creating project directories..."
mkdir -p temp
mkdir -p logs
mkdir -p tests/fixtures

# Set up test fixtures
print_status $YELLOW "Setting up test fixtures..."

# Create test text file
cat > tests/fixtures/test_text.txt << EOF
This is a test document for conversion testing.
It contains multiple lines of text.
This will be used to test the document conversion functionality.

Features to test:
- Basic text conversion
- Multiple paragraphs
- Special characters: àáâãäåæçèéêë
- Numbers: 123456789
- Symbols: !@#$%^&*()
EOF

# Create test HTML file
cat > tests/fixtures/test_document.html << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Test Document</title>
    <meta charset="UTF-8">
</head>
<body>
    <h1>Test Document for Conversion</h1>
    <p>This is a <strong>test document</strong> created for testing the LibreOffice document converter.</p>
    
    <h2>Features</h2>
    <ul>
        <li>HTML to PDF conversion</li>
        <li>Rich text formatting</li>
        <li>Lists and headers</li>
    </ul>
    
    <h2>Test Content</h2>
    <p>This document contains various elements:</p>
    <ol>
        <li>Headers of different sizes</li>
        <li>Paragraphs with <em>italic</em> and <strong>bold</strong> text</li>
        <li>Lists (both ordered and unordered)</li>
        <li>Special characters: àáâãäåæçèéêë</li>
    </ol>
    
    <table border="1">
        <tr>
            <th>Column 1</th>
            <th>Column 2</th>
        </tr>
        <tr>
            <td>Data 1</td>
            <td>Data 2</td>
        </tr>
    </table>
</body>
</html>
EOF

# Create .gitkeep file for temp directory
touch temp/.gitkeep

print_status $GREEN "✅ Test fixtures created"

# Set environment variables
print_status $YELLOW "Setting up environment..."
export DISPLAY=""
export SAL_USE_VCLPLUGIN=svp

# Test the application
print_status $YELLOW "Running basic tests..."
python -c "
import sys
sys.path.append('.')
from app import Config, DocumentConverter
print('✅ Application imports successfully')

config = Config('config-test.yaml')
print('✅ Configuration loads successfully')

converter = DocumentConverter(config)
print('✅ Converter initializes successfully')
"

# Run a quick test conversion
print_status $YELLOW "Testing document conversion..."
python -c "
import asyncio
import sys
sys.path.append('.')
from app import Config, DocumentConverter

async def test_conversion():
    config = Config('config-test.yaml')
    converter = DocumentConverter(config)
    
    test_content = b'This is a test document for conversion.'
    success, message, output_file = await converter.convert_document(test_content, 'test.txt')
    
    if success:
        print('✅ Test conversion successful')
        import os
        if output_file and os.path.exists(output_file):
            os.remove(output_file)
    else:
        print(f'⚠️  Test conversion failed: {message}')
        print('This may be expected in some environments')

asyncio.run(test_conversion())
"

# Create Docker setup
print_status $YELLOW "Verifying Docker setup..."
if command_exists docker; then
    print_status $GREEN "✅ Docker is available"
    print_status $YELLOW "You can build the Docker image with:"
    print_status $BLUE "    docker-compose up --build"
else
    print_status $YELLOW "⚠️  Docker not found. Install Docker to use containerized deployment."
fi

# Setup complete
print_header "Setup Complete!"

print_status $GREEN "✅ LibreOffice Document Converter setup completed successfully!"
echo
print_status $YELLOW "Next steps:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Run tests: ./scripts/test.sh"
echo "3. Start the application: python app.py"
echo "4. Or use Docker: docker-compose up --build"
echo
print_status $YELLOW "Configuration files:"
echo "- Main config: config.yaml"
echo "- Test config: config-test.yaml"
echo
print_status $YELLOW "Test the API endpoints:"
echo "- Health check: curl http://localhost:8000/health"
echo "- Supported formats: curl http://localhost:8000/formats"
echo "- Convert document: curl -X POST -F 'file=@test.txt' http://localhost:8000/convert"
echo

print_status $BLUE "Happy converting! 🚀"