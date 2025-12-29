"""
Sentiment analysis utility for voice agent calls.
Analyzes user utterances to determine overall call sentiment.
"""
import logging
from typing import Dict

logger = logging.getLogger("smiledesk-agent")

# Lazy load the pipeline to avoid slowing down startup
_sentiment_pipeline = None

def _get_pipeline():
    """Lazy load the sentiment analysis pipeline."""
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        try:
            from transformers import pipeline
            _sentiment_pipeline = pipeline("sentiment-analysis")
            logger.info("Sentiment analysis pipeline loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load sentiment pipeline: {e}")
            _sentiment_pipeline = False  # Mark as failed
    return _sentiment_pipeline


def analyze_sentiment(text: str) -> Dict[str, any]:
    """
    Analyze sentiment of the given text.
    
    Args:
        text: The text to analyze (typically concatenated user utterances)
    
    Returns:
        dict with keys:
        - label: "POSITIVE", "NEGATIVE", or error states
        - score: confidence score (0-1)
        - error: error message if applicable
    """
    pipeline = _get_pipeline()
    
    # Handle pipeline loading failure
    if pipeline is False:
        return {"label": "UNAVAILABLE", "score": 0.0, "error": "Pipeline failed to load"}
    
    # Validate input
    if not text or not text.strip():
        return {"label": "NO_TEXT", "score": 0.0}
    
    try:
        # Truncate text if too long (BERT models typically max at 512 tokens)
        max_chars = 2000
        if len(text) > max_chars:
            logger.info(f"Truncating text from {len(text)} to {max_chars} chars for sentiment")
            text = text[:max_chars]
        
        # Run sentiment analysis
        result = pipeline(text)
        
        # Extract result (pipeline returns a list)
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return result
        
    except Exception as e:
        logger.error(f"Error during sentiment analysis: {e}")
        return {"label": "ERROR", "score": 0.0, "error": str(e)}




