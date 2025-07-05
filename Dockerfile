FROM python:3.13-slim

# Build arguments for metadata
ARG BUILD_DATE
ARG VERSION
ARG GIT_COMMIT
ARG GIT_BRANCH

# Labels for image metadata
LABEL maintainer="LibreOffice Document Converter Team"
LABEL version="${VERSION}"
LABEL description="Headless LibreOffice document converter with FastAPI"
LABEL build-date="${BUILD_DATE}"
LABEL git-commit="${GIT_COMMIT}"
LABEL git-branch="${GIT_BRANCH}"

# Install LibreOffice headless and minimal dependencies
RUN apt-get update && apt-get install -y \
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    libreoffice-headless \
    --no-install-recommends \
    && apt-get remove -y \
    libreoffice-gtk3 \
    libreoffice-gnome \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for headless operation
ENV DISPLAY=""
ENV SAL_USE_VCLPLUGIN=svp

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create directories for temporary files
RUN mkdir -p /tmp/converter

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "app.py"]