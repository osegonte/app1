-- FilmFluent PostgreSQL Database Schema (Unified Version)
-- This schema defines tables for storing subtitle analysis data and translations

-- Enable UUID extension for generating unique IDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Movies table - stores information about analyzed movies
CREATE TABLE movies (
    movie_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    release_year INTEGER,
    language VARCHAR(50) DEFAULT 'English',
    genre VARCHAR(100),
    runtime_minutes INTEGER,
    subtitle_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB -- For additional flexible data storage
);

-- Subtitle files table - stores information about processed subtitle files
CREATE TABLE subtitle_files (
    file_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    movie_id UUID REFERENCES movies(movie_id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_path TEXT,
    encoding VARCHAR(50),
    subtitle_count INTEGER,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    file_hash VARCHAR(64) UNIQUE -- To avoid duplicate processing
);

-- Analysis results table - stores aggregated analysis data
CREATE TABLE analysis_results (
    analysis_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID REFERENCES subtitle_files(file_id) ON DELETE CASCADE,
    total_words INTEGER NOT NULL,
    unique_words INTEGER NOT NULL,
    total_sentences INTEGER NOT NULL,
    average_words_per_sentence REAL,
    average_word_length REAL,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Words dictionary - master table of all unique words across all movies
CREATE TABLE words_dictionary (
    word_id SERIAL PRIMARY KEY,
    word VARCHAR(100) UNIQUE NOT NULL,
    is_stopword BOOLEAN DEFAULT FALSE,
    language VARCHAR(50) DEFAULT 'English'
);

-- Word frequencies - tracks word occurrences across files
-- Note: Added view_word_text as a JOIN view to easily access word text
CREATE TABLE word_frequencies (
    frequency_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID REFERENCES subtitle_files(file_id) ON DELETE CASCADE,
    word_id INTEGER REFERENCES words_dictionary(word_id) ON DELETE CASCADE,
    frequency INTEGER NOT NULL DEFAULT 1,
    relative_frequency REAL, -- Frequency relative to total words in file
    UNIQUE(file_id, word_id)
);

-- Sentences table - stores extracted sentences
CREATE TABLE sentences (
    sentence_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID REFERENCES subtitle_files(file_id) ON DELETE CASCADE,
    sentence_text TEXT NOT NULL, -- Renamed from 'sentence' to 'sentence_text' for clarity
    word_count INTEGER NOT NULL,
    start_time INTERVAL, -- Optional: if timestamp data is preserved from SRT
    end_time INTERVAL    -- Optional: if timestamp data is preserved from SRT
);

-- Global word stats - aggregated word statistics across all movies
CREATE TABLE global_word_stats (
    word_id INTEGER REFERENCES words_dictionary(word_id) ON DELETE CASCADE PRIMARY KEY,
    total_occurrences BIGINT NOT NULL DEFAULT 0,
    document_frequency INTEGER NOT NULL DEFAULT 0, -- Number of files containing this word
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
-- Target languages table - stores information about languages for translation
CREATE TABLE target_languages (
    language_id SERIAL PRIMARY KEY,
    language_code VARCHAR(10) NOT NULL UNIQUE,  -- ISO language code (e.g., 'es', 'fr', 'de')
    language_name VARCHAR(50) NOT NULL,         -- Full language name (e.g., 'Spanish', 'French')
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert common target languages
INSERT INTO target_languages (language_code, language_name) VALUES
('es', 'Spanish'),
('fr', 'French'),
('de', 'German'),
('it', 'Italian'),
('pt', 'Portuguese'),
('zh', 'Chinese'),
('ja', 'Japanese'),
('ru', 'Russian');

-- Word translations table - stores translations of individual words
CREATE TABLE word_translations (
    translation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    word_id INTEGER REFERENCES words_dictionary(word_id) ON DELETE CASCADE,
    language_id INTEGER REFERENCES target_languages(language_id) ON DELETE CASCADE,
    translation VARCHAR(100) NOT NULL,
    confidence_score REAL,  -- Optional score from translation API
    context_examples JSONB,  -- Optional examples of usage
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(word_id, language_id, translation)
);

-- Sentence translations table - stores translations of sentences
CREATE TABLE sentence_translations (
    translation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sentence_id UUID REFERENCES sentences(sentence_id) ON DELETE CASCADE,
    language_id INTEGER REFERENCES target_languages(language_id) ON DELETE CASCADE,
    translation TEXT NOT NULL,
    confidence_score REAL,  -- Optional score from translation API
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sentence_id, language_id)
);

-- Translation jobs table - tracks translation batch jobs
CREATE TABLE translation_jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID REFERENCES subtitle_files(file_id) ON DELETE CASCADE,
    language_id INTEGER REFERENCES target_languages(language_id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending', 'in_progress', 'completed', 'failed'
    words_translated INTEGER DEFAULT 0,
    sentences_translated INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    UNIQUE(file_id, language_id)
);

-- Create indexes for performance
CREATE INDEX idx_word_frequencies_file_id ON word_frequencies(file_id);
CREATE INDEX idx_word_frequencies_word_id ON word_frequencies(word_id);
CREATE INDEX idx_sentences_file_id ON sentences(file_id);
CREATE INDEX idx_subtitle_files_movie_id ON subtitle_files(movie_id);
CREATE INDEX idx_words_dictionary_word ON words_dictionary(word);
CREATE INDEX idx_word_translations_word_id ON word_translations(word_id);
CREATE INDEX idx_word_translations_language_id ON word_translations(language_id);
CREATE INDEX idx_sentence_translations_sentence_id ON sentence_translations(sentence_id);
CREATE INDEX idx_sentence_translations_language_id ON sentence_translations(language_id);
CREATE INDEX idx_translation_jobs_file_id ON translation_jobs(file_id);
CREATE INDEX idx_translation_jobs_status ON translation_jobs(status);

-- Create a function to update global word stats when word frequencies are added
CREATE OR REPLACE FUNCTION update_global_word_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- Update or insert into global_word_stats
    INSERT INTO global_word_stats (word_id, total_occurrences, document_frequency)
    VALUES (NEW.word_id, NEW.frequency, 1)
    ON CONFLICT (word_id) DO UPDATE SET
        total_occurrences = global_word_stats.total_occurrences + NEW.frequency,
        document_frequency = global_word_stats.document_frequency + 1,
        last_updated = CURRENT_TIMESTAMP;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create a trigger to update global stats when new word frequencies are added
CREATE TRIGGER trigger_update_global_word_stats
AFTER INSERT ON word_frequencies
FOR EACH ROW EXECUTE FUNCTION update_global_word_stats();

-- Create a view to easily access word text with frequencies
-- This solves the issue with accessing word_text in word_frequencies table
CREATE VIEW word_frequencies_view AS
SELECT 
    wf.frequency_id,
    wf.file_id,
    wf.word_id,
    wd.word AS word_text,
    wf.frequency,
    wf.relative_frequency
FROM 
    word_frequencies wf
JOIN 
    words_dictionary wd ON wf.word_id = wd.word_id;