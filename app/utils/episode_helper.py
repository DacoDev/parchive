"""
Utility functions for handling episode numbers and ranges.
"""
from typing import List, Optional

def parse_episode_range(episode_input: str) -> List[int]:
    """
    Parse an episode input string to a list of episode indices.
    
    Args:
        episode_input: String representing episodes to download.
                      "all" or empty = all episodes
                      "5" = single episode
                      "1-5" = range of episodes
                      "1-5,10-15,20" = multiple ranges and individual episodes
                      
    Returns:
        List of episode indices to download
    """
    if not episode_input or episode_input.lower() == "all":
        return []  # Empty list means all episodes
    
    # Handle comma-separated ranges
    if "," in episode_input:
        result = []
        for part in episode_input.split(","):
            # Recursively parse each part and combine
            result.extend(parse_episode_range(part.strip()))
        return sorted(list(set(result)))  # Sort and deduplicate
    
    # Single episode
    if episode_input.isdigit():
        return [int(episode_input)]
    
    # Range of episodes
    if "-" in episode_input:
        try:
            start, end = episode_input.split("-", 1)
            start = int(start.strip())
            end = int(end.strip())
            
            if start > end:
                start, end = end, start  # Swap if start > end
                
            return list(range(start, end + 1))
        except (ValueError, TypeError):
            # If parsing fails, return empty list (all episodes)
            return []
    
    # Default to all episodes if format not recognized
    return []

def get_episode_description(episode_range: List[int]) -> str:
    """
    Convert an episode range list to a human-readable description.
    
    Args:
        episode_range: List of episode indices
        
    Returns:
        Human-readable description of the episodes
    """
    if not episode_range:
        return "all episodes"
    
    if len(episode_range) == 1:
        return f"episode {episode_range[0]}"
    
    # Check if it's a continuous range
    if episode_range == list(range(min(episode_range), max(episode_range) + 1)):
        return f"episodes {min(episode_range)}-{max(episode_range)}"
    
    # If it's a discontinuous list
    return f"episodes {', '.join(str(ep) for ep in episode_range)}" 