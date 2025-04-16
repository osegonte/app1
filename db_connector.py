#!/usr/bin/env python3
"""
Database Connector Module for FilmFluent Project

This module handles the connection to PostgreSQL and provides functions
for storing subtitle analysis data in the database.
"""

import os
import sys
import json
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values


class FilmFluentDB:
    """Class for handling database operations for the FilmFluent project."""
    
    def __init__(self, db_config=None):
        """
        Initialize the database connection.
        
        Args:
            db_config (dict): Database configuration parameters.
                If None, environment variables will be used.
        """
        if db_config is None:
            # Use environment variables for configuration
            self.db_config = {
                'dbname': os.environ.get('FILMFLUENT_DB_NAME', 'filmfluent'),
                'user': os.environ.get('FILMFLUENT_DB_USER', 'postgres'),
                'password': os.environ.get('FILMFLUENT_DB_PASSWORD', ''),
                'host': os.environ.get('FILMFLUENT_DB_HOST', 'localhost'),
                'port': os.environ.get('FILMFLUENT_DB_PORT', '5432')
            }
        else:
            self.db_config = db_config
        
        self.conn = None
        self.cur = None
    
    def connect(self):
        """
        Establish connection to the PostgreSQL database.
        
        Returns:
            bool: True if connection successful, False otherwise.
        """
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
            return True
        except psycopg2.Error as e:
            print(f"Database connection error: {e}")
            return False
    
    def close(self):
        """Close the database connection."""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
    
    def create_tables(self):
        """
        Create all required tables if they don't exist.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Read SQL schema file
            schema_file = os.path.join(os.path.dirname(__file__), 'film_fluent_schema.sql')
            with open(schema_file, 'r') as f:
                schema_sql = f.read()
            
            # Execute the SQL
            self.cur.execute(schema_sql)
            self.conn.commit()
            print("Database tables created successfully.")
            return True
        except Exception as e:
            print(f"Error creating tables: {e}")
            self.conn.rollback()
            return False
    
    def get_file_hash(self, file_path):
        """
        Calculate a hash for a file to avoid duplicate processing.
        
        Args:
            file_path (str): Path to the file.
            
        Returns:
            str: SHA-256 hash of the file.
        """
        hash_sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            # Read and update hash in chunks for large files
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
                
        return hash_sha256.hexdigest()
    
    def file_exists(self, file_hash):
        """
        Check if a file has already been processed.
        
        Args:
            file_hash (str): The file's hash.
            
        Returns:
            bool: True if exists, False otherwise.
        """
        self.cur.execute("SELECT file_id FROM subtitle_files WHERE file_hash = %s", (file_hash,))
        return self.cur.rowcount > 0
    
    def store_movie(self, movie_data):
        """
        Store movie information in the database.
        
        Args:
            movie_data (dict): Movie metadata including title, year, etc.
            
        Returns:
            str: The UUID of the inserted/updated movie record.
        """
        sql = """
        INSERT INTO movies 
            (title, release_year, language, genre, runtime_minutes, subtitle_count, metadata)
        VALUES 
            (%s, %s, %s, %s, %s, %s, %s)
        RETURNING movie_id
        """
        
        values = (
            movie_data.get('title'),
            movie_data.get('release_year'),
            movie_data.get('language', 'English'),
            movie_data.get('genre'),
            movie_data.get('runtime_minutes'),
            movie_data.get('subtitle_count'),
            json.dumps(movie_data.get('metadata', {}))
        )
        
        self.cur.execute(sql, values)
        result = self.cur.fetchone()
        self.conn.commit()
        
        return result['movie_id']
    
    def store_subtitle_file(self, movie_id, file_data):
        """
        Store subtitle file information in the database.
        
        Args:
            movie_id (str): UUID of the associated movie.
            file_data (dict): File metadata.
            
        Returns:
            str: The UUID of the inserted file record.
        """
        # Check if file already exists by hash
        file_hash = self.get_file_hash(file_data['file_path'])
        if self.file_exists(file_hash):
            print(f"File already processed: {file_data['filename']}")
            self.cur.execute("SELECT file_id FROM subtitle_files WHERE file_hash = %s", (file_hash,))
            return self.cur.fetchone()['file_id']
        
        sql = """
        INSERT INTO subtitle_files 
            (movie_id, filename, file_path, encoding, subtitle_count, file_hash)
        VALUES 
            (%s, %s, %s, %s, %s, %s)
        RETURNING file_id
        """
        
        values = (
            movie_id,
            file_data.get('filename'),
            file_data.get('file_path'),
            file_data.get('encoding', 'UTF-8'),
            file_data.get('subtitle_count', 0),
            file_hash
        )
        
        self.cur.execute(sql, values)
        result = self.cur.fetchone()
        self.conn.commit()
        
        return result['file_id']
    
    def store_analysis_results(self, file_id, analysis):
        """
        Store analysis results in the database.
        
        Args:
            file_id (str): UUID of the associated subtitle file.
            analysis (dict): Analysis data.
            
        Returns:
            str: The UUID of the inserted analysis record.
        """
        avg_words_per_sent = analysis['total_words'] / analysis['total_sentences'] if analysis['total_sentences'] > 0 else 0
        
        # Calculate average word length
        total_chars = sum(len(word) * freq for word, freq in analysis['word_frequencies'].items())
        avg_word_length = total_chars / analysis['total_words'] if analysis['total_words'] > 0 else 0
        
        sql = """
        INSERT INTO analysis_results 
            (file_id, total_words, unique_words, total_sentences, 
             average_words_per_sentence, average_word_length)
        VALUES 
            (%s, %s, %s, %s, %s, %s)
        RETURNING analysis_id
        """
        
        values = (
            file_id,
            analysis['total_words'],
            analysis['unique_words'],
            analysis['total_sentences'],
            avg_words_per_sent,
            avg_word_length
        )
        
        self.cur.execute(sql, values)
        result = self.cur.fetchone()
        self.conn.commit()
        
        return result['analysis_id']
    
    def store_word_frequencies(self, file_id, word_frequencies, total_words):
        """
        Store word frequencies in the database.
        
        Args:
            file_id (str): UUID of the associated subtitle file.
            word_frequencies (dict): Word frequency dictionary.
            total_words (int): Total word count for relative frequency calculation.
            
        Returns:
            int: Number of word frequency records inserted.
        """
        # First, ensure all words are in the dictionary
        words_to_insert = []
        for word in word_frequencies.keys():
            words_to_insert.append((word, False, 'English'))
        
        if words_to_insert:
            # Use execute_values for efficient bulk insert
            insert_sql = """
            INSERT INTO words_dictionary (word, is_stopword, language)
            VALUES %s
            ON CONFLICT (word) DO NOTHING
            """
            execute_values(self.cur, insert_sql, words_to_insert)
            self.conn.commit()
        
        # Now get word_ids for all words
        word_ids = {}
        words_list = list(word_frequencies.keys())
        if words_list:
            placeholders = ','.join(['%s'] * len(words_list))
            self.cur.execute(
                f"SELECT word_id, word FROM words_dictionary WHERE word IN ({placeholders})",
                words_list
            )
            for row in self.cur.fetchall():
                word_ids[row['word']] = row['word_id']
        
        # Insert word frequencies
        freq_to_insert = []
        for word, count in word_frequencies.items():
            if word in word_ids:
                rel_freq = count / total_words if total_words > 0 else 0
                freq_to_insert.append((file_id, word_ids[word], count, rel_freq))
        
        if freq_to_insert:
            freq_sql = """
            INSERT INTO word_frequencies (file_id, word_id, frequency, relative_frequency)
            VALUES %s
            ON CONFLICT (file_id, word_id) DO UPDATE SET
              frequency = excluded.frequency,
              relative_frequency = excluded.relative_frequency
            """
            execute_values(self.cur, freq_sql, freq_to_insert)
            self.conn.commit()
        
        return len(freq_to_insert)
    
    def store_sentences(self, file_id, sentences):
        """
        Store extracted sentences in the database.
        
        Args:
            file_id (str): UUID of the associated subtitle file.
            sentences (list): List of sentence strings.
            
        Returns:
            int: Number of sentences inserted.
        """
        sentences_to_insert = []
        
        for sentence in sentences:
            # Count words in the sentence using a simple split (could use tokenizer for more accuracy)
            word_count = len(sentence.split())
            sentences_to_insert.append((file_id, sentence, word_count))
        
        if sentences_to_insert:
            sql = """
            INSERT INTO sentences (file_id, sentence, word_count)
            VALUES %s
            """
            execute_values(self.cur, sql, sentences_to_insert)
            self.conn.commit()
        
        return len(sentences_to_insert)
    
    def store_analysis(self, movie_data, file_data, analysis_results):
        """
        Store all analysis data in the database.
        
        Args:
            movie_data (dict): Movie metadata.
            file_data (dict): Subtitle file metadata.
            analysis_results (dict): Analysis results.
            
        Returns:
            dict: Dictionary with stored entity IDs.
        """
        try:
            # Store movie data
            movie_id = self.store_movie(movie_data)
            
            # Store subtitle file data
            file_id = self.store_subtitle_file(movie_id, file_data)
            
            # Store analysis results
            analysis_id = self.store_analysis_results(file_id, analysis_results)
            
            # Store word frequencies
            word_count = self.store_word_frequencies(
                file_id, 
                analysis_results['word_frequencies'], 
                analysis_results['total_words']
            )
            
            # Store sentences
            sentence_count = self.store_sentences(file_id, analysis_results['sentences'])
            
            print(f"Stored: {word_count} words and {sentence_count} sentences in database.")
            
            return {
                'movie_id': movie_id,
                'file_id': file_id,
                'analysis_id': analysis_id,
                'word_count': word_count,
                'sentence_count': sentence_count
            }
            
        except Exception as e:
            print(f"Error storing analysis data: {e}")
            self.conn.rollback()
            return None


def initialize_db(args=None):
    """
    Initialize database connection based on command line arguments.
    
    Args:
        args: Argument namespace with optional no_db attribute
        
    Returns:
        FilmFluentDB: Database connection object or None
    """
    db = None
    use_db = True
    
    if args is not None and hasattr(args, 'no_db'):
        use_db = not args.no_db
    
    if use_db:
        print("Connecting to database...")
        db = FilmFluentDB()
        if not db.connect():
            print("Failed to connect to database. Continuing without database storage.")
            db = None
        else:
            print("Database connected successfully.")
    
    return db


if __name__ == "__main__":
    # Example usage when run as a script
    db = FilmFluentDB()
    if not db.connect():
        sys.exit(1)
    
    # Create tables if needed
    db.create_tables()
    
    # Close connection
    db.close()
    
    print("Database setup complete.")