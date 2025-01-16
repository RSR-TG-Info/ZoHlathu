__version__ = "0.1.0"
__all__ = ["ZohlathuClient", "ZohlathuError"]

# zohlathu/exceptions.py
class ZohlathuError(Exception):
    """Base exception class for Zohlathu package"""
    pass

class LyricsNotFoundError(ZohlathuError):
    """Raised when lyrics are not found"""
    pass

import feedparser
import html2text
import re
from typing import Dict, Optional
from .exceptions import LyricsNotFoundError

class RSR:
    """Client for fetching lyrics from Zohlathu.in"""
    
    def __init__(self):
        self.base_url = "https://www.blogger.com/feeds/690973182178026088/posts/default"
    
    async def get_lyrics(self, query: str) -> Dict[str, str]:
        """
        Fetch lyrics for the given song query
        
        Args:
            query (str): Song name or artist to search for
            
        Returns:
            dict: Dictionary containing title and lyrics
            
        Raises:
            LyricsNotFoundError: If lyrics are not found
        """
        search_query = query.replace(' ', '+')
        feed_url = f'{self.base_url}?q={search_query}'
        
        feed = feedparser.parse(feed_url)
        
        if feed.bozo or feed.status == 404 or not feed.entries:
            raise LyricsNotFoundError(f"No lyrics found for: {query}")
            
        for entry in feed.entries:
            content = html2text(entry.content[0]['value'])
            pattern = r'\* \* \*(.*?)\* \* \*'
            cleaned_content = re.sub(pattern, '', content, flags=re.DOTALL)
            
            if len(cleaned_content) == 0:
                raise LyricsNotFoundError(f"No lyrics content found for: {query}")
                
            return {
                "title": entry.title,
                "lyrics": cleaned_content.strip(),
                "source_url": entry.link
            }
        
        raise LyricsNotFoundError(f"No lyrics found for: {query}")
