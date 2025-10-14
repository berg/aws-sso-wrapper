# aws-sso-wrapper

AWS SSO login wrapper that opens authentication URLs in a specific Chrome profile.

## Features

- **Chrome Profile Detection**: Automatically finds Chrome profiles based on logged-in Google account domain/email
- **Automatic SSO Login**: Ensures valid AWS SSO credentials before executing commands
- **macOS Support**: Built specifically for macOS

## Installation

### For Development

```bash
# Clone and install locally
git clone <repo-url>
cd aws-sso-wrapper
uv sync
```

### Using uvx (Recommended)

Once published or available locally:

```bash
# Run directly without installation
uvx --from . aws-sso-wrapper -- aws sts get-caller-identity

# Or install globally with pipx/uv
uv tool install .
```

### Using pip

```bash
pip install -e .
```

## Usage

### Setup

Set the `CHROME_PROFILE_IDENTIFIER` environment variable to specify which Chrome profile to use:

```bash
# By domain
export CHROME_PROFILE_IDENTIFIER="example.com"

# Or by full email
export CHROME_PROFILE_IDENTIFIER="user@example.com"
```

### Running Commands

Ensure AWS SSO credentials are valid before running a command:

```bash
# The -- separates the wrapper args from the command to execute
aws-sso-wrapper -- aws sts get-caller-identity

# Another example
aws-sso-wrapper -- aws s3 ls
```

This will:
1. Check if AWS SSO credentials are valid
2. If invalid, initiate SSO login (opening browser in specified Chrome profile)
3. Execute the command once credentials are valid

## How It Works

### Chrome Profile Detection

The tool searches Chrome's profile directories (`~/Library/Application Support/Google/Chrome/`) and reads the `Preferences` file to find profiles with matching Google account emails.

### AWS SSO Credential Validation

Checks the AWS SSO cache directory (`~/.aws/sso/cache/`) for valid access tokens by:
1. Reading cache JSON files
2. Checking the `expiresAt` timestamp
3. Comparing against current time (UTC)

### SSO Login Flow

When credentials need refresh:
1. Reads AWS config (`~/.aws/config`) for SSO settings
2. Invokes `aws sso login` with a custom `BROWSER` environment variable
3. The custom browser launcher opens URLs in the specified Chrome profile
4. User completes authentication in the correct browser profile

## Requirements

- macOS (for Chrome profile detection and notifications)
- Python 3.13+
- AWS CLI installed and configured with SSO
- Google Chrome with at least one profile

## Environment Variables

- `CHROME_PROFILE_IDENTIFIER`: Domain or email to identify Chrome profile (required for profile-specific login)

## Examples

### Shell Alias

Add to your `.zshrc` or `.bashrc`:

```bash
export CHROME_PROFILE_IDENTIFIER="work-email@company.com"
alias aws-work='aws-sso-wrapper -- aws'
```

Then use:
```bash
aws-work sts get-caller-identity
aws-work s3 ls
```

## Troubleshooting

**Profile not found**: Ensure you're logged into Chrome with the Google account matching `CHROME_PROFILE_IDENTIFIER`.

**AWS CLI not found**: Install AWS CLI v2 from https://aws.amazon.com/cli/

**Credentials still invalid**: Run `aws sso login` manually first to ensure your AWS config is correct.
