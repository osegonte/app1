import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from db_connector import FilmFluentDB

def run_visualization_app():
    st.set_page_config(page_title="FilmFluent Visualizations", layout="wide")
    
    st.title("FilmFluent Data Visualization")
    
    # Connect to database
    db = FilmFluentDB()
    if not db.connect():
        st.error("Failed to connect to database")
        return
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Overview", "Movie Analysis", "Word Analysis", "Translation Progress"])
    
    if page == "Overview":
        show_overview(db)
    elif page == "Movie Analysis":
        show_movie_analysis(db)
    elif page == "Word Analysis":
        show_word_analysis(db)
    elif page == "Translation Progress":
        show_translation_progress(db)
    
    db.close()

def show_overview(db):
    st.header("Database Overview")
    
    # Query for overview stats
    db.cur.execute("""
        SELECT COUNT(DISTINCT m.movie_id) as movie_count,
               COUNT(DISTINCT wf.word_id) as unique_words_count,
               SUM(ar.total_words) as total_words,
               SUM(ar.total_sentences) as total_sentences
        FROM movies m
        JOIN subtitle_files sf ON m.movie_id = sf.movie_id
        JOIN analysis_results ar ON sf.file_id = ar.file_id
        JOIN word_frequencies wf ON sf.file_id = wf.file_id
    """)
    
    overview = db.cur.fetchone()
    
    # Display stats in columns
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Movies", overview['movie_count'])
    with col2:
        st.metric("Unique Words", overview['unique_words_count'])
    with col3:
        st.metric("Total Words", f"{overview['total_words']:,}")
    with col4:
        st.metric("Total Sentences", f"{overview['total_sentences']:,}")
    
    # Movie word count comparison
    st.subheader("Movies by Word Count")
    db.cur.execute("""
        SELECT m.title, ar.total_words, ar.unique_words
        FROM movies m
        JOIN subtitle_files sf ON m.movie_id = sf.movie_id
        JOIN analysis_results ar ON sf.file_id = ar.file_id
        ORDER BY ar.total_words DESC
        LIMIT 10
    """)
    
    movie_stats = pd.DataFrame(db.cur.fetchall())
    if not movie_stats.empty:
        fig = px.bar(movie_stats, x='title', y=['total_words', 'unique_words'], 
                     title="Word Counts by Movie",
                     labels={'value': 'Count', 'variable': 'Type'},
                     barmode='group')
        st.plotly_chart(fig, use_container_width=True)

def show_movie_analysis(db):
    st.header("Movie Analysis")
    
    # Get list of movies
    db.cur.execute("SELECT movie_id, title, release_year FROM movies ORDER BY title")
    movies = db.cur.fetchall()
    
    # Create a dropdown to select movie
    selected_movie = st.selectbox(
        "Select a movie:",
        options=[(m['movie_id'], f"{m['title']} ({m['release_year'] or 'N/A'})") for m in movies],
        format_func=lambda x: x[1]
    )
    
    if selected_movie:
        movie_id = selected_movie[0]
        
        # Get movie details
        db.cur.execute("""
            SELECT m.title, m.release_year, sf.filename, 
                   ar.total_words, ar.unique_words, ar.total_sentences,
                   sf.file_id
            FROM movies m
            JOIN subtitle_files sf ON m.movie_id = sf.movie_id
            JOIN analysis_results ar ON sf.file_id = ar.file_id
            WHERE m.movie_id = %s
        """, (movie_id,))
        
        movie_details = db.cur.fetchone()
        
        if movie_details:
            # Display movie details
            st.subheader(f"{movie_details['title']} ({movie_details['release_year'] or 'N/A'})")
            
            # Display metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Words", f"{movie_details['total_words']:,}")
            with col2:
                st.metric("Unique Words", f"{movie_details['unique_words']:,}")
            with col3:
                st.metric("Vocabulary Diversity", 
                          f"{(movie_details['unique_words']/movie_details['total_words']*100):.1f}%")
            
            # Word cloud placeholder (would need wordcloud library)
            st.subheader("Top Words")
            
            # Get top words
            db.cur.execute("""
                SELECT w.word, wf.frequency 
                FROM word_frequencies wf
                JOIN words_dictionary w ON wf.word_id = w.word_id
                WHERE wf.file_id = %s
                ORDER BY wf.frequency DESC
                LIMIT 25
            """, (movie_details['file_id'],))
            
            word_data = pd.DataFrame(db.cur.fetchall())
            if not word_data.empty:
                fig = px.bar(word_data, x='word', y='frequency', 
                             title="Most Frequent Words",
                             labels={'word': 'Word', 'frequency': 'Frequency'})
                st.plotly_chart(fig, use_container_width=True)
            
            # Translation status
            st.subheader("Translation Status")
            db.cur.execute("""
                SELECT tl.language_name, 
                       COUNT(wt.translation_id) as translated_count,
                       ar.unique_words as total_unique_words,
                       COUNT(wt.translation_id)::float / ar.unique_words * 100 as percent_translated
                FROM target_languages tl
                LEFT JOIN word_translations wt ON tl.language_id = wt.language_id
                JOIN word_frequencies wf ON wt.word_id = wf.word_id
                JOIN analysis_results ar ON wf.file_id = ar.file_id
                WHERE wf.file_id = %s
                GROUP BY tl.language_name, ar.unique_words
                ORDER BY percent_translated DESC
            """, (movie_details['file_id'],))
            
            translation_data = pd.DataFrame(db.cur.fetchall())
            if not translation_data.empty:
                fig = px.bar(translation_data, x='language_name', y='percent_translated',
                             title="Translation Progress by Language",
                             labels={'language_name': 'Language', 'percent_translated': '% Translated'})
                fig.update_layout(yaxis_range=[0, 100])
                st.plotly_chart(fig, use_container_width=True)

def show_word_analysis(db):
    st.header("Word Analysis")
    
    # Get top words across all movies
    db.cur.execute("""
        SELECT w.word, SUM(wf.frequency) as total_frequency, COUNT(DISTINCT sf.file_id) as movie_count
        FROM word_frequencies wf
        JOIN words_dictionary w ON wf.word_id = w.word_id
        JOIN subtitle_files sf ON wf.file_id = sf.file_id
        WHERE w.is_stopword = FALSE
        GROUP BY w.word
        ORDER BY total_frequency DESC
        LIMIT 50
    """)
    
    global_words = pd.DataFrame(db.cur.fetchall())
    if not global_words.empty:
        st.subheader("Most Common Words Across All Movies")
        fig = px.bar(global_words.head(20), x='word', y='total_frequency',
                     title="Most Frequent Words Overall",
                     labels={'word': 'Word', 'total_frequency': 'Total Frequency'})
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("Words by Movie Occurrence")
        fig = px.scatter(global_words, x='total_frequency', y='movie_count', text='word',
                         title="Word Frequency vs. Movie Occurrence",
                         labels={'total_frequency': 'Total Frequency', 'movie_count': 'Number of Movies'})
        st.plotly_chart(fig, use_container_width=True)
    
    # Word search
    st.subheader("Word Search")
    search_word = st.text_input("Enter a word to search:")
    if search_word:
        db.cur.execute("""
            SELECT m.title, wf.frequency
            FROM word_frequencies wf
            JOIN words_dictionary w ON wf.word_id = w.word_id
            JOIN subtitle_files sf ON wf.file_id = sf.file_id
            JOIN movies m ON sf.movie_id = m.movie_id
            WHERE w.word = %s
            ORDER BY wf.frequency DESC
        """, (search_word.lower(),))
        
        word_results = pd.DataFrame(db.cur.fetchall())
        if not word_results.empty:
            fig = px.bar(word_results, x='title', y='frequency',
                         title=f"Frequency of '{search_word}' by Movie",
                         labels={'title': 'Movie', 'frequency': 'Frequency'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"No occurrences of '{search_word}' found.")

def show_translation_progress(db):
    st.header("Translation Progress")
    
    # Translation overview
    db.cur.execute("""
        SELECT tl.language_name, COUNT(DISTINCT wt.word_id) as translated_words
        FROM target_languages tl
        LEFT JOIN word_translations wt ON tl.language_id = wt.language_id
        GROUP BY tl.language_name
        ORDER BY translated_words DESC
    """)
    
    translation_overview = pd.DataFrame(db.cur.fetchall())
    if not translation_overview.empty:
        fig = px.bar(translation_overview, x='language_name', y='translated_words',
                     title="Words Translated by Language",
                     labels={'language_name': 'Language', 'translated_words': 'Words Translated'})
        st.plotly_chart(fig, use_container_width=True)
    
    # Translation progress over time (would need timestamps)
    st.subheader("Recent Translations")
    db.cur.execute("""
        SELECT w.word, wt.translation, tl.language_name, wt.created_at
        FROM word_translations wt
        JOIN words_dictionary w ON wt.word_id = w.word_id
        JOIN target_languages tl ON wt.language_id = tl.language_id
        ORDER BY wt.created_at DESC
        LIMIT 100
    """)
    
    recent_translations = pd.DataFrame(db.cur.fetchall())
    if not recent_translations.empty:
        st.dataframe(recent_translations)

if __name__ == "__main__":
    run_visualization_app()