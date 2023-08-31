import threading, time, os, signal, requests
from flask import Flask, request, session, redirect, url_for, jsonify
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Create a Flask app instance
app = Flask(__name__)

# Configure session settings
app.config['SESSION_COOKIE_NAME'] = 'Spotify Cookie'
app.secret_key = 'SECRET KEY'
TOKEN_INFO = 'token_info'

# Route to handle logging in
@app.route('/')
def login():
    # Generate authorization URL using Spotify OAuth
    auth_url = create_spotify_oauth().get_authorize_url()
    return redirect(auth_url)

# Route to handle the redirect URI after authorization
@app.route('/redirect_page')
def redirect_page():
    # Clear any existing session data
    session.clear()
    # Get the authorization code from the request
    code = request.args.get('code')
    # Exchange code for access token and save in session
    token_info = create_spotify_oauth().get_access_token(code)
    session[TOKEN_INFO] = token_info
    
    return redirect(url_for('save_discover_weekly', _external=True))

# Route to save the Discover Weekly songs to a playlist
@app.route('/saveDiscoverWeekly')
def save_discover_weekly():
    try:
        # Get token info from the session
        token_info = get_token()
    except:
        # Redirect user to login if token info not found
        return redirect("/")
    
    # Create Spotipy instance with access token
    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_id = sp.current_user()['id']

    # Find or create playlist IDs
    discover_weekly_playlist_id, saved_weekly_playlist_id = find_playlist_ids(sp.current_user_playlists()['items'])

    if not discover_weekly_playlist_id:
        return 'Discover Weekly not found.'

    if not saved_weekly_playlist_id:
        saved_weekly_playlist_id = create_saved_weekly_playlist(sp, user_id)

    # Get tracks from playlists and check for duplicates
    discover_weekly_tracks = sp.playlist_items(discover_weekly_playlist_id)['items']
    saved_weekly_tracks = sp.user_playlist_tracks(user_id, saved_weekly_playlist_id)['items']
    saved_weekly_uris = [track['track']['uri'] for track in saved_weekly_tracks]

    song_uris = [song['track']['uri'] for song in discover_weekly_tracks if song['track']['uri'] not in saved_weekly_uris]

    # Add new tracks to the saved weekly playlist
    if song_uris:
        sp.user_playlist_add_tracks(user_id, saved_weekly_playlist_id, song_uris)

    return 'Discover Weekly songs added successfully'

# Function to find playlist IDs
def find_playlist_ids(playlists):
    discover_weekly_playlist_id = None
    saved_weekly_playlist_id = None

    for playlist in playlists:
        if playlist['name'] == 'Discover Weekly':
            discover_weekly_playlist_id = playlist['id']
        if playlist['name'] == 'Discover Weekly Archive':
            saved_weekly_playlist_id = playlist['id']

    return discover_weekly_playlist_id, saved_weekly_playlist_id

# Function to create saved weekly playlist
def create_saved_weekly_playlist(sp, user_id):
    new_playlist = sp.user_playlist_create(user_id, 'dw archive', True)
    return new_playlist['id']

# Function to get token from session or refresh if needed
def get_token():
    token_info = session.get(TOKEN_INFO, None)
    if not token_info:
        return redirect(url_for('login', _external=False))

    now = int(time.time())
    if token_info['expires_at'] - now < 60:
        spotify_oauth = create_spotify_oauth()
        token_info = spotify_oauth.refresh_access_token(token_info['refresh_token'])

    return token_info

# Function to create Spotify OAuth instance
def create_spotify_oauth():
    return SpotifyOAuth(
        client_id='CLIENT ID',
        client_secret='SECRET ID',
        redirect_uri=url_for('redirect_page', _external=True),
        scope='user-library-read playlist-modify-public playlist-modify-private'
    )

# Route to stop the server
@app.route('/stopServer', methods=['GET'])
def stop_server():
    os.kill(os.getpid(), signal.SIGINT)
    return jsonify({"success": True, "message": "Server is shutting down..."})

# Function to run the Flask app in a separate thread
def run_flask_app():
    app.run()

# Main entry point
if __name__ == '__main__':
    # Start Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.start()

    # Configure Selenium WebDriver
    options = webdriver.ChromeOptions()
    options.headless = True
    driver = webdriver.Chrome(options=options)

    try:
        # Open the Spotify login page using Selenium
        driver.execute_script("window.open('http://localhost:5000/', '_blank');")

        wait = WebDriverWait(driver, 10)
        driver.switch_to.window(driver.window_handles[-1])
        username = wait.until(EC.presence_of_element_located((By.ID, 'login-username')))
        username.clear()
        username.send_keys("USERNAME")

        password = driver.find_element(By.ID, "login-password")
        password.clear()
        password.send_keys("PASSWORD")

        login = driver.find_element(By.ID, "login-button")
        login.click()

        time.sleep(5)
    finally:
        # Close browser window and stop the Flask server
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            driver.close()

        requests.get('http://localhost:5000/stopServer')
