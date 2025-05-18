from openai import OpenAI
from typing import Optional, List, Dict, Any
import os
from ..utils.config import config

class AIService:
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ):
        """
        Initialize the AI service with Docker Model Runner.
        
        Args:
            base_url: The URL of the Model Runner API (overrides config)
            model: The model to use (overrides config)
            temperature: Controls randomness (0.0 to 1.0) (overrides config)
            max_tokens: Maximum number of tokens to generate (overrides config)
        """
        # Set defaults from config
        self.base_url = base_url or config.ai_url
        self.model = model or config.get("ai", "show_analysis_model", "llama3-70b")
        self.temperature = temperature or config.get("ai", "temperature", 0.7)
        self.max_tokens = max_tokens or config.get("ai", "max_tokens", 500)
        
        # Initialize OpenAI client
        self.client = OpenAI(
            base_url=self.base_url,
            api_key="not-needed"  # API key not required for local Model Runner
        )
        
        # Check if AI is enabled and model is available
        self.is_enabled = config.ai_enabled
        self.is_model_available = self.is_enabled and self.check_connection()

    def check_connection(self) -> bool:
        """
        Check if the model server is available.
        
        Returns:
            bool: True if the server is available, False otherwise
        """
        if not self.is_enabled:
            return False
            
        try:
            # Send a minimal request to check if the server is responsive
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            return True
        except Exception:
            return False

    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None
    ) -> str:
        """
        Generate a response from the AI model.
        
        Args:
            prompt: The user's input prompt
            system_prompt: Optional system prompt to set context
            temperature: Optional override for temperature
            max_tokens: Optional override for max tokens
            model: Optional override for model
            
        Returns:
            The generated response as a string
        """
        # If AI is disabled or model is not available, return a placeholder message
        if not self.is_enabled:
            return "[Analysis unavailable - AI is disabled in configuration]"
            
        if not self.is_model_available:
            return "[Analysis unavailable - Local AI model not running]"
            
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
            
        messages.append({"role": "user", "content": prompt})
        
        # Determine if streaming is enabled from config
        stream = config.get("ai", "stream_responses", False)
        
        try:
            response = self.client.chat.completions.create(
                model=model or self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                stream=stream
            )
            
            # Handle streaming responses if enabled
            if stream:
                chunks = []
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        chunks.append(chunk.choices[0].delta.content)
                return "".join(chunks)
            else:
                return response.choices[0].message.content
        except Exception as e:
            return f"Error generating response: {str(e)}"

    def analyze_url(self, url_data: Dict[str, Any]) -> str:
        """
        Analyze a URL entry and provide insights.
        
        Args:
            url_data: Dictionary containing URL information (name, episode, url)
            
        Returns:
            Analysis of the URL entry
        """
        prompt = f"""
        Analyze this URL entry:
        Name: {url_data.get('name', 'N/A')}
        Episode: {url_data.get('episode', 'N/A')}
        URL: {url_data.get('url', 'N/A')}
        
        Provide a brief analysis of this entry.
        """
        
        system_prompt = "You are a helpful assistant that analyzes URL entries and provides insights."
        
        return self.generate_response(prompt, system_prompt)
        
    def analyze_show(self, show: Any) -> str:
        """
        Analyze a show and provide insights.
        
        Args:
            show: Show object containing show information
            
        Returns:
            Analysis of the show
        """
        # Use show-specific model and settings from config
        model = config.get("ai", "show_analysis_model", self.model)
        
        system_prompt = "You are a helpful podcast analyst who provides concise, informative insights about podcast shows."
        
        # Build rich context from all available metadata
        metadata_context = []
        
        if hasattr(show, 'name') and show.name:
            metadata_context.append(f"- Name: {show.name}")
            
        if hasattr(show, 'description') and show.description:
            metadata_context.append(f"- Description: {show.description}")
            
        if hasattr(show, 'author') and show.author:
            metadata_context.append(f"- Author/Host: {show.author}")
            
        if hasattr(show, 'category') and show.category:
            metadata_context.append(f"- Category: {show.category}")
            
        if hasattr(show, 'language') and show.language:
            metadata_context.append(f"- Language: {show.language}")
            
        if hasattr(show, 'copyright') and show.copyright:
            metadata_context.append(f"- Copyright: {show.copyright}")
        
        # Format the metadata section, or use a placeholder if no metadata is available
        metadata_section = "\n".join(metadata_context) if metadata_context else "Limited metadata available"
        
        prompt = f"""
Task: Analyze the following podcast show and provide a brief informative summary.

Podcast Information:
{metadata_section}

Your analysis should cover:
1. What the podcast appears to be about based on its metadata
2. Any notable information that can be inferred from the metadata
3. A concise summary (2-3 sentences)
"""
        
        return self.generate_response(prompt, system_prompt, model=model)
        
    def analyze_episode(self, episode: Any, show_name: str = "Unknown Show") -> str:
        """
        Analyze an episode and provide insights.
        
        Args:
            episode: Episode object containing episode information
            show_name: Name of the show this episode belongs to
            
        Returns:
            Analysis of the episode
        """
        # Use episode-specific model and settings from config
        model = config.get("ai", "episode_analysis_model", self.model)
        
        system_prompt = "You are a helpful podcast analyst who provides concise, informative insights about podcast episodes."
        
        # Build rich context from all available metadata
        metadata_context = []
        
        metadata_context.append(f"- Show: {show_name}")
        
        if hasattr(episode, 'title') and episode.title:
            metadata_context.append(f"- Title: {episode.title}")
            
        if hasattr(episode, 'episode_number') and episode.episode_number:
            metadata_context.append(f"- Episode Number: {episode.episode_number}")
            
        if hasattr(episode, 'published_at') and episode.published_at:
            metadata_context.append(f"- Published: {episode.published_at.isoformat() if episode.published_at else 'Unknown'}")
            
        if hasattr(episode, 'description') and episode.description:
            metadata_context.append(f"- Description: {episode.description}")
            
        if hasattr(episode, 'summary') and episode.summary:
            metadata_context.append(f"- Summary: {episode.summary}")
            
        if hasattr(episode, 'author') and episode.author:
            metadata_context.append(f"- Author/Host: {episode.author}")
            
        if hasattr(episode, 'duration') and episode.duration:
            metadata_context.append(f"- Duration: {episode.duration}")
            
        if hasattr(episode, 'keywords') and episode.keywords:
            metadata_context.append(f"- Keywords: {episode.keywords}")
        
        # Format the metadata section, or use a placeholder if no metadata is available
        metadata_section = "\n".join(metadata_context) if metadata_context else "Limited metadata available"
        
        prompt = f"""
Task: Analyze the following podcast episode and provide a brief informative summary.

Episode Information:
{metadata_section}

Your analysis should cover:
1. What the episode appears to be about based on its metadata
2. Any notable information that can be inferred from the metadata
3. A concise summary (2-3 sentences)
"""
        
        return self.generate_response(prompt, system_prompt, model=model) 