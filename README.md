# Proton MCP Server

A Model Context Protocol (MCP) server that provides AI assistants with access to ProtonMail functionality through the Proton Bridge. Enables email management, junk filtering, and automatic unsubscription directly from Claude Desktop and other MCP-compatible AI tools.

## Features

### 📧 Core Email Operations
- **Search emails** with IMAP queries and filtering
- **Send emails** with reply-to support
- **Retrieve full email content** including attachments info
- **Move emails** between folders (Inbox, Spam, Trash, etc.)
- **Get recent emails** within specified time ranges

### 🛡️ Advanced Junk Filtering  
- **Pattern-based spam detection** using regular expressions
- **Bulk email analysis** with junk scoring (unlikely/low/medium/high)
- **Auto-move to Spam folder** for detected junk emails
- **Smart filtering** that learns from common spam patterns
- **Whitelist-friendly** - focuses on obvious spam indicators

### 🚫 Automatic Unsubscribe
- **RFC 2369 compliance** - parses List-Unsubscribe headers
- **RFC 8058 one-click** unsubscribe support
- **Bulk unsubscribe** from multiple mailing lists
- **Mailing list detection** - identifies frequent senders
- **Safety controls** - all actions require explicit confirmation

## Prerequisites

1. **ProtonMail Account** - Any ProtonMail plan (Free/Plus/Business)
2. **Proton Bridge** - Downloaded and running locally
   - Get it from: https://proton.me/mail/bridge
   - Must be running during MCP server operation
3. **Claude Desktop** - For AI integration
   - Download from: https://claude.ai/download

## Installation

### 1. Clone and Setup
```bash
git clone <repository-url>
cd proton-mcp-server
```

### 2. Set Up Virtual Environment
To isolate dependencies and avoid conflicts with other Python projects, create and activate a virtual environment:

```bash
# Create a virtual environment named 'venv'
python3 -m venv venv

# Activate the virtual environment
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

Once activated, your terminal prompt should change to indicate the virtual environment is active (e.g., `(venv)`). To deactivate the virtual environment later, simply run:
```bash
deactivate
```

### 3. Install Dependencies
With the virtual environment activated, install the required dependencies from `requirements.txt`:

```bash
pip install -r requirements.txt
```

To ensure reproducibility, verify that all dependencies are installed correctly by running:
```bash
pip list
```

### 4. Configure Environment
```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or your preferred editor
```

Update `.env` with your Proton details:
```env
PROTON_EMAIL=your-email@proton.me
PROTON_BRIDGE_PASSWORD=your-bridge-app-password
```

**Getting your Bridge password:**
1. Open Proton Bridge application
2. Go to Settings → Account
3. Generate or copy your Bridge password (not your regular Proton password!)

### 5. Configure Claude Desktop

Edit your Claude Desktop configuration file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
- **Windows**: `%APPDATA%\\Claude\\claude_desktop_config.json`

Add this MCP server configuration:
```json
{
  "mcpServers": {
    "proton-email": {
      "command": "/path/to/your/proton-mcp-server/venv/bin/python",
      "args": ["/path/to/your/proton-mcp-server/proton-email-server.py"],
      "env": {
        "BRIDGE_IMAP_HOST": "127.0.0.1",
        "BRIDGE_IMAP_PORT": "1143", 
        "BRIDGE_SMTP_HOST": "127.0.0.1",
        "BRIDGE_SMTP_PORT": "1025",
        "PROTON_EMAIL": "your-email@proton.me",
        "PROTON_BRIDGE_PASSWORD": "your-bridge-app-password"
      }
    }
  }
}
```

**Replace the paths** with your actual system paths.

### 6. Restart Claude Desktop

Completely quit and restart Claude Desktop for the configuration to take effect.

## Usage Examples

### Basic Email Operations
```
# Search recent emails
search_emails(query="ALL", limit=10)

# Get specific email content
get_email_content(email_id="123")

# Send an email
send_email(to="friend@example.com", subject="Hello", body="Hi there!")
```

### Junk Email Filtering
```
# Analyze emails for junk
filter_junk_emails(limit=20, action="analyze")

# Auto-move junk to Spam folder
filter_junk_emails(limit=20, action="move_to_spam")

# Search emails excluding junk
search_emails_filtered(query="ALL", exclude_junk=true)
```

### Automatic Unsubscribe
```
# Find unsubscribe opportunities
bulk_find_unsubscribe_opportunities(days=30)

# Unsubscribe from specific email
unsubscribe_from_email(email_id="123", confirm=true)

# Identify mailing list senders  
get_mailing_list_senders(days=30, min_emails=3)
```

## Available MCP Tools

| Tool | Description |
|------|-------------|
| `search_emails` | Search emails with IMAP queries |
| `get_email_content` | Get full content of specific email |
| `send_email` | Send email via SMTP |
| `get_recent_emails` | Get emails from recent days |
| `filter_junk_emails` | Analyze/filter junk emails |
| `analyze_email_for_junk` | Detailed junk analysis |
| `move_email_to_folder` | Move emails between folders |
| `get_mailboxes` | List available folders |
| `search_emails_filtered` | Search with junk filtering |
| `find_unsubscribe_links` | Find unsubscribe methods |
| `unsubscribe_from_email` | Execute unsubscribe |
| `bulk_find_unsubscribe_opportunities` | Bulk unsubscribe discovery |
| `get_mailing_list_senders` | Identify frequent senders |

## Security & Privacy

- **Local operation** - All processing happens on your machine
- **No data collection** - No analytics or tracking
- **Proton Bridge required** - Uses official Proton encryption
- **Standard protocols** - IMAP/SMTP only, no proprietary APIs
- **Safety controls** - Destructive actions require confirmation

## Troubleshooting

### Connection Issues
- Ensure Proton Bridge is running and logged in
- Check that ports 1143 (IMAP) and 1025 (SMTP) are available
- Verify your Bridge password (not your regular Proton password)

### Claude Desktop Integration
- Restart Claude Desktop completely after config changes
- Check file paths in configuration are absolute paths
- Ensure Python virtual environment is activated

### Performance
- Large mailboxes may take time to analyze
- Consider using smaller `limit` parameters for testing
- Bulk operations include rate limiting to be respectful

## Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

## License

This project is open source. Please respect ProtonMail's Terms of Service when using this tool.

## Disclaimer

This tool is not affiliated with or endorsed by Proton AG. Use at your own discretion and ensure compliance with your organization's email policies.