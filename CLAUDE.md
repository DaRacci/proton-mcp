# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python MCP (Model Context Protocol) server that provides email functionality for ProtonMail via the Proton Bridge. The server acts as a bridge between AI assistants and ProtonMail, allowing programmatic access to email operations.

## Architecture

**Core Components:**
- `ProtonEmailClient` class (`proton-email-server.py:27-184`): Main email client that handles IMAP/SMTP connections to Proton Bridge
- MCP server setup using FastMCP framework (`proton-email-server.py:25`)
- Four main MCP tools: `search_emails`, `get_email_content`, `send_email`, `get_recent_emails`
- One MCP resource: `inbox_summary` for getting inbox overview

**Connection Architecture:**
- Connects to local Proton Bridge instance (default: 127.0.0.1:1143 for IMAP, 127.0.0.1:1025 for SMTP)
- Uses standard IMAP/SMTP protocols with authentication via Proton Bridge credentials
- Environment-based configuration for connection details and credentials

## Development Commands

**Running the Server:**
```bash
source venv/bin/activate
python proton-email-server.py
```

**Virtual Environment:**
- Uses Python 3.13 virtual environment in `venv/` directory
- Activate with: `source venv/bin/activate`
- No package manifest files (requirements.txt, pyproject.toml) present - dependencies managed in virtual environment

## Configuration

**Required Environment Variables (.env file):**
- `BRIDGE_IMAP_HOST`: Proton Bridge IMAP host (default: 127.0.0.1)
- `BRIDGE_IMAP_PORT`: Proton Bridge IMAP port (default: 1143)  
- `BRIDGE_SMTP_HOST`: Proton Bridge SMTP host (default: 127.0.0.1)
- `BRIDGE_SMTP_PORT`: Proton Bridge SMTP port (default: 1025)
- `PROTON_EMAIL`: Your ProtonMail email address
- `PROTON_BRIDGE_PASSWORD`: Proton Bridge application password

## Key Features

**Email Operations:**
- Search emails with IMAP queries
- Retrieve full email content by ID
- Send emails with optional reply-to functionality
- Get recent emails within specified time range
- MIME header decoding and email body extraction

**MCP Integration:**
- Exposes email functionality as MCP tools for AI assistant integration
- Provides inbox summary resource
- Error handling with descriptive messages for failed operations

## Junk Email Filtering

**Core Detection Logic (`ProtonEmailClient.is_junk_email`):**
- Pattern-based spam detection using regular expressions
- Analyzes subject lines, sender addresses, and email body content
- Scoring system: unlikely (0), low (1), medium (2-3), high (4+) junk likelihood
- Detects common spam patterns: urgent actions, suspicious offers, phishing attempts

**Detection Criteria:**
- Subject patterns: urgent actions, lottery/money offers, pharmaceutical spam
- Sender patterns: suspicious domains (.tk, .ml, .ga), generic admin/support addresses  
- Body content: phishing attempts, crypto scams, inheritance fraud
- Format issues: excessive capitals, multiple exclamation marks

**New MCP Tools:**
- `filter_junk_emails`: Analyze emails in bulk, optionally move spam to Spam folder
- `analyze_email_for_junk`: Detailed junk analysis for specific email
- `move_email_to_folder`: Move emails between folders (Spam, Trash, Archive, etc.)
- `get_mailboxes`: List available folders
- `search_emails_filtered`: Enhanced search with junk filtering option

## Automatic Unsubscribe

**Core Detection Logic (`ProtonEmailClient.find_unsubscribe_links`):**
- RFC 2369 List-Unsubscribe header parsing (mailto: and https: URLs)
- RFC 8058 One-Click unsubscribe detection and support
- HTML body analysis for unsubscribe link extraction
- Text body pattern matching for unsubscribe URLs
- Deduplication of multiple unsubscribe methods per email

**Unsubscribe Execution (`ProtonEmailClient.execute_unsubscribe`):**
- HTTP GET/POST requests with browser-like headers
- One-click unsubscribe support via POST with special headers
- Response validation and confirmation detection
- Timeout and error handling for unreliable unsubscribe services

**New MCP Tools:**
- `find_unsubscribe_links`: Find all unsubscribe methods in specific email
- `unsubscribe_from_email`: Execute unsubscribe for specific email (requires confirm=True)
- `bulk_find_unsubscribe_opportunities`: Scan recent emails for unsubscribe opportunities  
- `get_mailing_list_senders`: Identify frequent senders (potential mailing lists)

**Safety Features:**
- All unsubscribe actions require explicit `confirm=True` parameter
- Dry-run modes for testing without actual execution
- Request delays between bulk operations to be respectful
- Comprehensive logging and error reporting

## Folder Management

**Core Functionality (`ProtonEmailClient.create_folder`, `ProtonEmailClient.delete_folder`):**
- Create new email folders/mailboxes via IMAP CREATE command
- Delete existing folders via IMAP DELETE command
- Integration with existing folder listing and email moving capabilities

**New MCP Tools:**
- `create_folder`: Create new email folders
- `delete_folder`: Delete existing folders
- `get_mailboxes`: List available folders (existing)
- `move_email_to_folder`: Move emails between folders (existing)

## Email Filtering Rules

**Core Architecture (`ProtonEmailClient` filtering methods):**
- JSON-based rule storage in `filter_rules.json` file
- Rule-based email processing with conditions and actions
- Support for multiple condition types and automated actions
- Rule statistics tracking (emails processed, last applied)

**Rule Structure:**
- **Conditions**: `from`, `to`, `subject_contains`, `subject_equals`, `body_contains`, `sender_domain`
- **Actions**: `move_to_folder`, `mark_as_read`, `mark_as_important`, `delete`
- **Metadata**: Rule ID, name, enabled status, creation date, usage statistics

**Core Processing Logic (`ProtonEmailClient.apply_filter_rules`):**
- Loads all enabled rules from JSON storage
- Processes emails in specified mailbox against rule conditions
- Executes matching actions (move, mark, delete) for qualifying emails
- Updates rule statistics and saves back to storage
- Returns detailed results of processing and actions taken

**New MCP Tools:**
- `create_filter_rule`: Create new filtering rules with JSON conditions/actions
- `list_filter_rules`: Get all existing filtering rules
- `delete_filter_rule`: Remove filtering rules by ID
- `update_filter_rule`: Modify existing rules (enable/disable, change conditions/actions)
- `apply_filter_rules`: Manually apply all enabled rules to mailbox emails
- `get_filter_rule_examples`: Get example rule formats and common patterns

**Rule Examples:**
- GitHub notifications → move to "GitHub" folder + mark as read
- Marketing emails (contains "unsubscribe") → move to "Marketing" folder  
- Important client emails → move to "VIP" folder + mark as important
- Newsletter emails → auto-organize by sender domain

**Safety Features:**
- Rule validation for supported conditions and actions
- Unique rule naming enforcement
- Detailed error handling and logging
- Rule statistics for monitoring effectiveness

## Bulk Operations & Performance Optimization

**Core Efficiency Improvements:**
- **Bulk Email Retrieval**: `get_bulk_emails()` and `get_bulk_emails_with_html()` methods fetch multiple emails in batches using IMAP pipelining
- **Batch Processing**: Process emails in configurable chunks (50-100 emails per batch) to optimize memory usage and IMAP performance
- **Bulk IMAP Operations**: `bulk_move_emails()`, `bulk_mark_emails()`, `bulk_delete_emails()` use comma-separated ID lists for efficient server communication
- **Optimized Rule Processing**: Filter rules now queue actions and execute them in bulk rather than per-email

**Performance Improvements:**
- **10-50x faster** for bulk operations (moving 100 emails: ~2 seconds vs ~30 seconds individually)
- **Memory efficient** chunked processing for large email volumes (200+ emails)
- **Fallback handling** for IMAP server limitations with graceful degradation to individual operations
- **Batch size optimization** based on email content type (text vs HTML)

**New Bulk MCP Tools:**
- `bulk_move_emails`: Move multiple emails by comma-separated IDs
- `bulk_mark_emails_as_read`: Mark multiple emails as read/unread
- `bulk_mark_emails_as_important`: Flag multiple emails as important
- `bulk_delete_emails`: Bulk delete (to Trash or permanent)
- `bulk_get_emails`: Efficiently retrieve multiple complete emails
- `apply_filter_rules_optimized`: Process large email volumes with chunked filtering

**Optimized Existing Tools:**
- `filter_junk_emails`: Now uses bulk retrieval and bulk moves for spam
- `apply_filter_rules`: Queues actions and executes them in bulk
- `bulk_find_unsubscribe_opportunities`: Uses bulk HTML email retrieval

**Usage Examples:**
```
# Move 50 emails to folder efficiently
bulk_move_emails("1,2,3,4,5,...,50", "Archive", "INBOX")

# Process 200 emails with filter rules in 50-email chunks  
apply_filter_rules_optimized("INBOX", 200, 50)

# Mark 25 emails as read in one operation
bulk_mark_emails_as_read("101,102,103,...,125", "INBOX", true)
```

## Dependencies

Key external dependencies (installed in venv):
- `mcp.server.fastmcp`: FastMCP framework for MCP server
- `python-dotenv`: Environment variable loading
- `requests`: HTTP client for unsubscribe functionality
- `json`: JSON handling for filter rules storage
- Standard library: `imaplib`, `smtplib`, `email`, `logging`, `re`