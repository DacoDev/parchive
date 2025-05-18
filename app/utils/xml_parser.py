import xml.etree.ElementTree as ET
import urllib.request
import urllib.error
from typing import Dict, Optional, List, Any
import re
from datetime import datetime
import html

# Define XML namespaces used in podcast feeds
NAMESPACES = {
    'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
    'atom': 'http://www.w3.org/2005/Atom',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'media': 'http://search.yahoo.com/mrss/'
}

def parse_rss_feed(input_data: str) -> Optional[Dict[str, Any]]:
    """
    Parse an RSS feed URL or XML string and extract channel information.
    
    Args:
        input_data: Either a URL to an RSS feed or raw XML data
        
    Returns:
        Dictionary with extracted information or None if parsing failed
    """
    try:
        # Determine if input is a URL or XML data
        is_url = input_data.startswith('http') and not input_data.strip().startswith('<')
        
        if is_url:
            # Fetch the RSS feed
            response = urllib.request.urlopen(input_data, timeout=10)
            xml_data = response.read()
        else:
            # Assume it's already XML data
            xml_data = input_data.encode('utf-8')
        
        # Parse XML
        root = ET.fromstring(xml_data)
        
        # Register namespaces for proper parsing
        for prefix, uri in NAMESPACES.items():
            ET.register_namespace(prefix, uri)
        
        # Find channel element
        channel = root.find('.//channel')
        if channel is None:
            return None
            
        # Extract show information
        result = extract_show_info(channel)
            
        # Extract episodes
        items = root.findall('.//item')
        episodes = []
        
        # Start indexing from 1 for user-facing numbers
        for i, item in enumerate(items):
            episode = extract_episode_info(item, i + 1)
            if episode and 'title' in episode and 'url' in episode:
                episodes.append(episode)
                
        if episodes:
            result['episodes'] = episodes
            result['episode_count'] = len(episodes)
            
        return result
    except (urllib.error.URLError, ET.ParseError, Exception) as e:
        print(f"Error parsing RSS feed: {e}")
        return None

def extract_show_info(channel: ET.Element) -> Dict[str, str]:
    """Extract show metadata from the channel element"""
    result = {}
    
    # Basic show info
    title_elem = channel.find('./title')
    if title_elem is not None and title_elem.text:
        result['title'] = title_elem.text.strip()
    
    description_elem = channel.find('./description')
    if description_elem is not None and description_elem.text:
        result['description'] = clean_html(description_elem.text.strip())
    
    # Author info (try different possible locations)
    author = None
    itunes_author = channel.find('./itunes:author', NAMESPACES)
    if itunes_author is not None and itunes_author.text:
        author = itunes_author.text.strip()
    elif channel.find('./managingEditor') is not None and channel.find('./managingEditor').text:
        author = channel.find('./managingEditor').text.strip()
        
    if author:
        result['author'] = author
        
    # Language
    language_elem = channel.find('./language')
    if language_elem is not None and language_elem.text:
        result['language'] = language_elem.text.strip()
        
    # Copyright
    copyright_elem = channel.find('./copyright')
    if copyright_elem is not None and copyright_elem.text:
        result['copyright'] = copyright_elem.text.strip()
        
    # Image URL (try both standard and iTunes locations)
    image_url = None
    image_elem = channel.find('./image/url')
    if image_elem is not None and image_elem.text:
        image_url = image_elem.text.strip()
    else:
        itunes_image = channel.find('./itunes:image', NAMESPACES)
        if itunes_image is not None and 'href' in itunes_image.attrib:
            image_url = itunes_image.attrib['href'].strip()
            
    if image_url:
        result['image_url'] = image_url
        
    # Category (combine iTunes categories for better context)
    categories = []
    for cat_elem in channel.findall('./itunes:category', NAMESPACES):
        if 'text' in cat_elem.attrib:
            category = cat_elem.attrib['text']
            subcategory = None
            
            # Check for subcategory
            sub_elem = cat_elem.find('./itunes:category', NAMESPACES)
            if sub_elem is not None and 'text' in sub_elem.attrib:
                subcategory = sub_elem.attrib['text']
                
            if subcategory:
                categories.append(f"{category} > {subcategory}")
            else:
                categories.append(category)
                
    if categories:
        result['category'] = '; '.join(categories)
        
    return result

def extract_episode_info(item: ET.Element, index: int) -> Dict[str, Any]:
    """Extract episode metadata from an item element"""
    episode = {}
    
    # Get title
    item_title = item.find('./title')
    if item_title is not None and item_title.text:
        episode['title'] = item_title.text.strip()
        
    # Get enclosure (download URL)
    enclosure = item.find('./enclosure')
    if enclosure is not None and 'url' in enclosure.attrib:
        episode['url'] = enclosure.attrib['url']
        
    # Get publication date
    pub_date = item.find('./pubDate')
    if pub_date is not None and pub_date.text:
        episode['pub_date'] = pub_date.text
        
        # Try to parse the date
        try:
            # Format example: "Wed, 15 Jun 2022 12:00:00 GMT"
            date_obj = datetime.strptime(pub_date.text.strip(), "%a, %d %b %Y %H:%M:%S %Z")
            episode['published_at'] = date_obj
        except (ValueError, TypeError):
            try:
                # Try alternative format: "Wed, 15 Jun 2022 12:00:00 +0000"
                date_obj = datetime.strptime(pub_date.text.strip()[:-6], "%a, %d %b %Y %H:%M:%S")
                episode['published_at'] = date_obj
            except (ValueError, TypeError):
                # Keep the original string if parsing fails
                pass
                
    # Get iTunes episode number
    itunes_episode = item.find('./itunes:episode', NAMESPACES)
    if itunes_episode is not None and itunes_episode.text:
        episode['itunes_episode'] = itunes_episode.text.strip()
        
    # Use iTunes episode number as episode_number if available
    if 'itunes_episode' in episode:
        episode['episode_number'] = episode['itunes_episode']
    else:
        # Default to the index
        episode['episode_number'] = str(index)
        
        # Try to extract from title
        if 'title' in episode:
            # Look for patterns like "123: Title" or "Episode 123 - Title"
            match = re.search(r'^(?:Episode\s*)?(\d+)(?:[\s:\-\.]+)', episode['title'])
            if match:
                episode['episode_number'] = match.group(1)
        
    # Get description (prefer content:encoded for full HTML if available)
    content_encoded = item.find('./content:encoded', NAMESPACES)
    description = item.find('./description')
    
    if content_encoded is not None and content_encoded.text:
        episode['description'] = clean_html(content_encoded.text.strip())
    elif description is not None and description.text:
        episode['description'] = clean_html(description.text.strip())
        
    # Get summary (prefer iTunes summary for a cleaner version)
    itunes_summary = item.find('./itunes:summary', NAMESPACES)
    
    if itunes_summary is not None and itunes_summary.text:
        episode['summary'] = clean_html(itunes_summary.text.strip())
    elif 'description' in episode:
        # Use the description but limit to first paragraph
        first_para = episode['description'].split('\n', 1)[0]
        episode['summary'] = first_para
        
    # Get author
    itunes_author = item.find('./itunes:author', NAMESPACES)
    author = item.find('./author')
    
    if itunes_author is not None and itunes_author.text:
        episode['author'] = itunes_author.text.strip()
    elif author is not None and author.text:
        episode['author'] = author.text.strip()
        
    # Get episode image
    itunes_image = item.find('./itunes:image', NAMESPACES)
    media_thumbnail = item.find('./media:thumbnail', NAMESPACES)
    
    if itunes_image is not None and 'href' in itunes_image.attrib:
        episode['image_url'] = itunes_image.attrib['href'].strip()
    elif media_thumbnail is not None and 'url' in media_thumbnail.attrib:
        episode['image_url'] = media_thumbnail.attrib['url'].strip()
        
    # Get duration
    itunes_duration = item.find('./itunes:duration', NAMESPACES)
    if itunes_duration is not None and itunes_duration.text:
        episode['duration'] = itunes_duration.text.strip()
        
    # Get keywords
    itunes_keywords = item.find('./itunes:keywords', NAMESPACES)
    if itunes_keywords is not None and itunes_keywords.text:
        episode['keywords'] = itunes_keywords.text.strip()
        
    return episode

def clean_html(text: str) -> str:
    """Clean HTML content by decoding entities and removing tags"""
    # Decode HTML entities
    text = html.unescape(text)
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip() 