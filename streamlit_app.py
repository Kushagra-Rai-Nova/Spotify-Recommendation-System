import streamlit as st
import requests
import base64
import pandas as pd
import spotipy
import plotly.express as px
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime

# Spotify API credentials
CLIENT_ID = '04f7d8078cc94e0c98cb9efc7838ec6a'
CLIENT_SECRET = 'f8a6603864b64dd68344c9fdd91b9f42'

# Base64 encode the client ID and client secret
client_credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
client_credentials_base64 = base64.b64encode(client_credentials.encode())

# Request the access token
token_url = 'https://accounts.spotify.com/api/token'
headers = {
    'Authorization': f'Basic {client_credentials_base64.decode()}'
}
data = {
    'grant_type': 'client_credentials'
}
response = requests.post(token_url, data=data, headers=headers)

if response.status_code == 200:
    access_token = response.json()['access_token']
    st.success("Access token obtained successfully.")
else:
    st.error("Error obtaining access token.")
    st.stop()

def get_trending_playlist_data(playlist_id, access_token):
    sp = spotipy.Spotify(auth=access_token)
    playlist_tracks = sp.playlist_tracks(playlist_id, fields='items(track(id, name, artists, album(id, name)))')

    music_data = []
    for track_info in playlist_tracks['items']:
        track = track_info['track']
        track_name = track['name']
        artists = ', '.join([artist['name'] for artist in track['artists']])
        album_name = track['album']['name']
        album_id = track['album']['id']
        track_id = track['id']

        audio_features = sp.audio_features(track_id)[0] if track_id != 'Not available' else None

        try:
            album_info = sp.album(album_id) if album_id != 'Not available' else None
            release_date = album_info['release_date'] if album_info else None
        except:
            release_date = None

        try:
            track_info = sp.track(track_id) if track_id != 'Not available' else None
            popularity = track_info['popularity'] if track_info else None
        except:
            popularity = None

        track_data = {
            'Track Name': track_name,
            'Artists': artists,
            'Album Name': album_name,
            'Album ID': album_id,
            'Track ID': track_id,
            'Popularity': popularity,
            'Release Date': release_date,
            'Duration (ms)': audio_features['duration_ms'] if audio_features else None,
            'Explicit': track_info.get('explicit', None),
            'External URLs': track_info.get('external_urls', {}).get('spotify', None),
            'Danceability': audio_features['danceability'] if audio_features else None,
            'Energy': audio_features['energy'] if audio_features else None,
            'Key': audio_features['key'] if audio_features else None,
            'Loudness': audio_features['loudness'] if audio_features else None,
            'Mode': audio_features['mode'] if audio_features else None,
            'Speechiness': audio_features['speechiness'] if audio_features else None,
            'Acousticness': audio_features['acousticness'] if audio_features else None,
            'Instrumentalness': audio_features['instrumentalness'] if audio_features else None,
            'Liveness': audio_features['liveness'] if audio_features else None,
            'Valence': audio_features['valence'] if audio_features else None,
            'Tempo': audio_features['tempo'] if audio_features else None,
        }

        music_data.append(track_data)

    df = pd.DataFrame(music_data)
    return df

def extract_playlist_id(playlist_link):
    # Extract the playlist ID from the provided link
    try:
        playlist_id = playlist_link.split("/")[-1].split("?")[0]
        return playlist_id
    except IndexError:
        return None

# Streamlit app layout
st.title("Spotify Playlist Analysis and Recommendations")

# Input field for the Spotify playlist link
playlist_link = st.text_input("Enter Spotify playlist link:", "https://open.spotify.com/playlist/6DSdE2wZ57zr6yeUKrxXZK")

if playlist_link:
    playlist_id = extract_playlist_id(playlist_link)
    if playlist_id:
        music_df = get_trending_playlist_data(playlist_id, access_token)
        st.write(music_df)
        st.write("Null values in DataFrame:", music_df.isnull().sum())

        # Data preprocessing and normalization
        scaler = MinMaxScaler()
        music_features = music_df[['Danceability', 'Energy', 'Key', 'Loudness', 'Mode', 'Speechiness', 'Acousticness', 'Instrumentalness', 'Liveness', 'Valence', 'Tempo']].values
        music_features_scaled = scaler.fit_transform(music_features)

        # Function for content-based recommendations
        def content_based_recommendations(input_song_name, num_recommendations=5):
            if input_song_name not in music_df['Track Name'].values:
                st.error(f"'{input_song_name}' not found in the dataset. Please enter a valid song name.")
                return None

            input_song_index = music_df[music_df['Track Name'] == input_song_name].index[0]
            similarity_scores = cosine_similarity([music_features_scaled[input_song_index]], music_features_scaled)
            similar_song_indices = similarity_scores.argsort()[0][::-1][1:num_recommendations + 1]
            recommendations = music_df.iloc[similar_song_indices][['Track Name', 'Artists', 'Album Name', 'Release Date', 'Popularity']]
            return recommendations

        # Function for hybrid recommendations
        def calculate_weighted_popularity(release_date):
            release_date = datetime.strptime(release_date, '%Y-%m-%d')
            time_span = datetime.now() - release_date
            weight = 1 / (time_span.days + 1)
            return weight

        def hybrid_recommendations(input_song_name, num_recommendations=5, alpha=0.5):
            if input_song_name not in music_df['Track Name'].values:
                st.error(f"'{input_song_name}' not found in the dataset. Please enter a valid song name.")
                return None

            content_based_rec = content_based_recommendations(input_song_name, num_recommendations)
            popularity_score = music_df.loc[music_df['Track Name'] == input_song_name, 'Popularity'].values[0]
            weighted_popularity_score = popularity_score * calculate_weighted_popularity(music_df.loc[music_df['Track Name'] == input_song_name, 'Release Date'].values[0])

            input_song_df = pd.DataFrame({
                'Track Name': [input_song_name],
                'Artists': [music_df.loc[music_df['Track Name'] == input_song_name, 'Artists'].values[0]],
                'Album Name': [music_df.loc[music_df['Track Name'] == input_song_name, 'Album Name'].values[0]],
                'Release Date': [music_df.loc[music_df['Track Name'] == input_song_name, 'Release Date'].values[0]],
                'Popularity': [weighted_popularity_score]
            })

            hybrid_recommendations = pd.concat([content_based_rec, input_song_df], ignore_index=True)
            hybrid_recommendations = hybrid_recommendations.sort_values(by='Popularity', ascending=False)
            hybrid_recommendations = hybrid_recommendations[hybrid_recommendations['Track Name'] != input_song_name]
            return hybrid_recommendations

        # Select a song for recommendations
        input_song_name = st.selectbox("Select a song for recommendations", music_df['Track Name'].unique())
        if input_song_name:
            recommendations = hybrid_recommendations(input_song_name, num_recommendations=5)
            if recommendations is not None:
                st.write(f"Hybrid recommended songs for '{input_song_name}':")
                st.write(recommendations)

        # Graphs
        st.title("Graphs")

        # Popularity distribution
        fig = px.histogram(music_df, x='Popularity', nbins=20, title='Popularity Distribution')
        st.plotly_chart(fig)

        # Danceability vs Energy
        fig = px.scatter(music_df, x='Danceability', y='Energy', color='Popularity', title='Danceability vs Energy')
        st.plotly_chart(fig)

        # Release dates
        fig = px.histogram(music_df, x='Release Date', nbins=20, title='Release Date Distribution')
        st.plotly_chart(fig)

        # Acousticness distribution
        fig = px.histogram(music_df, x='Acousticness', nbins=20, title='Acousticness Distribution')
        st.plotly_chart(fig)
    else:
        st.error("Invalid playlist link. Please enter a valid Spotify playlist link.")
else:
    st.info("Please enter a Spotify playlist link to get started.")
