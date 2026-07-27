"""
Sentiment analysis processor.

This module computes the overall sentiment polarity of a news article.
The implementation currently uses TextBlob but can easily be replaced
by another NLP model (e.g. VADER, spaCy, Hugging Face, OpenAI).
"""

from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from scipy.special import softmax
from .base import BaseProcessor

class SentimentAnalyzer(BaseProcessor):
    def __init__(self, cfg):
        self.sentiment_model = AutoModelForSequenceClassification.from_pretrained(cfg.SENTIMENT_MODEL)
        self.tokenizer_sentiment = AutoTokenizer.from_pretrained(cfg.SENTIMENT_MODEL)

    def process(self, text):
        with torch.no_grad():
            text = self.analyze(text)
            encoded_input = self.tokenizer_sentiment(text, return_tensors='pt')
            output = self.sentiment_model(**encoded_input)
            scores = output[0][0].detach().numpy()
            scores = list(softmax(scores))
            print(f'The scores of the sentiment are: {scores}')
            return True if scores[2] > 0.2 else False
    
    def analyze(self, text):
        new_text = []
        for t in text.split(" "):
            t = '@user' if t.startswith('@') and len(t) > 1 else t
            t = 'http' if t.startswith('http') else t
            new_text.append(t)
        return " ".join(new_text)

