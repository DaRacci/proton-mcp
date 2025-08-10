import asyncio
import imaplib
import smtplib
import email
import os
import logging
import re
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from typing import Any, List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
import time

from mcp.server.fastmcp import FastMCP
from mcp.types import Resource, Tool, TextContent
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MCP Server instance
mcp = FastMCP("ProtonEmailServer")

class ProtonEmailClient:
    def __init__(self):
        self.imap_host = os.getenv("BRIDGE_IMAP_HOST", "127.0.0.1")
        self.imap_port = int(os.getenv("BRIDGE_IMAP_PORT", "1143"))
        self.smtp_host = os.getenv("BRIDGE_SMTP_HOST", "127.0.0.1")
        self.smtp_port = int(os.getenv("BRIDGE_SMTP_PORT", "1025"))
        self.email = os.getenv("PROTON_EMAIL")
        self.password = os.getenv("PROTON_BRIDGE_PASSWORD")
        
        if not all([self.email, self.password]):
            raise ValueError("Email credentials not found in environment variables")
    
    def connect_imap(self):
        """Connect to IMAP server"""
        try:
            mail = imaplib.IMAP4(self.imap_host, self.imap_port)
            mail.login(self.email, self.password)
            return mail
        except Exception as e:
            logger.error(f"IMAP connection failed: {e}")
            raise
    
    def connect_smtp(self):
        """Connect to SMTP server"""
        try:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls()
            server.login(self.email, self.password)
            return server
        except Exception as e:
            logger.error(f"SMTP connection failed: {e}")
            raise
    
    def decode_mime_words(self, text):
        """Decode MIME encoded words"""
        if text is None:
            return ""
        decoded_words = decode_header(text)
        decoded_text = ""
        for word, encoding in decoded_words:
            if isinstance(word, bytes):
                word = word.decode(encoding or 'utf-8', errors='ignore')
            decoded_text += word
        return decoded_text
    
    def search_emails(self, query: str = "ALL", mailbox: str = "INBOX", limit: int = 10):
        """Search emails in specified mailbox"""
        mail = self.connect_imap()
        try:
            mail.select(mailbox)
            status, messages = mail.search(None, query)
            
            if status != 'OK':
                return []
            
            message_ids = messages[0].split()
            # Get most recent emails (reverse order)
            message_ids = message_ids[-limit:]
            
            emails = []
            for msg_id in reversed(message_ids):
                status, msg_data = mail.fetch(msg_id, '(RFC822)')
                if status == 'OK':
                    raw_email = msg_data[0][1]
                    email_message = email.message_from_bytes(raw_email)
                    
                    # Extract email details
                    subject = self.decode_mime_words(email_message['Subject'])
                    from_addr = self.decode_mime_words(email_message['From'])
                    date = email_message['Date']
                    
                    # Get email body
                    body = self.get_email_body(email_message)
                    
                    emails.append({
                        'id': msg_id.decode(),
                        'subject': subject,
                        'from': from_addr,
                        'date': date,
                        'body': body[:500] + "..." if len(body) > 500 else body  # Truncate for preview
                    })
            
            return emails
        finally:
            mail.close()
            mail.logout()
    
    def get_email_body(self, email_message):
        """Extract email body text"""
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    except:
                        continue
        else:
            try:
                body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                body = str(email_message.get_payload())
        
        return body
    
    def get_full_email(self, email_id: str, mailbox: str = "INBOX"):
        """Get full email content by ID"""
        mail = self.connect_imap()
        try:
            mail.select(mailbox)
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                return None
            
            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            return {
                'id': email_id,
                'subject': self.decode_mime_words(email_message['Subject']),
                'from': self.decode_mime_words(email_message['From']),
                'to': self.decode_mime_words(email_message['To']),
                'date': email_message['Date'],
                'body': self.get_email_body(email_message)
            }
        finally:
            mail.close()
            mail.logout()
    
    def send_email(self, to: str, subject: str, body: str, reply_to_id: str = None):
        """Send email via SMTP"""
        server = self.connect_smtp()
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email
            msg['To'] = to
            msg['Subject'] = subject
            
            # Add reply headers if replying to an email
            if reply_to_id:
                msg['In-Reply-To'] = reply_to_id
                msg['References'] = reply_to_id
            
            msg.attach(MIMEText(body, 'plain'))
            
            server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
        finally:
            server.quit()
    
    def is_junk_email(self, email_data: Dict) -> Dict[str, Any]:
        """
        Analyze email to determine if it's likely junk/spam.
        Returns a dictionary with junk detection results.
        """
        junk_indicators = []
        junk_score = 0
        
        subject = email_data.get('subject', '').lower()
        from_addr = email_data.get('from', '').lower()
        body = email_data.get('body', '').lower()
        
        # Common spam subject patterns
        spam_subject_patterns = [
            r'urgent.*action.*required',
            r'congratulations.*won',
            r'free.*money|money.*free',
            r'limited.*time.*offer',
            r'act.*now|click.*here',
            r'viagra|cialis|pharmacy',
            r'increase.*size',
            r'lose.*weight.*fast',
            r'make.*money.*fast',
            r'nigerian.*prince',
            r'tax.*refund',
            r'security.*alert',
            r're:.*re:.*re:',  # Multiple "re:" forwards
        ]
        
        for pattern in spam_subject_patterns:
            if re.search(pattern, subject):
                junk_indicators.append(f"Suspicious subject pattern: {pattern}")
                junk_score += 2
        
        # Check for suspicious sender patterns
        suspicious_sender_patterns = [
            r'noreply@.*\.tk$',  # Suspicious TLDs
            r'.*@.*\.ml$',
            r'.*@.*\.ga$',
            r'admin@.*',
            r'support@.*',
            r'security@.*',
        ]
        
        for pattern in suspicious_sender_patterns:
            if re.search(pattern, from_addr):
                junk_indicators.append(f"Suspicious sender pattern: {pattern}")
                junk_score += 1
        
        # Check body content for spam indicators
        spam_body_patterns = [
            r'click.*here.*now',
            r'urgent.*respond',
            r'verify.*account.*immediately',
            r'suspended.*account',
            r'winner.*lottery',
            r'inheritance.*million',
            r'bitcoin.*investment',
            r'crypto.*opportunity',
        ]
        
        for pattern in spam_body_patterns:
            if re.search(pattern, body):
                junk_indicators.append(f"Suspicious body content: {pattern}")
                junk_score += 2
        
        # Check for excessive caps
        if len(subject) > 10:
            caps_ratio = sum(1 for c in subject if c.isupper()) / len(subject)
            if caps_ratio > 0.5:
                junk_indicators.append("Excessive capital letters in subject")
                junk_score += 1
        
        # Check for excessive exclamation marks
        exclamation_count = subject.count('!') + body[:500].count('!')
        if exclamation_count > 3:
            junk_indicators.append(f"Excessive exclamation marks ({exclamation_count})")
            junk_score += 1
        
        # Determine junk likelihood
        if junk_score >= 4:
            likelihood = "high"
        elif junk_score >= 2:
            likelihood = "medium"
        elif junk_score >= 1:
            likelihood = "low"
        else:
            likelihood = "unlikely"
        
        return {
            "is_likely_junk": junk_score >= 2,
            "junk_score": junk_score,
            "likelihood": likelihood,
            "indicators": junk_indicators,
            "email_id": email_data.get('id')
        }
    
    def move_email_to_folder(self, email_id: str, target_folder: str, source_folder: str = "INBOX"):
        """Move an email from one folder to another"""
        mail = self.connect_imap()
        try:
            mail.select(source_folder)
            # Copy email to target folder
            result = mail.copy(email_id, target_folder)
            if result[0] == 'OK':
                # Mark as deleted in source folder
                mail.store(email_id, '+FLAGS', '\\Deleted')
                mail.expunge()
                return True
            else:
                logger.error(f"Failed to copy email to {target_folder}: {result}")
                return False
        except Exception as e:
            logger.error(f"Failed to move email: {e}")
            return False
        finally:
            mail.close()
            mail.logout()
    
    def get_mailbox_list(self):
        """Get list of available mailboxes/folders"""
        mail = self.connect_imap()
        try:
            status, mailboxes = mail.list()
            if status == 'OK':
                folder_list = []
                for mailbox in mailboxes:
                    # Parse mailbox name from IMAP response
                    parts = mailbox.decode().split('"')
                    if len(parts) >= 3:
                        folder_name = parts[-2]
                        folder_list.append(folder_name)
                return folder_list
            return []
        except Exception as e:
            logger.error(f"Failed to get mailbox list: {e}")
            return []
        finally:
            mail.close()
            mail.logout()
    
    def get_full_email_with_html(self, email_id: str, mailbox: str = "INBOX"):
        """Get full email content including HTML parts for link extraction"""
        mail = self.connect_imap()
        try:
            mail.select(mailbox)
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                return None
            
            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            # Extract both text and HTML content
            text_content = ""
            html_content = ""
            
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    
                    if "attachment" not in content_disposition:
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                content = payload.decode('utf-8', errors='ignore')
                                if content_type == "text/plain":
                                    text_content += content
                                elif content_type == "text/html":
                                    html_content += content
                        except:
                            continue
            else:
                try:
                    payload = email_message.get_payload(decode=True)
                    if payload:
                        content = payload.decode('utf-8', errors='ignore')
                        if email_message.get_content_type() == "text/html":
                            html_content = content
                        else:
                            text_content = content
                except:
                    pass
            
            return {
                'id': email_id,
                'subject': self.decode_mime_words(email_message['Subject']),
                'from': self.decode_mime_words(email_message['From']),
                'to': self.decode_mime_words(email_message['To']),
                'date': email_message['Date'],
                'text_body': text_content,
                'html_body': html_content,
                'list_unsubscribe': email_message.get('List-Unsubscribe', ''),
                'list_unsubscribe_post': email_message.get('List-Unsubscribe-Post', '')
            }
        finally:
            mail.close()
            mail.logout()
    
    def find_unsubscribe_links(self, email_data: Dict) -> Dict[str, Any]:
        """
        Find unsubscribe links and methods in an email.
        Returns various unsubscribe options found.
        """
        unsubscribe_methods = []
        
        # Check List-Unsubscribe header (RFC 2369)
        list_unsubscribe = email_data.get('list_unsubscribe', '')
        if list_unsubscribe:
            # Parse mailto and HTTP URLs from List-Unsubscribe header
            mailto_matches = re.findall(r'<mailto:([^>]+)>', list_unsubscribe)
            http_matches = re.findall(r'<(https?://[^>]+)>', list_unsubscribe)
            
            for mailto in mailto_matches:
                unsubscribe_methods.append({
                    'type': 'mailto',
                    'address': mailto,
                    'method': 'email'
                })
            
            for url in http_matches:
                unsubscribe_methods.append({
                    'type': 'http',
                    'url': url,
                    'method': 'click'
                })
        
        # Check for one-click unsubscribe (RFC 8058)
        list_unsubscribe_post = email_data.get('list_unsubscribe_post', '')
        if list_unsubscribe_post and 'List-Unsubscribe=One-Click' in list_unsubscribe_post:
            # Find the corresponding HTTP URL for one-click
            for method in unsubscribe_methods:
                if method['type'] == 'http':
                    method['one_click'] = True
                    method['method'] = 'one_click'
        
        # Extract unsubscribe links from email body
        text_body = email_data.get('text_body', '')
        html_body = email_data.get('html_body', '')
        
        # Common unsubscribe link patterns
        unsubscribe_patterns = [
            r'(?i)unsubscribe.*?https?://[^\s<>"]+',
            r'(?i)https?://[^\s<>"]*unsubscribe[^\s<>"]*',
            r'(?i)https?://[^\s<>"]*opt.?out[^\s<>"]*',
            r'(?i)https?://[^\s<>"]*remove[^\s<>"]*',
        ]
        
        # Search in HTML content for href attributes
        if html_body:
            html_unsubscribe_patterns = [
                r'(?i)<a[^>]*href=["\']([^"\']*unsubscribe[^"\']*)["\'][^>]*>',
                r'(?i)<a[^>]*href=["\']([^"\']*opt.?out[^"\']*)["\'][^>]*>',
                r'(?i)<a[^>]*href=["\']([^"\']*remove[^"\']*)["\'][^>]*>',
            ]
            
            for pattern in html_unsubscribe_patterns:
                matches = re.findall(pattern, html_body)
                for match in matches:
                    if match.startswith('http'):
                        unsubscribe_methods.append({
                            'type': 'http',
                            'url': match,
                            'method': 'click',
                            'source': 'html_body'
                        })
        
        # Search in text content
        for pattern in unsubscribe_patterns:
            matches = re.findall(pattern, text_body)
            for match in matches:
                # Extract just the URL part
                url_match = re.search(r'https?://[^\s<>"]+', match)
                if url_match:
                    unsubscribe_methods.append({
                        'type': 'http',
                        'url': url_match.group(),
                        'method': 'click',
                        'source': 'text_body'
                    })
        
        # Remove duplicates
        seen_urls = set()
        unique_methods = []
        for method in unsubscribe_methods:
            identifier = method.get('url') or method.get('address')
            if identifier not in seen_urls:
                seen_urls.add(identifier)
                unique_methods.append(method)
        
        return {
            'email_id': email_data.get('id'),
            'subject': email_data.get('subject'),
            'from': email_data.get('from'),
            'unsubscribe_methods': unique_methods,
            'total_methods': len(unique_methods),
            'has_one_click': any(method.get('one_click', False) for method in unique_methods)
        }
    
    def execute_unsubscribe(self, unsubscribe_method: Dict, timeout: int = 10) -> Dict[str, Any]:
        """
        Execute an unsubscribe request.
        """
        result = {
            'method': unsubscribe_method,
            'success': False,
            'message': '',
            'status_code': None
        }
        
        try:
            if unsubscribe_method['type'] == 'mailto':
                # For mailto unsubscribe, we would send an email
                # This is more complex and requires careful handling
                result['message'] = "Mailto unsubscribe requires manual email sending"
                result['success'] = False
                
            elif unsubscribe_method['type'] == 'http':
                url = unsubscribe_method['url']
                
                # Set up headers to look like a real browser
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                }
                
                if unsubscribe_method.get('one_click'):
                    # RFC 8058 one-click unsubscribe
                    headers['List-Unsubscribe'] = 'One-Click'
                    response = requests.post(url, headers=headers, timeout=timeout, allow_redirects=True)
                else:
                    # Regular HTTP GET request
                    response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
                
                result['status_code'] = response.status_code
                
                if response.status_code in [200, 201, 202, 204]:
                    result['success'] = True
                    result['message'] = f"Unsubscribe request successful (HTTP {response.status_code})"
                else:
                    result['message'] = f"Unsubscribe request failed with HTTP {response.status_code}"
                
                # Check response content for confirmation
                if result['success']:
                    content = response.text.lower()
                    confirmation_phrases = [
                        'unsubscribed', 'removed', 'opted out', 'no longer receive',
                        'successfully unsubscribed', 'email address has been removed'
                    ]
                    if any(phrase in content for phrase in confirmation_phrases):
                        result['message'] += " - Confirmation detected in response"
                
        except requests.exceptions.Timeout:
            result['message'] = f"Request timed out after {timeout} seconds"
        except requests.exceptions.ConnectionError:
            result['message'] = "Connection error - could not reach unsubscribe URL"
        except requests.exceptions.RequestException as e:
            result['message'] = f"Request failed: {str(e)}"
        except Exception as e:
            result['message'] = f"Unexpected error: {str(e)}"
        
        return result

# Initialize email client
email_client = ProtonEmailClient()

# MCP Tools
@mcp.tool()
def search_emails(query: str = "ALL", mailbox: str = "INBOX", limit: int = 10) -> List[dict]:
    """
    Search for emails in your Proton mailbox.
    
    Args:
        query: IMAP search query (e.g., 'FROM "sender@example.com"', 'SUBJECT "important"')
        mailbox: Mailbox to search in (default: INBOX)
        limit: Maximum number of emails to return (default: 10)
    
    Returns:
        List of email summaries with id, subject, from, date, and body preview
    """
    try:
        return email_client.search_emails(query, mailbox, limit)
    except Exception as e:
        return [{"error": f"Failed to search emails: {str(e)}"}]

@mcp.tool()
def get_email_content(email_id: str, mailbox: str = "INBOX") -> dict:
    """
    Get the full content of a specific email.
    
    Args:
        email_id: The ID of the email to retrieve
        mailbox: Mailbox containing the email (default: INBOX)
    
    Returns:
        Full email content including subject, from, to, date, and complete body
    """
    try:
        email_data = email_client.get_full_email(email_id, mailbox)
        if email_data:
            return email_data
        else:
            return {"error": "Email not found"}
    except Exception as e:
        return {"error": f"Failed to get email: {str(e)}"}

@mcp.tool()
def send_email(to: str, subject: str, body: str, reply_to_id: str = None) -> dict:
    """
    Send an email via Proton Mail.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body content
        reply_to_id: Optional ID of email being replied to
    
    Returns:
        Success status and message
    """
    try:
        success = email_client.send_email(to, subject, body, reply_to_id)
        if success:
            return {"status": "success", "message": "Email sent successfully"}
        else:
            return {"status": "error", "message": "Failed to send email"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to send email: {str(e)}"}

@mcp.tool()
def get_recent_emails(days: int = 7, mailbox: str = "INBOX") -> List[dict]:
    """
    Get recent emails from the specified number of days.
    
    Args:
        days: Number of days back to search (default: 7)
        mailbox: Mailbox to search in (default: INBOX)
    
    Returns:
        List of recent emails
    """
    try:
        since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
        query = f'SINCE "{since_date}"'
        return email_client.search_emails(query, mailbox, 20)
    except Exception as e:
        return [{"error": f"Failed to get recent emails: {str(e)}"}]

@mcp.tool()
def filter_junk_emails(mailbox: str = "INBOX", limit: int = 20, action: str = "analyze") -> List[dict]:
    """
    Filter and analyze emails for junk/spam content.
    
    Args:
        mailbox: Mailbox to analyze (default: INBOX)
        limit: Maximum number of emails to analyze (default: 20)
        action: Action to take - "analyze" (default) or "move_to_spam"
    
    Returns:
        List of emails with junk analysis results
    """
    try:
        # Get recent emails
        emails = email_client.search_emails("ALL", mailbox, limit)
        if not emails or (len(emails) == 1 and "error" in emails[0]):
            return emails
        
        filtered_results = []
        moved_count = 0
        
        for email_item in emails:
            # Get full email content for better analysis
            full_email = email_client.get_full_email(email_item['id'], mailbox)
            if not full_email:
                continue
                
            # Analyze for junk
            junk_analysis = email_client.is_junk_email(full_email)
            
            # Add original email data to result
            result = {
                **email_item,
                "junk_analysis": junk_analysis
            }
            
            # If action is move_to_spam and email is likely junk
            if action == "move_to_spam" and junk_analysis["is_likely_junk"]:
                try:
                    if email_client.move_email_to_folder(email_item['id'], "Spam", mailbox):
                        result["action_taken"] = "moved_to_spam"
                        moved_count += 1
                    else:
                        result["action_taken"] = "move_failed"
                except Exception as e:
                    result["action_taken"] = f"move_error: {str(e)}"
            
            filtered_results.append(result)
        
        # Add summary
        junk_count = sum(1 for r in filtered_results if r["junk_analysis"]["is_likely_junk"])
        summary = {
            "summary": {
                "total_analyzed": len(filtered_results),
                "junk_detected": junk_count,
                "moved_to_spam": moved_count if action == "move_to_spam" else 0
            }
        }
        filtered_results.insert(0, summary)
        
        return filtered_results
    except Exception as e:
        return [{"error": f"Failed to filter junk emails: {str(e)}"}]

@mcp.tool()
def move_email_to_folder(email_id: str, target_folder: str, source_folder: str = "INBOX") -> dict:
    """
    Move a specific email to a different folder.
    
    Args:
        email_id: The ID of the email to move
        target_folder: Target folder name (e.g., "Spam", "Trash", "Archive")
        source_folder: Source folder name (default: INBOX)
    
    Returns:
        Status of the move operation
    """
    try:
        success = email_client.move_email_to_folder(email_id, target_folder, source_folder)
        if success:
            return {
                "status": "success", 
                "message": f"Email {email_id} moved from {source_folder} to {target_folder}"
            }
        else:
            return {
                "status": "error", 
                "message": f"Failed to move email {email_id}"
            }
    except Exception as e:
        return {"status": "error", "message": f"Error moving email: {str(e)}"}

@mcp.tool()
def get_mailboxes() -> List[str]:
    """
    Get list of available mailboxes/folders.
    
    Returns:
        List of mailbox names
    """
    try:
        return email_client.get_mailbox_list()
    except Exception as e:
        return [f"Error: {str(e)}"]

@mcp.tool()
def analyze_email_for_junk(email_id: str, mailbox: str = "INBOX") -> dict:
    """
    Analyze a specific email for junk/spam indicators.
    
    Args:
        email_id: The ID of the email to analyze
        mailbox: Mailbox containing the email (default: INBOX)
    
    Returns:
        Detailed junk analysis for the email
    """
    try:
        # Get full email content
        email_data = email_client.get_full_email(email_id, mailbox)
        if not email_data:
            return {"error": "Email not found"}
        
        # Analyze for junk
        junk_analysis = email_client.is_junk_email(email_data)
        
        return {
            "email": {
                "id": email_data["id"],
                "subject": email_data["subject"],
                "from": email_data["from"],
                "date": email_data["date"]
            },
            "junk_analysis": junk_analysis
        }
    except Exception as e:
        return {"error": f"Failed to analyze email: {str(e)}"}

@mcp.tool()
def search_emails_filtered(query: str = "ALL", mailbox: str = "INBOX", limit: int = 10, exclude_junk: bool = False) -> List[dict]:
    """
    Search for emails with optional junk filtering.
    
    Args:
        query: IMAP search query (e.g., 'FROM "sender@example.com"', 'SUBJECT "important"')
        mailbox: Mailbox to search in (default: INBOX)  
        limit: Maximum number of emails to return (default: 10)
        exclude_junk: If True, filter out likely junk emails (default: False)
    
    Returns:
        List of email summaries, optionally filtered for junk
    """
    try:
        emails = email_client.search_emails(query, mailbox, limit if not exclude_junk else limit * 2)
        if not emails or (len(emails) == 1 and "error" in emails[0]):
            return emails
        
        if not exclude_junk:
            return emails
        
        # Filter out junk emails
        filtered_emails = []
        for email_item in emails:
            if len(filtered_emails) >= limit:
                break
                
            # Get full email content for junk analysis
            full_email = email_client.get_full_email(email_item['id'], mailbox)
            if full_email:
                junk_analysis = email_client.is_junk_email(full_email)
                if not junk_analysis["is_likely_junk"]:
                    filtered_emails.append(email_item)
        
        return filtered_emails
    except Exception as e:
        return [{"error": f"Failed to search emails: {str(e)}"}]

@mcp.tool()
def find_unsubscribe_links(email_id: str, mailbox: str = "INBOX") -> dict:
    """
    Find unsubscribe links and methods in a specific email.
    
    Args:
        email_id: The ID of the email to analyze
        mailbox: Mailbox containing the email (default: INBOX)
    
    Returns:
        Dictionary with unsubscribe methods found
    """
    try:
        # Get full email content with HTML
        email_data = email_client.get_full_email_with_html(email_id, mailbox)
        if not email_data:
            return {"error": "Email not found"}
        
        # Find unsubscribe methods
        unsubscribe_info = email_client.find_unsubscribe_links(email_data)
        
        return unsubscribe_info
    except Exception as e:
        return {"error": f"Failed to find unsubscribe links: {str(e)}"}

@mcp.tool()
def unsubscribe_from_email(email_id: str, mailbox: str = "INBOX", method_index: int = 0, confirm: bool = False) -> dict:
    """
    Unsubscribe from a mailing list using links found in an email.
    
    Args:
        email_id: The ID of the email containing unsubscribe links
        mailbox: Mailbox containing the email (default: INBOX)
        method_index: Index of unsubscribe method to use (default: 0 for first method)
        confirm: Must be True to actually execute unsubscribe (safety measure)
    
    Returns:
        Result of unsubscribe attempt
    """
    try:
        if not confirm:
            return {
                "error": "Safety measure: set confirm=True to execute unsubscribe",
                "message": "Use find_unsubscribe_links first to see available methods"
            }
        
        # Get full email content with HTML
        email_data = email_client.get_full_email_with_html(email_id, mailbox)
        if not email_data:
            return {"error": "Email not found"}
        
        # Find unsubscribe methods
        unsubscribe_info = email_client.find_unsubscribe_links(email_data)
        
        if not unsubscribe_info['unsubscribe_methods']:
            return {"error": "No unsubscribe methods found in this email"}
        
        if method_index >= len(unsubscribe_info['unsubscribe_methods']):
            return {
                "error": f"Method index {method_index} out of range. Available methods: 0-{len(unsubscribe_info['unsubscribe_methods'])-1}"
            }
        
        # Execute unsubscribe
        method = unsubscribe_info['unsubscribe_methods'][method_index]
        result = email_client.execute_unsubscribe(method)
        
        return {
            "email_info": {
                "id": email_data['id'],
                "subject": email_data['subject'],
                "from": email_data['from']
            },
            "unsubscribe_result": result
        }
    except Exception as e:
        return {"error": f"Failed to unsubscribe: {str(e)}"}

@mcp.tool()
def bulk_find_unsubscribe_opportunities(mailbox: str = "INBOX", days: int = 30, limit: int = 50) -> List[dict]:
    """
    Scan recent emails to find unsubscribe opportunities from mailing lists.
    
    Args:
        mailbox: Mailbox to scan (default: INBOX)
        days: Number of days back to search (default: 30)
        limit: Maximum emails to analyze (default: 50)
    
    Returns:
        List of emails with unsubscribe opportunities
    """
    try:
        # Get recent emails
        since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
        query = f'SINCE "{since_date}"'
        emails = email_client.search_emails(query, mailbox, limit)
        
        if not emails or (len(emails) == 1 and "error" in emails[0]):
            return emails
        
        unsubscribe_opportunities = []
        processed = 0
        
        for email_item in emails:
            processed += 1
            logger.info(f"Analyzing email {processed}/{len(emails)}: {email_item.get('subject', 'No Subject')}")
            
            try:
                # Get full email content
                email_data = email_client.get_full_email_with_html(email_item['id'], mailbox)
                if not email_data:
                    continue
                
                # Find unsubscribe methods
                unsubscribe_info = email_client.find_unsubscribe_links(email_data)
                
                if unsubscribe_info['total_methods'] > 0:
                    # Add basic email info
                    opportunity = {
                        **email_item,
                        "unsubscribe_info": unsubscribe_info
                    }
                    unsubscribe_opportunities.append(opportunity)
                    
            except Exception as e:
                logger.warning(f"Failed to analyze email {email_item['id']}: {e}")
                continue
        
        # Add summary
        summary = {
            "summary": {
                "emails_analyzed": processed,
                "unsubscribe_opportunities": len(unsubscribe_opportunities),
                "one_click_available": sum(1 for opp in unsubscribe_opportunities 
                                         if opp["unsubscribe_info"]["has_one_click"])
            }
        }
        
        return [summary] + unsubscribe_opportunities
    except Exception as e:
        return [{"error": f"Failed to find unsubscribe opportunities: {str(e)}"}]

@mcp.tool()
def get_mailing_list_senders(mailbox: str = "INBOX", days: int = 30, min_emails: int = 2) -> List[dict]:
    """
    Identify frequent senders that might be mailing lists.
    
    Args:
        mailbox: Mailbox to analyze (default: INBOX)
        days: Number of days back to analyze (default: 30)
        min_emails: Minimum number of emails to consider sender as mailing list (default: 2)
    
    Returns:
        List of potential mailing list senders with email counts
    """
    try:
        # Get recent emails
        since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
        query = f'SINCE "{since_date}"'
        emails = email_client.search_emails(query, mailbox, 200)  # Higher limit for analysis
        
        if not emails or (len(emails) == 1 and "error" in emails[0]):
            return emails
        
        # Count emails per sender
        sender_counts = {}
        for email_item in emails:
            from_addr = email_item.get('from', '').strip()
            if from_addr:
                if from_addr not in sender_counts:
                    sender_counts[from_addr] = {
                        'count': 0,
                        'subjects': [],
                        'latest_date': email_item.get('date', '')
                    }
                sender_counts[from_addr]['count'] += 1
                sender_counts[from_addr]['subjects'].append(email_item.get('subject', 'No Subject'))
        
        # Filter for potential mailing lists
        mailing_lists = []
        for sender, data in sender_counts.items():
            if data['count'] >= min_emails:
                # Check for mailing list indicators
                is_likely_mailing_list = any([
                    'newsletter' in sender.lower(),
                    'noreply' in sender.lower(),
                    'marketing' in sender.lower(),
                    'updates' in sender.lower(),
                    'notifications' in sender.lower(),
                    data['count'] >= 5  # High volume sender
                ])
                
                mailing_lists.append({
                    'sender': sender,
                    'email_count': data['count'],
                    'likely_mailing_list': is_likely_mailing_list,
                    'latest_date': data['latest_date'],
                    'sample_subjects': data['subjects'][:3]  # First 3 subjects as sample
                })
        
        # Sort by email count (descending)
        mailing_lists.sort(key=lambda x: x['email_count'], reverse=True)
        
        return mailing_lists
    except Exception as e:
        return [{"error": f"Failed to analyze mailing list senders: {str(e)}"}]

# MCP Resources
@mcp.resource("proton://inbox/summary")
def inbox_summary() -> Resource:
    """Get a summary of your inbox"""
    try:
        recent_emails = email_client.search_emails("ALL", "INBOX", 5)
        summary = f"Recent emails in your Proton inbox:\n\n"
        for email_item in recent_emails:
            summary += f"{email_item['subject']} - From: {email_item['from']} ({email_item['date']})\n"
        
        return Resource(
            uri="proton://inbox/summary",
            name="Inbox Summary",
            description="Summary of recent emails in your Proton inbox",
            mimeType="text/plain",
            text=summary
        )
    except Exception as e:
        return Resource(
            uri="proton://inbox/summary",
            name="Inbox Summary",
            description="Error retrieving inbox summary",
            mimeType="text/plain",
            text=f"Error: {str(e)}"
        )

# Run the server
if __name__ == "__main__":
    mcp.run()