import base64
import requests
import time
import pandas as pd
import re

class SpotifyClientCredentials:
    OAUTH_TOKEN_URL = "https://accounts.spotify.com/api/token"

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret

    def _make_authorization_headers(self):
        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        return {"Authorization": f"Basic {auth_header}"}

    def get_access_token(self):
        headers = self._make_authorization_headers()
        payload = {"grant_type": "client_credentials"}
        response = requests.post(self.OAUTH_TOKEN_URL, headers=headers, data=payload)
        if response.status_code != 200:
            raise Exception("Failed to retrieve access token")
        token_info = response.json()
        token_info["expires_at"] = int(time.time()) + token_info["expires_in"]
        return token_info["access_token"]

def fetch_playlists(user_id, access_token):
    url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    return response.json()

def fetch_playlist_tracks(playlist_id, access_token):
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    tracks_data = response.json()

    detailed_tracks = []

    for item in tracks_data.get('items', []):
        track = item.get('track', {})
        if track:
            track_id = track.get('id')
            track_name = track.get('name')
            album_name = track.get('album', {}).get('name')
            artist_names = ', '.join([artist['name'] for artist in track.get('artists', [])])
            detailed_tracks.append({
                'id': track_id,
                'name': track_name,
                'album': album_name,
                'artists': artist_names
            })

    return detailed_tracks

def fetch_audio_features(track_ids, access_token):
    url = "https://api.spotify.com/v1/audio-features"
    headers = {"Authorization": f"Bearer {access_token}"}
    data = []
    for track_id in track_ids:
        response = requests.get(f"{url}/{track_id}", headers=headers)
        if response.status_code == 200:
            data.append(response.json())
    return data

def get_track_ids(tracks):
    return [track['id'] for track in tracks]

def create_dataframe(tracks, features):
    tracks_df = pd.DataFrame(tracks)
    features_df = pd.DataFrame(features)
    merged_df = pd.merge(tracks_df, features_df, left_on='id', right_on='id')
    return merged_df

def main():
    client_id = "2e00646f1b2c4e7e9b10b6a07cd89449"
    client_secret = "67063bd95bc84162b501b030fe055d8b"
    credentials_manager = SpotifyClientCredentials(client_id, client_secret)
    access_token = credentials_manager.get_access_token()

    user_input = input("Enter a user ID or playlist ID: ")

    all_tracks = []
    if re.match(r'^[0-9a-zA-Z]{22}$', user_input) or user_input.startswith('spotify:playlist:'):
        tracks = fetch_playlist_tracks(user_input.replace('spotify:playlist:', ''), access_token)
        all_tracks.extend(tracks)
    else:
        playlists_json = fetch_playlists(user_input, access_token)
        if 'items' in playlists_json:
            print("Select playlist(s) to fetch tracks from (comma-separated for multiple):")
            for i, playlist in enumerate(playlists_json['items'], start=1):
                print(f"{i}: {playlist['name']} (ID: {playlist['id']})")
            selected_indexes = input("Enter the number(s) of the playlist(s) you want to fetch tracks for: ")
            selected_indexes = [int(index.strip()) - 1 for index in selected_indexes.split(',') if index.strip().isdigit()]
            
            for index in selected_indexes:
                if index >= 0 and index < len(playlists_json['items']):
                    selected_playlist_id = playlists_json['items'][index]['id']
                    tracks = fetch_playlist_tracks(selected_playlist_id, access_token)
                    all_tracks.extend(tracks)
                else:
                    print(f"Invalid choice: {index + 1}. Skipping...")

            if not all_tracks:
                print("No tracks found or unable to fetch tracks for the selected playlists.")
                return
        else:
            print("No playlists found or unable to fetch playlists for the user.")
            return

    track_ids = get_track_ids(all_tracks)
    features = fetch_audio_features(track_ids, access_token)

    df = create_dataframe(all_tracks, features)
    
    df.to_csv("spotify_audio_features.csv", index=False)
    print("Audio_features saved to spotify_audio_features.csv")
    print(df)


if __name__ == "__main__":
    main()
