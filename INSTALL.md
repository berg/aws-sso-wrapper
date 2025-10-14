# Installation and Usage Guide

## Package Structure

The package is now properly structured for distribution:

```
aws-sso-wrapper/
├── pyproject.toml          # Package metadata and build config
├── README.md               # User documentation
├── aws_sso_wrapper/        # Python package
│   └── __init__.py        # Main module with CLI entry point
└── .python-version         # Python version (3.13)
```

## Installation Methods

### 1. Local Development Install

```bash
# From the project directory
uv sync

# Run the tool
uv run aws-sso-wrapper -- aws sts get-caller-identity
```

### 2. Install as a Tool (Recommended for daily use)

```bash
# From the project directory
uv tool install .

# Now available globally
aws-sso-wrapper -- aws sts get-caller-identity
```

### 3. Run with uvx (No installation needed)

```bash
# From the project directory
uvx --from . aws-sso-wrapper -- aws sts get-caller-identity
```

### 4. Traditional pip install

```bash
# Install in editable mode
pip install -e .

# Or regular install
pip install .
```

## Environment Variables

Set these before using:

```bash
# Required: Specify which Chrome profile to use
export CHROME_PROFILE_IDENTIFIER="your-email@example.com"
# or by domain
export CHROME_PROFILE_IDENTIFIER="example.com"

# Optional: Override AWS paths
export AWS_CONFIG_FILE="$HOME/.aws/config"
export AWS_PROFILE="my-profile"
export AWS_SSO_CACHE_PATH="$HOME/.aws/sso"
export AWS_CLI_CACHE_DIR="$HOME/.aws/cli"
```

## Usage Examples

```bash
# Basic usage
aws-sso-wrapper -- aws sts get-caller-identity

# With other AWS commands
aws-sso-wrapper -- aws s3 ls
aws-sso-wrapper -- aws ec2 describe-instances

# Create an alias for convenience
alias aws-work='aws-sso-wrapper -- aws'
aws-work sts get-caller-identity
```

## How It Works

1. **Checks credentials**: Looks in AWS SSO cache for valid tokens
2. **Initiates login if needed**: Runs `aws sso login` with custom browser launcher
3. **Opens correct Chrome profile**: Uses Chrome profile directory matching your email
4. **Executes command**: Runs your AWS CLI command once credentials are valid

## Building for Distribution

```bash
# Build wheel and sdist
uv build

# Outputs to dist/
# - aws-sso-wrapper-0.1.0-py3-none-any.whl
# - aws-sso-wrapper-0.1.0.tar.gz
```

## Publishing (Future)

```bash
# To PyPI (when ready)
uv publish

# Then users can install with:
uvx aws-sso-wrapper -- aws sts get-caller-identity
# or
uv tool install aws-sso-wrapper
```

## Verifying Installation

```bash
# Check the command is available
which aws-sso-wrapper

# View help
aws-sso-wrapper --help

# Test credential checking (won't execute anything if creds are valid)
aws-sso-wrapper -- echo "test"
```

## Key Configuration Changes Made

1. **Added build system**: Uses `hatchling` for PEP 517 compliant builds
2. **Proper package structure**: Moved code to `aws_sso_wrapper/` directory
3. **Entry point configured**: `aws-sso-wrapper` command points to `aws_sso_wrapper:main`
4. **Python version relaxed**: Changed from `>=3.13` to `>=3.10` for broader compatibility
5. **Removed boto3 dependency**: Not actually used in the code
6. **Added package metadata**: Proper wheel packaging configuration
