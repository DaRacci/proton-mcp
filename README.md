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
