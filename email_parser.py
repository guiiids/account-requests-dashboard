"""
Email Parser for iLab Account Requests
Parses incoming iLab account request notification emails.

The standard iLab notification email from support@ilabsolutions.com contains:
    name: <requester name>
    email: <requester email>
    institution: <organization name>
    lab_name: <lab name>
    time: <timestamp>
    link: <ilab admin link>
"""
import re
from datetime import datetime


def parse_ilab_email(subject: str, body: str, sender: str = None) -> dict:
    """
    Parse an iLab account request notification email.
    
    Args:
        subject: Email subject line (e.g., "Manami Roychowdhury-Saha is requesting an account")
        body: Email body (plain text preferred, HTML will be stripped)
        sender: Email sender address
    
    Returns:
        dict with parsed fields:
        - requester_name: str
        - requester_email: str  
        - institution: str
        - lab_name: str
        - request_time: str
        - ilab_link: str
        - raw_body: str
        - is_valid: bool (True if critical fields were parsed)
    """
    result = {
        'requester_name': None,
        'requester_email': None,
        'institution': None,
        'lab_name': None,
        'request_time': None,
        'ilab_link': None,
        'raw_body': body,
        'is_valid': False
    }
    
    # Clean the body - strip HTML if present
    clean_body = strip_html(body)
    
    # Parse key-value pairs from the iLab format
    # Pattern: "key: value" at the start of a line or after whitespace
    patterns = {
        'name': r'(?:^|\n)\s*name:\s*(.+?)(?:\n|$)',
        'email': r'(?:^|\n)\s*email:\s*(\S+@\S+)',
        'institution': r'(?:^|\n)\s*institution:\s*(.+?)(?:\n|$)',
        'lab_name': r'(?:^|\n)\s*lab_name:\s*(.+?)(?:\n|$)',
        'time': r'(?:^|\n)\s*time:\s*(.+?)(?:\n|$)',
        'link': r'(?:^|\n)\s*link:\s*\n?\s*(https?://\S+)',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, clean_body, re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip()
            if key == 'name':
                result['requester_name'] = value
            elif key == 'email':
                result['requester_email'] = value.lower()
            elif key == 'institution':
                result['institution'] = value
            elif key == 'lab_name':
                result['lab_name'] = value
            elif key == 'time':
                result['request_time'] = value
            elif key == 'link':
                result['ilab_link'] = value
    
    # Fallback: Try to extract name from subject if not found in body
    # Subject format: "Firstname Lastname is requesting an account"
    if not result['requester_name'] and subject:
        subject_match = re.match(r'^(.+?)\s+is\s+requesting\s+an?\s+account', subject, re.IGNORECASE)
        if subject_match:
            result['requester_name'] = subject_match.group(1).strip()
    
    # Determine validity - must have at least email or name
    result['is_valid'] = bool(result['requester_email'] or result['requester_name'])
    
    return result


def strip_html(text: str) -> str:
    """
    Remove HTML tags and decode common entities for plain text extraction.
    """
    if not text:
        return ''
    
    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    
    # Remove style and script blocks
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Convert <br> and <p> to newlines
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '', text, flags=re.IGNORECASE)
    
    # Remove all other HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decode common HTML entities
    entities = {
        '&nbsp;': ' ',
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
        '&quot;': '"',
        '&#39;': "'",
        '&apos;': "'",
    }
    for entity, char in entities.items():
        text = text.replace(entity, char)
    
    # Collapse multiple blank lines
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    
    # Strip leading whitespace from each line and collapse inline spaces
    lines = text.split('\n')
    lines = [line.strip() for line in lines]
    text = '\n'.join(lines)
    
    return text.strip()


def is_original_request_email(sender: str, subject: str) -> bool:
    """
    Check if this is an original iLab request email (vs a reply/forward).
    Original emails come from support@ilabsolutions.com.
    """
    if not sender:
        return False
    
    sender_lower = sender.lower()
    # Original notifications come from iLab
    if 'ilabsolutions.com' in sender_lower or 'ilab' in sender_lower:
        return True
    
    return False


def extract_request_from_thread(body: str) -> dict:
    """
    For threaded emails, try to find and extract the original iLab request data
    which is typically quoted at the bottom of the thread.
    """
    # Look for the original iLab block - it contains the key-value format
    # Find the section that has name:/email:/institution:/lab_name: together
    
    # Use the same parsing logic
    return parse_ilab_email('', body)


# For testing
if __name__ == '__main__':
    # Test with sample email body
    sample = """
    name: Tim Takeuchi
    email: tim.takeuchi@thinkdeca.com
    institution: Deca Technologies
    lab_name: San Jose, Benedict (DT) Lab
    time: 2026-02-20 18:46:24 -0500

    link:
    https://my.ilabsolutions.com/administration/account_requests
    """
    
    result = parse_ilab_email("Manami Roychowdhury-Saha is requesting an account", sample)
    print("Parsed result:")
    for k, v in result.items():
        if k != 'raw_body':
            print(f"  {k}: {v}")
