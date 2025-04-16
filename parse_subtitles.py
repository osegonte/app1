#!/usr/bin/env python3
"""
SRT Subtitle Parser for FilmFluent Project

This module handles the parsing of SRT subtitle files and provides
functions to extract text content with optional timing information.
"""

import re
import os
import codecs
import chardet


def detect_encoding(file_path):
    """
    Detects the encoding of a file using chardet.
    
    Args:
        file_path (str): Path to the file.
    
    Returns:
        str: Detected encoding.
    """
    with open(file_path, 'rb') as file:
        raw_data = file.read(10000)  # Read a chunk to detect encoding
        result = chardet.detect(raw_data)
        return result['encoding']


def parse_timestamp(timestamp_str):
    """
    Parses an SRT timestamp string into a more usable format.
    
    Args:
        timestamp_str (str): The timestamp string in the format "00:00:00,000"
    
    Returns:
        dict: Dictionary with 'hours', 'minutes', 'seconds', and 'milliseconds' keys.
    """
    pattern = r'(\d{2}):(\d{2}):(\d{2}),(\d{3})'
    match = re.match(pattern, timestamp_str)
    
    if not match:
        return None
    
    hours, minutes, seconds, milliseconds = map(int, match.groups())
    
    return {
        'hours': hours,
        'minutes': minutes,
        'seconds': seconds,
        'milliseconds': milliseconds,
        'total_seconds': hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
    }


def parse_time_range(time_line):
    """
    Parses a time range line from an SRT file.
    
    Args:
        time_line (str): The line containing the time range (e.g., "00:00:20,000 --> 00:00:24,400")
    
    Returns:
        tuple: (start_time, end_time) dictionaries.
    """
    pattern = r'([\d:,]+)\s*-->\s*([\d:,]+)'
    match = re.match(pattern, time_line)
    
    if not match:
        return None, None
    
    start_time_str, end_time_str = match.groups()
    start_time = parse_timestamp(start_time_str)
    end_time = parse_timestamp(end_time_str)
    
    return start_time, end_time


def clean_subtitle_text(text):
    """
    Cleans subtitle text by removing HTML-like tags and normalizing whitespace.
    
    Args:
        text (str): The subtitle text.
    
    Returns:
        str: Cleaned subtitle text.
    """
    # Remove HTML-like tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    # Normalize whitespace (replace multiple spaces with single space)
    text = re.sub(r'\s+', ' ', text)
    
    return text


def parse_srt(file_path):
    """
    Parses an SRT file and extracts subtitle entries.
    
    Args:
        file_path (str): Path to the SRT file.
    
    Returns:
        list: List of dictionaries containing subtitle entries with keys:
              'index', 'start_time', 'end_time', 'text', 'cleaned_text'
    """
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        return []
    
    try:
        # Detect encoding and open file
        encoding = detect_encoding(file_path)
        with codecs.open(file_path, 'r', encoding=encoding, errors='replace') as file:
            content = file.read()
    except Exception as e:
        print(f"Error reading the file: {e}")
        return []
    
    # Split file into subtitle blocks (separated by blank lines)
    subtitle_blocks = re.split(r'\n\s*\n', content.strip())
    
    subtitles = []
    
    for block in subtitle_blocks:
        lines = block.strip().split('\n')
        
        if len(lines) < 3:
            continue  # Skip incomplete blocks
        
        try:
            # Parse the subtitle number/index
            index = int(lines[0].strip())
            
            # Parse the timestamp line
            start_time, end_time = parse_time_range(lines[1])
            
            if not start_time or not end_time:
                continue
            
            # Get the subtitle text (could be multiple lines)
            text_lines = lines[2:]
            text = '\n'.join(text_lines)
            
            # Clean the text
            cleaned_text = clean_subtitle_text(text)
            
            # Add the subtitle entry to our list
            subtitles.append({
                'index': index,
                'start_time': start_time,
                'end_time': end_time,
                'text': text,
                'cleaned_text': cleaned_text
            })
            
        except Exception as e:
            print(f"Error parsing subtitle block: {e}")
            continue
    
    return subtitles


def get_subtitle_text_only(subtitles):
    """
    Extracts only the text content from parsed subtitles.
    
    Args:
        subtitles (list): List of subtitle dictionaries from parse_srt().
    
    Returns:
        list: List of cleaned subtitle text strings.
    """
    return [subtitle['cleaned_text'] for subtitle in subtitles]


def get_full_text(subtitles):
    """
    Combines all subtitle text into a single string.
    
    Args:
        subtitles (list): List of subtitle dictionaries from parse_srt().
    
    Returns:
        str: All subtitle text combined into one string.
    """
    text_list = get_subtitle_text_only(subtitles)
    return ' '.join(text_list)


if __name__ == "__main__":
    # Request file path from user when run as a script
    file_path = input("Please enter the path to the SRT subtitle file: ")
    
    # Parse the SRT file
    subtitles = parse_srt(file_path)
    
    # Display some information about the parsed subtitles
    if subtitles:
        print(f"\nSuccessfully parsed {len(subtitles)} subtitle entries.")
        print(f"First subtitle: \"{subtitles[0]['cleaned_text']}\"")
        print(f"Last subtitle: \"{subtitles[-1]['cleaned_text']}\"")
    else:
        print("No subtitles were parsed. Please check the file and try again.")