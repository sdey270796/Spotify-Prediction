# -*- coding: utf-8 -*-
"""spotify_app.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1ADvML8cQ5IDSNow4gjn7pnDmyLWS_XiE
"""

import subprocess
import sys

subprocess.check_call([sys.executable, "-m", "pip", "install", "streamlit", "-q"])

import gdown
import streamlit as st
import pandas as pd
import numpy as np
import joblib
from joblib import load
import requests
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.cluster import DBSCAN
from sklearn.pipeline import Pipeline
from collections import Counter
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import re
import nltk

# Download stopwords
nltk.download('punkt')
nltk.download('stopwords')

import warnings
warnings.filterwarnings('ignore')

# Load the prediction model
url = 'https://drive.google.com/uc?id=11QzvWm1UdQuTMhJcTht_9LBCnoGMlRxg'
model = 'spotify_best_model.sav'
response = requests.get(url)
with open(model, 'wb') as f:
    f.write(response.content)
model = load(model)

# DBSCAN clustering class
class DBSCANClustering(BaseEstimator, TransformerMixin):
    def __init__(self, eps=0.3, min_samples=5, features=None):
        self.eps = eps
        self.min_samples = min_samples
        self.features = features
        self.dbscan = DBSCAN(eps=self.eps, min_samples=self.min_samples)

    def fit(self, X, y=None):
        return self

    def transform(self, X, y=None):
        X = X.copy()

        # Apply DBSCAN clustering
        X_scaled = StandardScaler().fit_transform(X[self.features])
        cluster_labels = self.dbscan.fit_predict(X_scaled)

        # Reassign noise points (-1) to max(cluster) + 1
        max_cluster = cluster_labels[cluster_labels != -1].max() if cluster_labels[cluster_labels != -1].size > 0 else 0
        cluster_labels = np.where(cluster_labels == -1, max_cluster + 1, cluster_labels)

        # Add cluster labels to the dataset
        X['cluster_label'] = cluster_labels

        # Calculate the integer value of average popularity for each cluster
        avg_popularity = X.groupby('cluster_label')['popularity'].mean().round().astype(int)

        # Add average popularity back to the dataset
        X = X.merge(avg_popularity.rename('average_popularity'), on='cluster_label', how='left')

        # Drop the 'cluster_label' and 'popularity' columns
        X = X.drop(columns=['cluster_label', 'popularity'])

        return X

# Feature engineering class (used during training)
class FeatureEngineering(BaseEstimator, TransformerMixin):
    def __init__(self, original_data):
        self.stop_words = set(stopwords.words('english'))
        self.original_data = original_data

    def tokenize_and_clean(self, text):
        words = word_tokenize(text.lower())
        words = [word for word in words if word.isalpha() and word not in self.stop_words]
        return words

    def fit(self, X, y=None):
        # Extract frequent words and artists
        track_names = self.original_data['track_name'].apply(lambda x: self.tokenize_and_clean(str(x)))
        track_word_count = Counter([word for sublist in track_names for word in sublist])
        self.top_5_track_words = [word for word, _ in track_word_count.most_common(5)]

        album_names = self.original_data['album_name'].apply(lambda x: self.tokenize_and_clean(str(x)))
        album_word_count = Counter([word for sublist in album_names for word in sublist])
        self.top_5_album_words = [word for word, _ in album_word_count.most_common(5)]

        artist_names = self.original_data['artists'].apply(lambda x: str(x).split(';'))
        artist_name_count = Counter([artist.strip().lower() for sublist in artist_names for artist in sublist])
        self.top_5_artists = [artist for artist, _ in artist_name_count.most_common(5)]
        return self

    def transform(self, X, y=None):
        X = X.copy()

        # Create new columns based on the top 5 frequent words and artists
        for word in self.top_5_track_words:
            X[f'{word}_track'] = X['track_name'].apply(lambda x: 1 if word in self.tokenize_and_clean(str(x)) else 0).astype(bool)
        X['Others_track'] = X[[f'{word}_track' for word in self.top_5_track_words]].apply(lambda row: 1 if row.sum() == 0 else 0, axis=1).astype(bool)

        for word in self.top_5_album_words:
            X[f'{word}_album'] = X['album_name'].apply(lambda x: 1 if word in self.tokenize_and_clean(str(x)) else 0).astype(bool)
        X['Others_album'] = X[[f'{word}_album' for word in self.top_5_album_words]].apply(lambda row: 1 if row.sum() == 0 else 0, axis=1).astype(bool)

        for artist in self.top_5_artists:
            X[f'{artist}_artist'] = X['artists'].apply(lambda x: 1 if artist in [name.strip().lower() for name in str(x).split(';')] else 0).astype(bool)
        X['Others_artist'] = X[[f'{artist}_artist' for artist in self.top_5_artists]].apply(lambda row: 1 if row.sum() == 0 else 0, axis=1).astype(bool)

        # Drop unnecessary columns after creating the new ones
        X = X.drop(columns=['track_name', 'album_name', 'artists'])
        return X

# Preprocessing function with feature engineering and clustering
def preprocess_input(user_input, original_data):
    # Convert user input into a dataframe
    input_df = pd.DataFrame([user_input])

    # Apply the custom feature engineering
    feature_engineer = FeatureEngineering(original_data)
    input_df = feature_engineer.fit_transform(input_df)

    # Standardizing the numeric columns
    numeric_cols = input_df.select_dtypes(include=['int64', 'float64']).columns
    scaler = StandardScaler()
    input_df[numeric_cols] = scaler.fit_transform(input_df[numeric_cols])

    # Apply DBSCAN clustering
    clustering_pipeline = Pipeline([
        ('dbscan_clustering', DBSCANClustering(eps=0.3, min_samples=5, features=numeric_cols))
    ])
    input_df = clustering_pipeline.fit_transform(input_df)

    return input_df

# Streamlit app
st.title('Spotify Popularity Prediction and Clustering')

dataset_url = st.text_input("https://drive.google.com/uc?id=1gjkaAyYoVf_nXp1e-84l8IEDjEWZ9PnR")

if dataset_url:
    try:
        # Load dataset from URL
        dataset_url = st.text_input("https://drive.google.com/uc?id=1gjkaAyYoVf_nXp1e-84l8IEDjEWZ9PnR")
        output = 'spotify.csv'
        gdown.download(dataset_url, output, quiet=False)
        original_data = pd.read_csv(dataset_url)
        st.write("Dataset Loaded Successfully!")

        # User input for features
        st.write("### Input the features for the song:")
        track_name = st.text_input("Track Name")
        album_name = st.text_input("Album Name")
        artists = st.text_input("Artists (separated by semicolons)")
        duration_ms = st.number_input("Duration (ms)", min_value=0, max_value=600000, value=200000)
        danceability = st.slider("Danceability", min_value=0.0, max_value=1.0, value=0.5)
        energy = st.slider("Energy", min_value=0.0, max_value=1.0, value=0.5)
        key = st.selectbox("Key", ['C', 'C-sharp_D-flat', 'D', 'D-sharp_E-flat', 'E', 'F', 'F-sharp_G-flat', 'G', 'G-sharp_A-flat', 'A', 'A-sharp_B-flat', 'B'])
        loudness = st.number_input("Loudness (dB)", min_value=-60.0, max_value=0.0, value=-5.0)
        mode = st.selectbox("Mode", ['major', 'minor'])
        speechiness = st.slider("Speechiness", min_value=0.0, max_value=1.0, value=0.1)
        acousticness = st.slider("Acousticness", min_value=0.0, max_value=1.0, value=0.5)
        instrumentalness = st.slider("Instrumentalness", min_value=0.0, max_value=1.0, value=0.0)
        liveness = st.slider("Liveness", min_value=0.0, max_value=1.0, value=0.2)
        valence = st.slider("Valence", min_value=0.0, max_value=1.0, value=0.5)
        tempo = st.number_input("Tempo (BPM)", min_value=0.0, max_value=250.0, value=120.0)
        time_signature = st.selectbox("Time Signature", ['3/4', '4/4', '5/4', '6/4', '7/4'])
        track_genre = st.selectbox("Track Genre", [
                    'acoustic', 'afrobeat', 'alt-rock', 'alternative', 'ambient', 'anime', 'black-metal', 'bluegrass', 'blues', 'brazil',
                    'breakbeat', 'british', 'cantopop', 'chicago-house', 'children', 'chill', 'classical', 'club', 'comedy', 'country',
                    'dance', 'dancehall', 'death-metal', 'deep-house', 'detroit-techno', 'disco', 'disney', 'drum-and-bass', 'dub',
                    'dubstep', 'edm', 'electro', 'electronic', 'emo', 'folk', 'forro', 'french', 'funk', 'garage', 'german', 'gospel',
                    'goth', 'grindcore', 'groove', 'grunge', 'guitar', 'happy', 'hard-rock', 'hardcore', 'hardstyle', 'heavy-metal',
                    'hip-hop', 'honky-tonk', 'house', 'idm', 'indian', 'indie-pop', 'indie', 'industrial', 'iranian', 'j-dance', 'j-idol',
                    'j-pop', 'j-rock', 'jazz', 'k-pop', 'kids', 'latin', 'latino', 'malay', 'mandopop', 'metal', 'metalcore',
                    'minimal-techno', 'mpb', 'new-age', 'opera', 'pagode', 'party', 'piano', 'pop-film', 'pop', 'power-pop',
                    'progressive-house', 'psych-rock', 'punk-rock', 'punk', 'r-n-b', 'reggae', 'reggaeton', 'rock-n-roll', 'rock',
                    'rockabilly', 'romance', 'sad', 'salsa', 'samba', 'sertanejo', 'show-tunes', 'singer-songwriter', 'ska', 'sleep',
                    'songwriter', 'soul', 'spanish', 'study', 'swedish', 'synth-pop', 'tango', 'techno', 'trance', 'trip-hop', 'turkish',
                    'world-music'])

        # Create a dictionary with user inputs
        user_input = {
            'track_name': track_name,
            'album_name': album_name,
            'artists': artists,
            'duration_ms': duration_ms,
            'danceability': danceability,
            'energy': energy,
            'key': key,
            'loudness': loudness,
            'mode': mode,
            'speechiness': speechiness,
            'acousticness': acousticness,
            'instrumentalness': instrumentalness,
            'liveness': liveness,
            'valence': valence,
            'tempo': tempo,
            'time_signature': time_signature,
            'track_genre': track_genre
        }

        # Predict the average popularity based on user input
        if st.button('Predict Popularity'):
            processed_input = preprocess_input(user_input, original_data)
            prediction = model.predict(processed_input)

            # Display the prediction
            st.write(f"### Predicted Average Popularity: {prediction[0]}")
    except Exception as e:
        st.write(f"Error loading dataset: {e}")