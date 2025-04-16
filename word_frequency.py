#!/usr/bin/env python3
"""
Word Frequency Analysis Module for FilmFluent Project

This module processes subtitle text to extract words and sentences,
analyze word frequencies, and prepare data for PostgreSQL storage.
"""

import re
import string
import json
from collections import Counter
import os
import sys
import argparse
import json
from datetime import datetime

# Remove the circular import
# from word_frequency import WordFrequencyAnalyzer

# Use simple regex-based tokenizers instead of NLTK to avoid dependency issues
def simple_word_tokenize(text):
    """Simple word tokenizer using regex"""
    # Remove punctuation and split by whitespace
    return re.findall(r'\b\w+\b', text.lower())

def simple_sent_tokenize(text):
    """Simple sentence tokenizer using regex"""
    # Split on common sentence endings
    return re.split(r'[.!?]+\s+', text.strip())


class WordFrequencyAnalyzer:
    """Class for analyzing word frequency in subtitle text."""
    
    def __init__(self):
        """Initialize the analyzer with basic English stopwords."""
        # Common English stopwords - can be expanded
        self.stopwords = {
            'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'what',
            'which', 'this', 'that', 'these', 'those', 'then', 'just', 'so', 'than',
            'such', 'both', 'through', 'about', 'for', 'is', 'of', 'while', 'during',
            'to', 'from', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 'once',
            'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any', 'both',
            'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
            'not', 'only', 'own', 'same', 'too', 'very', 's', 't', 'can', 'will',
            'don', 'should', 'now', 'i', 'me', 'my', 'myself', 'we', 'our', 'ours',
            'ourselves', 'you', 'your', 'yours', 'yourself', 'yourselves', 'he', 'him',
            'his', 'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself',
            'they', 'them', 'their', 'theirs', 'themselves', 'am', 'are', 'was', 'were',
            'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did',
            'doing', 'would', 'could', 'should', 'ought', 'im', 'youre', 'hes', 'shes',
            'its', 'were', 'theyre', 'ive', 'youve', 'weve', 'theyve', 'id', 'youd',
            'hed', 'shed', 'wed', 'theyd', 'isnt', 'arent', 'wasnt', 'werent', 'hasnt',
            'havent', 'hadnt', 'doesnt', 'dont', 'didnt'
        }
    
    def tokenize_words(self, text):
        """
        Tokenize text into words, removing punctuation and converting to lowercase.
        
        Args:
            text (str): Text to tokenize
            
        Returns:
            list: List of word tokens
        """
        # Convert to lowercase and use regex to extract words
        words = simple_word_tokenize(text)
        
        # Filter out digits and empty strings
        words = [word for word in words 
                if not word.isdigit()
                and word.strip()]
        
        return words
    
    def tokenize_sentences(self, text):
        """
        Tokenize text into sentences.
        
        Args:
            text (str): Text to tokenize
            
        Returns:
            list: List of sentences
        """
        sentences = simple_sent_tokenize(text)
        # Filter out empty sentences
        return [s for s in sentences if s.strip()]
    
    def remove_stopwords(self, words):
        """
        Remove common stopwords if available.
        
        Args:
            words (list): List of words
            
        Returns:
            list: List of words with stopwords removed
        """
        if not self.stopwords:
            return words
            
        return [word for word in words if word not in self.stopwords]
    
    def count_word_frequency(self, words, remove_stopwords=True):
        """
        Count frequency of each word.
        
        Args:
            words (list): List of words
            remove_stopwords (bool): Whether to remove stopwords
            
        Returns:
            Counter: Counter object with word frequencies
        """
        if remove_stopwords and self.stopwords:
            words = self.remove_stopwords(words)
            
        return Counter(words)
    
    def get_top_words(self, word_counts, limit=100):
        """
        Get the most common words.
        
        Args:
            word_counts (Counter): Counter object with word frequencies
            limit (int): Maximum number of words to return
            
        Returns:
            list: List of (word, count) tuples
        """
        return word_counts.most_common(limit)
    
    def analyze_text(self, text, include_stopwords=False):
        """
        Perform complete analysis on text.
        
        Args:
            text (str): Text to analyze
            include_stopwords (bool): Whether to include stopwords in frequency count
            
        Returns:
            dict: Dictionary with analysis results
        """
        # Extract words and sentences
        words = self.tokenize_words(text)
        sentences = self.tokenize_sentences(text)
        
        # Count word frequencies
        word_counts = self.count_word_frequency(words, not include_stopwords)
        
        # Prepare results
        results = {
            'total_words': len(words),
            'unique_words': len(word_counts),
            'total_sentences': len(sentences),
            'word_frequencies': dict(word_counts),
            'top_words': dict(self.get_top_words(word_counts, 50)),
            'sentences': sentences
        }
        
        return results
    
    def prepare_for_postgres(self, analysis_results, subtitle_info=None):
        """
        Prepare analysis results for PostgreSQL storage.
        
        Args:
            analysis_results (dict): Results from analyze_text()
            subtitle_info (dict): Additional subtitle metadata
            
        Returns:
            dict: Dictionary with formatted data for PostgreSQL insertion
        """
        # Main analysis record
        analysis_record = {
            'total_words': analysis_results['total_words'],
            'unique_words': analysis_results['unique_words'],
            'total_sentences': analysis_results['total_sentences'],
            'metadata': json.dumps(subtitle_info) if subtitle_info else None
        }
        
        # Word frequency records (for a separate table)
        word_records = [
            {'word': word, 'frequency': count} 
            for word, count in analysis_results['word_frequencies'].items()
        ]
        
        # Sentence records (for a separate table)
        sentence_records = [
            {'sentence': sentence, 'word_count': len(self.tokenize_words(sentence))}
            for sentence in analysis_results['sentences']
        ]
        
        return {
            'analysis': analysis_record,
            'word_frequencies': word_records,
            'sentences': sentence_records
        }


def json_export(data, file_path):
    """
    Export analysis data to JSON file.
    
    Args:
        data (dict): Data to export
        file_path (str): Path to save JSON file
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # Example usage when run as a script
    import sys
    from parse_subtitles import parse_srt, get_full_text
    
    if len(sys.argv) < 2:
        file_path = input("Please enter the path to the SRT subtitle file: ")
    else:
        file_path = sys.argv[1]
    
    # Parse subtitles
    print(f"Parsing subtitle file: {file_path}")
    subtitles = parse_srt(file_path)
    
    if not subtitles:
        print("No subtitles were parsed. Please check the file and try again.")
        sys.exit(1)
    
    print(f"Successfully parsed {len(subtitles)} subtitle entries.")
    
    # Get full text
    print("Extracting and analyzing text...")
    full_text = get_full_text(subtitles)
    
    # Create analyzer and analyze text
    analyzer = WordFrequencyAnalyzer()
    analysis_results = analyzer.analyze_text(full_text)
    
    # Prepare data for PostgreSQL (demonstration)
    subtitle_info = {
        'filename': file_path,
        'subtitle_count': len(subtitles),
        'language': 'en'  # In a real app, you might detect this
    }
    
    pg_data = analyzer.prepare_for_postgres(analysis_results, subtitle_info)
    
    # Display some results
    print(f"\nAnalysis Results:")
    print(f"Total words: {analysis_results['total_words']}")
    print(f"Unique words: {analysis_results['unique_words']}")
    print(f"Total sentences: {analysis_results['total_sentences']}")
    print("\nTop 10 words:")
    for word, count in list(analysis_results['top_words'].items())[:10]:
        print(f"  {word}: {count}")
    
    # Option to save to JSON
    save_option = input("\nSave analysis to JSON file? (y/n): ")
    if save_option.lower() == 'y':
        json_path = file_path + '.analysis.json'
        json_export(analysis_results, json_path)
        print(f"Analysis saved to {json_path}")