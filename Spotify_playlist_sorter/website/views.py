from flask import flash, session, Flask, request, render_template, redirect, url_for, Blueprint, render_template_string
from markupsafe import Markup
from website.Spotify.spotify import SpotifyClientCredentials, fetch_playlists, fetch_playlist_tracks, create_dataframe, fetch_audio_features, get_track_ids
import pandas as pd
import re
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import plotly.express as px
from . import db  
from .models import Note
from datetime import datetime
import requests
import json

views = Blueprint('views', __name__)

# Your Spotify client details
SPOTIFY_CLIENT_ID = '2e00646f1b2c4e7e9b10b6a07cd89449'
SPOTIFY_CLIENT_SECRET = '67063bd95bc84162b501b030fe055d8b'
SPOTIFY_REDIRECT_URI = 'http://localhost:1234/callback'  



# Assuming you have a SpotifyClientCredentials instance globally accessible
credentials_manager = SpotifyClientCredentials(client_id="2e00646f1b2c4e7e9b10b6a07cd89449", client_secret="67063bd95bc84162b501b030fe055d8b")
access_token = credentials_manager.get_access_token()

@views.route('/input', methods=['GET', 'POST'])
def input_user_or_playlist():
    if request.method == 'POST':
        user_input = request.form.get('userOrPlaylistId')
        # Determine if input is a User ID or Playlist ID
        if re.match(r'^[0-9a-zA-Z]{22}$', user_input) or user_input.startswith('spotify:playlist:'):
            # Directly fetch tracks if it's a playlist ID
            return redirect(url_for('views.display_songs', playlist_id=user_input))
        else:
            # Fetch playlists if it's a User ID
            return redirect(url_for('views.display_playlists', user_id=user_input))
    return render_template('input.html')

@views.route('/playlists/<user_id>')
def display_playlists(user_id):
    playlists_json = fetch_playlists(user_id, access_token)
    return render_template('playlists.html', playlists=playlists_json.get('items', []), user_id=user_id)

@views.route('/songs/<playlist_id>')
def display_songs(playlist_id):
    tracks = fetch_playlist_tracks(playlist_id.replace('spotify:playlist:', ''), access_token)
    if tracks:
        track_ids = get_track_ids(tracks)
        features = fetch_audio_features(track_ids, access_token)
        df = create_dataframe(tracks, features)
        
        # Optionally, save the dataframe to CSV
        df.to_csv("spotify_audio_features.csv", index=False)
        
        # Perform clustering
        df = df[['id','name', 'artists', 'danceability', 'energy', 'key',
                 'loudness', 'speechiness', 'acousticness', 'instrumentalness',
                 'liveness', 'valence', 'tempo', 'duration_ms']].drop_duplicates()

        features = ['danceability', 'energy', 'key', 'loudness', 'speechiness',
                    'acousticness', 'instrumentalness', 'liveness', 'valence', 'tempo', 'duration_ms']

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(df[features])

        kmeans = KMeans(n_clusters=4, random_state=42)
        df['cluster'] = kmeans.fit_predict(X_scaled)

        # Map clusters to mood names
        cluster_names = {
            0: 'Energetic/Upbeat',
            1: 'Calm/Relaxed',
            2: 'Sad/Melancholic',
            3: 'Happy/Joyful'
        }
        df['mood'] = df['cluster'].map(cluster_names)

        mood_clusters = df.groupby('mood')['id'].apply(list).to_dict()

        session['mood_clusters'] = mood_clusters
        
        # Prepare songs HTML
        songs_html = df[['name', 'artists']].to_html(escape=False)
        
        # Categorize songs by mood and prepare HTML
        cluster_tables_html = {}
        for mood in cluster_names.values():
            cluster_df = df[df['mood'] == mood]
            mood_html = cluster_df[['name', 'artists']].to_html(escape=False)
            cluster_tables_html[mood] = mood_html
        
        # Construct the final HTML
        final_html = render_template_string("""
        <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Songs Categorized by Mood</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f4f4f4;
            color: #333;
        }
        h2, h3 {
            text-align: center;
            color: #007bff;
        }
        .songs-list, .mood-list {
            margin: 20px auto;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            max-width: 800px;
        }
        .songs-list table, .mood-list div {
            width: 100%;
            border-collapse: collapse;
        }
        .songs-list th, .songs-list td, .mood-list th, .mood-list td {
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        .mood-section {
            margin-bottom: 40px;
        }
        .mood-section:last-child {
            margin-bottom: 0;
        }
        .mood-title {
            margin-top: 0;
            padding-top: 20px;
        }
        .push-playlist-btn {
            display: block;
            width: 200px;
            margin: 20px auto;
            padding: 10px;
            background-color: #007bff;
            color: #ffffff;
            text-align: center;
            border-radius: 5px;
            text-decoration: none;
            font-weight: bold;
        }
        .push-playlist-btn:hover {
            background-color: #0056b3;
        }
    </style>
</head>
<body>
    <a href="{{ url_for('views.push_playlists_to_spotify') }}" class="push-playlist-btn">Push to Spotify</a>
    <h2>List of Songs</h2>
    <div class="songs-list">{{ songs_html|safe }}</div>
    <h2>↓ Categorized by Mood ↓</h2>
    {% for mood, html in cluster_tables_html.items() %}
        <div class="mood-section">
            <h3 class="mood-title">{{ mood }}</h3>
            <div class="mood-list">{{ html|safe }}</div>
        </div>
    {% endfor %}
</body>
</html>


        """, songs_html=songs_html, cluster_tables_html=cluster_tables_html)

        for index, row in df.iterrows():
            new_track = Note(
                track_id=row['id'],
                name=row['name'],
                artists=row['artists'],
                danceability=row['danceability'],
                energy=row['energy'],
                key=row['key'],
                loudness=row['loudness'],
                speechiness=row['speechiness'],
                acousticness=row['acousticness'],
                instrumentalness=row['instrumentalness'],
                liveness=row['liveness'],
                valence=row['valence'],
                tempo=row['tempo'],
                duration_ms=row['duration_ms'],
                playlist_id=playlist_id.replace('spotify:playlist:', ''),  # Adjust as necessary
                mood=row['mood']
            )
            db.session.add(new_track)
        db.session.commit()
        
        return final_html
    else:
        return "No tracks found or unable to fetch tracks for the selected playlist."


@views.route('/process_playlists', methods=['POST'])
def process_playlists():
    selected_playlist_ids = request.form.getlist('playlist_ids')
    
    all_tracks_info = []  # This will store both metadata and features

    for playlist_id in selected_playlist_ids:
        tracks_metadata = fetch_playlist_tracks(playlist_id, access_token)
        if tracks_metadata:
            track_ids = [track['id'] for track in tracks_metadata]
            features = fetch_audio_features(track_ids, access_token)
            # Merge features with metadata
            for feature in features:
                # Find the track metadata that matches this feature
                track_info = next((item for item in tracks_metadata if item['id'] == feature['id']), None)
                if track_info:
                    # Combine the metadata with features
                    combined_info = {**track_info, **feature}
                    all_tracks_info.append(combined_info)

    if all_tracks_info:
        df = pd.DataFrame(all_tracks_info)

        df = df[['id', 'name', 'artists', 'danceability', 'energy', 'key',
                 'loudness', 'speechiness', 'acousticness', 'instrumentalness',
                 'liveness', 'valence', 'tempo', 'duration_ms']].drop_duplicates()

        if 'name' in df.columns and 'artists' in df.columns:
            features = ['danceability', 'energy', 'key', 'loudness', 'speechiness',
                        'acousticness', 'instrumentalness', 'liveness', 'valence', 'tempo', 'duration_ms']
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(df[features])

            kmeans = KMeans(n_clusters=4, random_state=42)
            df['cluster'] = kmeans.fit_predict(X_scaled)

            # Map clusters to mood names
            cluster_names = {
                0: 'Energetic/Upbeat',
                1: 'Calm/Relaxed',
                2: 'Sad/Melancholic',
                3: 'Happy/Joyful'
            }
            df['mood'] = df['cluster'].map(cluster_names)

            mood_clusters = df.groupby('mood')['id'].apply(list).to_dict()

            session['mood_clusters'] = mood_clusters

            # Prepare songs HTML
            songs_html = df[['name', 'artists']].to_html(escape=False)
            
            # Categorize songs by mood and prepare HTML
            cluster_tables_html = {}
            for mood in cluster_names.values():
                cluster_df = df[df['mood'] == mood]
                mood_html = cluster_df[['name', 'artists']].to_html(escape=False)
                cluster_tables_html[mood] = mood_html
            
            # Construct the final HTML
            final_html = render_template_string("""
            <!DOCTYPE html>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Playlist Analysis</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            background-color: #f0f8ff;
            color: #333;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        h2 {
            color: #0056b3;
            margin-bottom: 20px;
        }
        .push-playlist-btn {
            display: block;
            width: 200px;
            margin: 0 auto 20px;
            padding: 10px;
            background-color: #007bff;
            color: #ffffff;
            text-align: center;
            border-radius: 5px;
            text-decoration: none;
            font-weight: bold;
            cursor: pointer;
        }
        .push-playlist-btn:hover {
            background-color: #0056b3;
        }
        .songs-list, .mood-section {
            width: 100%;
            max-width: 800px;
            margin-bottom: 20px;
            padding: 20px;
            background-color: #fff;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }
        h3 {
            color: #007bff;
            margin-top: 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 8px;
            border-bottom: 1px solid #ddd;
            text-align: left;
        }
    </style>
</head>
<body>
    <!-- Button for pushing playlists to Spotify -->
    <a href="{{ url_for('views.push_playlists_to_spotify') }}" class="push-playlist-btn">Push to Spotify</a>

    
    <h2>List of Songs</h2>
    <div class="songs-list">{{ songs_html|safe }}</div>
    <h2>↓ Categorized by Mood ↓</h2>
    {% for mood, html in cluster_tables_html.items() %}
        <div class="mood-section">
            <h3>{{ mood }}</h3>
            <div>{{ html|safe }}</div>
        </div>
    {% endfor %}
</body>
</html>

            """, songs_html=songs_html, cluster_tables_html=cluster_tables_html)

            for index, row in df.iterrows():
                new_track = Note(
                    track_id=row['id'],
                    name=row['name'],
                    artists=row['artists'],
                    danceability=row['danceability'],
                    energy=row['energy'],
                    key=row['key'],
                    loudness=row['loudness'],
                    speechiness=row['speechiness'],
                    acousticness=row['acousticness'],
                    instrumentalness=row['instrumentalness'],
                    liveness=row['liveness'],
                    valence=row['valence'],
                    tempo=row['tempo'],
                    duration_ms=row['duration_ms'],
                    playlist_id=playlist_id.replace('spotify:playlist:', ''),  # Adjust as necessary
                    mood=row['mood']
                )
                db.session.add(new_track)
            db.session.commit()
            
            return final_html
        else:
            return "Missing 'name' or 'artists' column in the DataFrame."
    else:
        return "No tracks found or unable to fetch tracks for the selected playlists."
    
@views.route('/spotify_login')
def spotify_login():
    # The scopes the app requires
    scope = "playlist-modify-public playlist-modify-private"
    # Redirect user to Spotify's authorization page
    return redirect(f"https://accounts.spotify.com/authorize?client_id={SPOTIFY_CLIENT_ID}&response_type=code&redirect_uri={SPOTIFY_REDIRECT_URI}&scope={scope}")

@views.route('/callback')
def spotify_callback():
    error = request.args.get('error')
    code = request.args.get('code')
    if error:
        flash(f"Error during Spotify authentication: {error}", "error")  # Display error to user
        return redirect(url_for('views.input_user_or_playlist'))  # Redirect to input page

    # Exchange the code for an access token
    auth_token_url = "https://accounts.spotify.com/api/token"
    payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': SPOTIFY_REDIRECT_URI,
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET,
    }
    response = requests.post(auth_token_url, data=payload)

    if response.status_code == 200:
        # Extract the access token from the response
        access_token = response.json().get('access_token')
        # Store the access token in the session for later use
        session['access_token'] = access_token
        flash("Successfully authenticated with Spotify.", "success")  # Inform user of successful login
        return redirect(url_for('views.input_user_or_playlist'))  # Redirect to input page
    else:
        flash("Failed to get access token from Spotify.", "error")  # Inform user of failure
        return redirect(url_for('views.input_user_or_playlist'))  # Redirect to input page

@views.route('/push_playlists_to_spotify')
def push_playlists_to_spotify():
    access_token = session.get('access_token')
    if not access_token:
        flash('You must be logged in to push playlists to Spotify.', 'error')
        return redirect(url_for('views.spotify_login'))

    user_id = '22dwt6rzglo62icgq5ner5wfi'
    if not user_id:
        flash("Spotify user ID not found.", 'error')
        return redirect(url_for('views.spotify_login'))

    mood_clusters = session.get('mood_clusters', {})
    if not mood_clusters:
        flash("No mood-based track clusters found.", 'error')
        return redirect(url_for('views.display_songs'))  # Adjust as needed

    for mood, track_uris in mood_clusters.items():
        playlist_name = f"{mood}_{datetime.now().strftime('%Y-%m-%d')}"
        playlist_id = create_playlist(user_id, playlist_name, access_token)
        if playlist_id:
            success = add_tracks_to_playlist(playlist_id, track_uris, access_token)
            if not success:
                flash(f"Failed to add tracks to the playlist '{playlist_name}'.", 'error')
        else:
            flash("Failed to create a playlist.", 'error')

    return redirect(url_for('views.input_user_or_playlist'))  # Adjust the redirect as needed


def create_playlist(user_id, name, access_token):
    url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = json.dumps({"name": name, "description": "Created via Mood Playlist Generator", "public": False})

    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 201:
        playlist_data = response.json()
        playlist_id = playlist_data['id']  # Extracting the playlist ID
        return playlist_id  # You can return the whole response or just the ID
    return None

def add_tracks_to_playlist(playlist_id, track_ids, access_token):
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = json.dumps({"uris": [f"spotify:track:{track_id}" for track_id in track_ids]})

    response = requests.post(url, headers=headers, data=payload)
    return response.status_code == 201 or response.status_code == 200