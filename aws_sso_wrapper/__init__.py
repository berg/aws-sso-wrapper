#!/usr/bin/env python3
"""
AWS SSO login wrapper that opens in a specific Chrome profile.
"""
import contextlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import click


def find_chrome_profile(identifier: str) -> str | None:
    """
    Find a Chrome profile based on a domain or username.

    Searches Chrome profiles on macOS for a matching Google account.

    Args:
        identifier: Domain or username to search for (e.g., 'example.com' or 'user@example.com')

    Returns:
        Profile directory name (e.g., 'Default', 'Profile 1') or None if not found
    """
    chrome_dir = Path.home() / "Library/Application Support/Google/Chrome"

    if not chrome_dir.exists():
        return None

    # Search through all profile directories
    for profile_dir in chrome_dir.iterdir():
        if not profile_dir.is_dir():
            continue

        # Check the Preferences file for Google account info
        prefs_file = profile_dir / "Preferences"
        if prefs_file.exists():
            try:
                with prefs_file.open() as f:
                    prefs = json.load(f)

                # Check account_info for matching email/domain
                account_info = prefs.get('account_info', [])
                for account in account_info:
                    email = account.get('email', '')
                    if identifier in email or email.endswith(f'@{identifier}'):
                        return profile_dir.name

                # Also check signin.allowed_on_next_startup which might contain the account
                google_services = prefs.get('signin', {})
                if google_services:
                    # Check various signin fields
                    for key in ['last_username', 'username']:
                        username = google_services.get(key, '')
                        if identifier in username or username.endswith(f'@{identifier}'):
                            return profile_dir.name

            except (json.JSONDecodeError, KeyError):
                continue

    return None


def get_aws_sso_cache_dir() -> Path:
    """Get the AWS SSO cache directory, respecting environment variables."""
    # Check for AWS_SSO_CACHE_PATH (custom)
    if sso_cache_path := os.environ.get('AWS_SSO_CACHE_PATH'):
        return Path(sso_cache_path) / "cache"

    # Check for AWS_CLI_CACHE_DIR
    if cli_cache_dir := os.environ.get('AWS_CLI_CACHE_DIR'):
        return Path(cli_cache_dir) / "sso" / "cache"

    # Default to ~/.aws/sso/cache
    return Path.home() / ".aws/sso/cache"


def check_sso_credentials_valid() -> bool:
    """
    Check if current AWS SSO credentials are valid by checking cache files.

    AWS SSO stores two types of cache files:
    - SSO token cache: Contains accessToken and expiresAt
    - Role credentials cache: Contains temporary AWS credentials

    Returns:
        True if valid credentials exist, False otherwise
    """
    cache_dir = get_aws_sso_cache_dir()

    if not cache_dir.exists():
        return False

    now = datetime.now(UTC)

    # Check all cache files for valid credentials
    for cache_file in cache_dir.glob("*.json"):
        try:
            with cache_file.open() as f:
                cache_data = json.load(f)

            # Check for accessToken (SSO token cache)
            if 'accessToken' in cache_data:
                expires_at = cache_data.get('expiresAt')
                if expires_at:
                    # Parse ISO format timestamp (e.g., "2024-01-15T12:00:00UTC")
                    expires_dt = datetime.fromisoformat(expires_at.rstrip('Z').rstrip('UTC'))
                    if expires_dt.tzinfo is None:
                        expires_dt = expires_dt.replace(tzinfo=UTC)

                    if expires_dt > now:
                        return True

            # Check for Credentials (role credential cache)
            if 'Credentials' in cache_data:
                creds = cache_data['Credentials']
                expiration = creds.get('Expiration')
                if expiration:
                    # Parse ISO format timestamp
                    exp_dt = datetime.fromisoformat(expiration.rstrip('Z'))
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=UTC)

                    if exp_dt > now:
                        return True

        except (json.JSONDecodeError, ValueError, KeyError, OSError):
            continue

    return False


def get_aws_config_file() -> Path:
    """Get the AWS config file path, respecting environment variables."""
    if config_file := os.environ.get('AWS_CONFIG_FILE'):
        return Path(config_file)
    return Path.home() / ".aws/config"


def get_aws_config() -> dict:
    """
    Parse AWS config to get SSO configuration.

    Returns:
        Dictionary with sso_start_url, sso_region, etc.
    """
    config_file = get_aws_config_file()
    config = {}

    if not config_file.exists():
        return config

    # Determine which profile to use
    target_profile = os.environ.get('AWS_PROFILE', 'default')

    # Simple parser for AWS config file
    # This is a basic implementation - you might want to use configparser or boto3's config
    current_profile = None
    with config_file.open() as f:
        for raw_line in f:
            line = raw_line.strip()
            if line.startswith('[') and line.endswith(']'):
                # Profile header - handle both [default] and [profile foo] formats
                profile_header = line[1:-1]
                if profile_header.startswith('profile '):
                    current_profile = profile_header[8:]  # Strip "profile " prefix
                else:
                    current_profile = profile_header
            elif '=' in line and current_profile:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Store SSO-related config from the target profile
                if current_profile == target_profile and key.startswith('sso_'):
                    config[key] = value

    return config


def open_url_in_chrome_profile(url: str, profile_name: str) -> None:
    """
    Open a URL in a specific Chrome profile using subprocess safely.

    Args:
        url: The URL to open
        profile_name: Chrome profile directory name
    """
    # Use subprocess directly - no shell, no script writing
    subprocess.run(
        [
            'open',
            '-na',
            'Google Chrome',
            '--args',
            f'--profile-directory={profile_name}',
            url
        ],
        check=False
    )


@contextlib.contextmanager
def browser_launcher_wrapper(profile_name: str):
    """
    Context manager that creates a temporary Python script to launch Chrome in a specific profile.

    This wrapper is needed because AWS CLI expects a BROWSER environment variable
    pointing to an executable that takes a URL as an argument.

    Args:
        profile_name: Chrome profile directory name

    Yields:
        Path to the wrapper script

    Example:
        with browser_launcher_wrapper("Profile 1") as wrapper_path:
            subprocess.run(['aws', 'sso', 'login'], env={'BROWSER': str(wrapper_path)})
    """
    # Create a Python wrapper that safely invokes Chrome with the profile
    wrapper_content = f'''#!/usr/bin/env python3
import subprocess
import sys

if len(sys.argv) < 2:
    sys.exit(1)

url = sys.argv[1]
profile_name = {profile_name!r}

# Safely open Chrome with the specified profile
subprocess.run(
    [
        'open',
        '-na',
        'Google Chrome',
        '--args',
        f'--profile-directory={{profile_name}}',
        url
    ],
    check=False
)
'''

    # Create temporary file that will be auto-deleted when context exits
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.py',
        prefix='open-in-profile-',
        delete=True
    ) as fd:
        fd.write(wrapper_content)
        fd.flush()
        wrapper_path = Path(fd.name)
        wrapper_path.chmod(0o700)  # Owner read/write/execute only

        # Yield the path while keeping the file descriptor open
        # This ensures the file exists for the entire duration
        yield wrapper_path


def perform_sso_login(profile_name: str | None = None):
    """
    Perform AWS SSO login by initiating the device authorization flow.

    This launches the SSO URL in the specified Chrome profile.

    Args:
        profile_name: Chrome profile name to use for opening the browser
    """
    # Get SSO config
    aws_config = get_aws_config()
    sso_start_url = aws_config.get('sso_start_url')
    aws_config.get('sso_region', 'us-east-1')

    if not sso_start_url:
        click.echo("Error: No SSO start URL found in AWS config", err=True)
        sys.exit(1)

    # Set up environment to run aws sso login
    env = os.environ.copy()

    try:
        # If we have a Chrome profile, use context manager for browser launcher
        if profile_name:
            with browser_launcher_wrapper(profile_name) as wrapper_path:
                env['BROWSER'] = str(wrapper_path)

                # Run aws sso login with the custom browser
                result = subprocess.run(
                    ['aws', 'sso', 'login'],
                    check=False, env=env,
                    capture_output=False,
                    text=True
                )

                if result.returncode != 0:
                    sys.exit(1)
        else:
            # No custom profile - run aws sso login normally
            result = subprocess.run(
                ['aws', 'sso', 'login'],
                check=False, env=env,
                capture_output=False,
                text=True
            )

            if result.returncode != 0:
                sys.exit(1)

    except FileNotFoundError:
        click.echo("Error: 'aws' CLI not found", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error during SSO login: {e}", err=True)
        sys.exit(1)


def ensure_sso_login(profile_name: str | None = None):
    """
    Ensure SSO credentials are valid, performing login if needed.

    Args:
        profile_name: Chrome profile name to use for opening the browser
    """
    if not check_sso_credentials_valid():
        perform_sso_login(profile_name)


@click.command()
@click.argument('command', nargs=-1, required=True)
def main(command):
    """
    AWS SSO login wrapper that opens in a specific Chrome profile.

    Check SSO credentials, login if needed, then execute command.

    Example: aws-sso-wrapper -- aws sts get-caller-identity
    """
    # Get Chrome profile from environment variable
    profile_identifier = os.environ.get('CHROME_PROFILE_IDENTIFIER')

    profile_name = None
    if profile_identifier:
        profile_name = find_chrome_profile(profile_identifier)

    # Ensure SSO credentials are valid
    ensure_sso_login(profile_name)

    # Execute the wrapped command
    try:
        result = subprocess.run(command, check=False)
        sys.exit(result.returncode)
    except FileNotFoundError:
        click.echo(f"Error: Command '{command[0]}' not found", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
