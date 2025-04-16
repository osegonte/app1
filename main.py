#!/usr/bin/env python3
"""
FilmFluent Project - Main Script

This script orchestrates the subtitle parsing, word frequency analysis,
and database storage components of the FilmFluent project.
"""

import os
import sys
import argparse
import json
from datetime import datetime
from parse_subtitles import parse_srt, get_full_text
from word_frequency import WordFrequencyAnalyzer
from db_connector import FilmFluentDB


def extract_movie_info_from_filename(filename):
    """
    Attempt to extract movie title and year from filename.
    
    Args:
        filename (str): The filename of the subtitle file.
        
    Returns:
        dict: Dictionary with title and year if found.
    """
    movie_info = {
        'title': None,
        'release_year': None
    }
    
    # Try to extract movie info from filename patterns like "Movie.Title.2020.srt"
    # or "Movie Title (2020).srt"
    import re
    
    # Pattern for "Movie.Title.2020.srt" or "Movie_Title_2020.srt"
    pattern1 = r'(.+?)[\._](\d{4})[\._]'
    match1 = re.search(pattern1, filename)
    
    # Pattern for "Movie Title (2020).srt"
    pattern2 = r'(.+?)\s*\((\d{4})\)'
    match2 = re.search(pattern2, filename)
    
    if match1:
        title = match1.group(1).replace('.', ' ').replace('_', ' ').strip()
        year = int(match1.group(2))
        movie_info['title'] = title
        movie_info['release_year'] = year
    elif match2:
        title = match2.group(1).strip()
        year = int(match2.group(2))
        movie_info['title'] = title
        movie_info['release_year'] = year
    
    return movie_info


def process_subtitle_file(file_path, db=None, save_json=False):
    """
    Process a subtitle file: parse, analyze, and store in database.
    
    Args:
        file_path (str): Path to the subtitle file.
        db (FilmFluentDB): Database connection object.
        save_json (bool): Whether to save analysis to JSON file.
        
    Returns:
        dict: Analysis results.
    """
    print(f"\n{'='*50}")
    print(f"Processing: {os.path.basename(file_path)}")
    print(f"{'='*50}")
    
    # Parse SRT file
    print("Parsing subtitle file...")
    subtitles = parse_srt(file_path)
    
    if not subtitles:
        print("No subtitles were parsed. Skipping file.")
        return None
    
    print(f"Successfully parsed {len(subtitles)} subtitle entries.")
    
    # Get full text
    print("Extracting text from subtitles...")
    full_text = get_full_text(subtitles)
    
    # Create analyzer and analyze text
    print("Analyzing text...")
    analyzer = WordFrequencyAnalyzer()
    analysis_results = analyzer.analyze_text(full_text)
    
    # Extract movie information from filename
    filename = os.path.basename(file_path)
    movie_info = extract_movie_info_from_filename(filename)
    
    # Add file info
    file_info = {
        'filename': filename,
        'file_path': file_path,
        'subtitle_count': len(subtitles),
        'processed_at': datetime.now().isoformat()
    }
    
    # Update movie info
    if not movie_info['title']:
        movie_info['title'] = os.path.splitext(filename)[0]
        
    movie_info['subtitle_count'] = len(subtitles)
    movie_info['metadata'] = {
        'processed_date': datetime.now().isoformat(),
        'first_subtitle': subtitles[0]['cleaned_text'] if subtitles else None,
        'last_subtitle': subtitles[-1]['cleaned_text'] if subtitles else None
    }
    
    # Display analysis results
    print(f"\nAnalysis Results:")
    print(f"Title: {movie_info['title']}")
    print(f"Year: {movie_info['release_year']}")
    print(f"Total words: {analysis_results['total_words']}")
    print(f"Unique words: {analysis_results['unique_words']}")
    print(f"Total sentences: {analysis_results['total_sentences']}")
    print("\nTop 10 words:")
    for word, count in list(analysis_results['top_words'].items())[:10]:
        print(f"  {word}: {count}")
    
    # Save to JSON if requested
    if save_json:
        json_path = file_path + '.analysis.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(analysis_results, f, ensure_ascii=False, indent=2)
        print(f"Analysis saved to {json_path}")
    
    # Store in database if db connection provided
    file_id = None
    if db:
        print("\nStoring analysis in database...")
        result = db.store_analysis(movie_info, file_info, analysis_results)
        if result:
            print("Successfully stored in database.")
            file_id = result.get('file_id')
        else:
            print("Failed to store in database.")
    
    return {
        'analysis_results': analysis_results,
        'file_id': file_id
    }


def main():
    """Main function to orchestrate the FilmFluent workflow."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='FilmFluent - Subtitle Analysis Tool')
    parser.add_argument('file_path', nargs='?', help='Path to the subtitle file or directory')
    parser.add_argument('--batch', action='store_true', help='Process all SRT files in directory')
    parser.add_argument('--db', action='store_true', default=True, help='Store results in PostgreSQL database')
    parser.add_argument('--json', action='store_true', help='Save analysis to JSON file')
    
    args = parser.parse_args()
    
    # Get file path from args or prompt
    if not args.file_path:
        args.file_path = input("Please enter the path to the SRT subtitle file or directory: ")
    
    # Initialize database connection if requested
    db = None
    if args.db:
        print("Connecting to database...")
        db = FilmFluentDB()
        if not db.connect():
            print("Failed to connect to database. Continuing without database storage.")
            db = None
        else:
            print("Database connected successfully.")
    
    # Process files
    if args.batch and os.path.isdir(args.file_path):
        # Process all SRT files in directory
        print(f"Batch processing all SRT files in: {args.file_path}")
        files_processed = 0
        
        for filename in os.listdir(args.file_path):
            if filename.lower().endswith('.srt'):
                file_path = os.path.join(args.file_path, filename)
                result = process_subtitle_file(
                    file_path, 
                    db, 
                    args.json
                )
                if result:
                    files_processed += 1
        
        print(f"\nBatch processing complete. Processed {files_processed} files.")
    else:
        # Process single file
        if not os.path.isfile(args.file_path):
            print(f"Error: File not found - {args.file_path}")
            return 1
        
        if not args.file_path.lower().endswith('.srt'):
            print(f"Warning: File does not have .srt extension - {args.file_path}")
        
        process_subtitle_file(
            args.file_path, 
            db, 
            args.json
        )
    
    # Close database connection
    if db:
        db.close()
        print("Database connection closed.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())