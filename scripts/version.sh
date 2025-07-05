#!/bin/bash

# Version management script for LibreOffice Document Converter
set -e

# Colors
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

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Get current version information
get_version_info() {
    # Try to get version from git tags
    if command_exists git && git rev-parse --git-dir > /dev/null 2>&1; then
        GIT_VERSION=$(git describe --tags --always --dirty 2>/dev/null || echo "")
        GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
        GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
        GIT_TAG=$(git describe --tags --exact-match 2>/dev/null || echo "")
    else
        GIT_VERSION=""
        GIT_COMMIT="unknown"
        GIT_BRANCH="unknown"
        GIT_TAG=""
    fi
    
    # Fallback version
    if [ -z "$GIT_VERSION" ]; then
        GIT_VERSION="dev-$(date +%Y%m%d)"
    fi
    
    BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
}

# Display version information
show_version() {
    get_version_info
    
    print_status $BLUE "📦 LibreOffice Document Converter - Version Information"
    echo "=================================="
    echo "Version:      $GIT_VERSION"
    echo "Git Commit:   $GIT_COMMIT"
    echo "Git Branch:   $GIT_BRANCH"
    echo "Git Tag:      ${GIT_TAG:-"(none)"}"
    echo "Build Date:   $BUILD_DATE"
    echo "=================================="
}

# Create a new version tag
create_tag() {
    local version=$1
    
    if [ -z "$version" ]; then
        print_status $RED "❌ Version required"
        echo "Usage: $0 tag <version>"
        echo "Example: $0 tag v1.0.0"
        exit 1
    fi
    
    if ! command_exists git; then
        print_status $RED "❌ Git is required for tagging"
        exit 1
    fi
    
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_status $RED "❌ Not in a git repository"
        exit 1
    fi
    
    # Check if tag already exists
    if git rev-parse "$version" >/dev/null 2>&1; then
        print_status $RED "❌ Tag '$version' already exists"
        exit 1
    fi
    
    # Check if working directory is clean
    if ! git diff-index --quiet HEAD --; then
        print_status $YELLOW "⚠️  Working directory has uncommitted changes"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status $YELLOW "Aborted"
            exit 1
        fi
    fi
    
    print_status $YELLOW "Creating tag: $version"
    
    # Create annotated tag
    git tag -a "$version" -m "Release $version"
    
    print_status $GREEN "✅ Tag '$version' created successfully"
    print_status $YELLOW "To push the tag: git push origin $version"
}

# List available tags
list_tags() {
    if ! command_exists git; then
        print_status $RED "❌ Git is required"
        exit 1
    fi
    
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_status $RED "❌ Not in a git repository"
        exit 1
    fi
    
    print_status $BLUE "📋 Available Tags:"
    echo "=================="
    
    if git tag -l | head -1 > /dev/null 2>&1; then
        git tag -l --sort=-version:refname | head -20
        
        local tag_count=$(git tag -l | wc -l)
        if [ "$tag_count" -gt 20 ]; then
            echo "... and $((tag_count - 20)) more"
        fi
    else
        echo "No tags found"
    fi
}

# Generate changelog
generate_changelog() {
    local since_tag=$1
    
    if ! command_exists git; then
        print_status $RED "❌ Git is required"
        exit 1
    fi
    
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_status $RED "❌ Not in a git repository"
        exit 1
    fi
    
    if [ -n "$since_tag" ]; then
        if ! git rev-parse "$since_tag" >/dev/null 2>&1; then
            print_status $RED "❌ Tag '$since_tag' not found"
            exit 1
        fi
        range="${since_tag}..HEAD"
        print_status $BLUE "📝 Changelog since $since_tag:"
    else
        # Get the latest tag
        latest_tag=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
        if [ -n "$latest_tag" ]; then
            range="${latest_tag}..HEAD"
            print_status $BLUE "📝 Changelog since $latest_tag:"
        else
            range="HEAD"
            print_status $BLUE "📝 All commits:"
        fi
    fi
    
    echo "=========================="
    
    # Generate changelog with categorized commits
    echo "## Features"
    git log $range --pretty=format:"- %s (%h)" --grep="feat:" --grep="feature:" || echo "- No new features"
    
    echo -e "\n## Bug Fixes"
    git log $range --pretty=format:"- %s (%h)" --grep="fix:" --grep="bug:" || echo "- No bug fixes"
    
    echo -e "\n## Improvements"
    git log $range --pretty=format:"- %s (%h)" --grep="improve:" --grep="enhance:" --grep="refactor:" || echo "- No improvements"
    
    echo -e "\n## Documentation"
    git log $range --pretty=format:"- %s (%h)" --grep="docs:" --grep="doc:" || echo "- No documentation changes"
    
    echo -e "\n## Other Changes"
    git log $range --pretty=format:"- %s (%h)" --invert-grep --grep="feat:" --grep="feature:" --grep="fix:" --grep="bug:" --grep="improve:" --grep="enhance:" --grep="refactor:" --grep="docs:" --grep="doc:" || echo "- No other changes"
    
    echo "=========================="
}

# Show next version suggestions
suggest_version() {
    if ! command_exists git; then
        print_status $RED "❌ Git is required"
        exit 1
    fi
    
    local current_tag=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
    
    # Parse semantic version
    if [[ $current_tag =~ ^v?([0-9]+)\.([0-9]+)\.([0-9]+) ]]; then
        local major=${BASH_REMATCH[1]}
        local minor=${BASH_REMATCH[2]}
        local patch=${BASH_REMATCH[3]}
        
        print_status $BLUE "📈 Version Suggestions (current: $current_tag):"
        echo "================================"
        echo "Patch:  v$major.$minor.$((patch + 1))   (bug fixes)"
        echo "Minor:  v$major.$((minor + 1)).0       (new features)"
        echo "Major:  v$((major + 1)).0.0            (breaking changes)"
    else
        print_status $BLUE "📈 Version Suggestions:"
        echo "======================"
        echo "Start:  v1.0.0"
        echo "Beta:   v1.0.0-beta"
        echo "Alpha:  v1.0.0-alpha"
    fi
}

# Main function
main() {
    case "${1:-show}" in
        "show"|"")
            show_version
            ;;
        "tag")
            create_tag "$2"
            ;;
        "list"|"tags")
            list_tags
            ;;
        "changelog")
            generate_changelog "$2"
            ;;
        "suggest")
            suggest_version
            ;;
        "help"|"-h"|"--help")
            print_status $BLUE "🔧 Version Management Script"
            echo "Usage: $0 [command] [options]"
            echo ""
            echo "Commands:"
            echo "  show              Show current version information (default)"
            echo "  tag <version>     Create a new version tag"
            echo "  list              List all available tags"
            echo "  changelog [tag]   Generate changelog since tag (or latest)"
            echo "  suggest           Suggest next version numbers"
            echo "  help              Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                      # Show version info"
            echo "  $0 tag v1.2.3          # Create tag v1.2.3"
            echo "  $0 list                 # List all tags"
            echo "  $0 changelog v1.0.0     # Changelog since v1.0.0"
            echo "  $0 suggest              # Suggest next versions"
            ;;
        *)
            print_status $RED "❌ Unknown command: $1"
            echo "Run '$0 help' for usage information"
            exit 1
            ;;
    esac
}

main "$@"