from flask import Flask, jsonify, request
from flask_sockets import Sockets
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from threading import Thread, Lock
import json
from utils import get_smartapi_session
import os
import time
from decouple import config

app = Flask(__name__)
sockets = Sockets(app)

API_KEY = config('API_KEY')
USERNAME = config('USERNAME')

correlation_id = "abc123"
mode = 1

live_data = []
data_lock = Lock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKENS_FILE_PATH = os.path.join(BASE_DIR, "tokens.json")

def load_initial_tokens():
    global token_list
    token_list = load_tokens_from_file()
    print(f"Loaded tokens: {token_list}")

def save_tokens_to_file(tokens):
    with open(TOKENS_FILE_PATH, "w") as file:
        json.dump(tokens, file)

def load_tokens_from_file():
    try:
        with open(TOKENS_FILE_PATH, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return []

token_list = load_tokens_from_file()
print(token_list)


class LiveDataStream:
    """Manages the WebSocket connection and data streaming."""

    def __init__(self):
        self.obj = get_smartapi_session()
        if self.obj:
            self.feed_token = self.obj['feedToken']
            self.auth_token = self.obj['authToken']
            self.sws = None
            self.connected = False
            self.thread = None
        else:
            print("Error: Failed to authenticate with SmartAPI")

    def initialize_connection(self):
        """Initialize WebSocket connection."""
        if not self.auth_token or not self.feed_token:
            print("Error: Authentication tokens missing, cannot initialize connection.")
            return

        self.sws = SmartWebSocketV2(self.auth_token, API_KEY, USERNAME, self.feed_token)
        self.sws.on_open = self.on_open
        self.sws.on_data = self.on_data
        self.sws.on_error = self.on_error
        self.sws.on_close = self.on_close
        try:
            self.sws.connect()
            print("qwertyui")
        except Exception as e:
            print(f"Error: WebSocket connection failed: {str(e)}")
            self.retry_connection()

    def on_open(self, wsapp):
        """Handle WebSocket open event."""
        try:
            if token_list:
                self.sws.subscribe(correlation_id, mode, token_list)
                print("Info: WebSocket connection opened and subscribed.")
                self.connected = True
            else:
                print("Warning: No tokens to subscribe. Please update the token list.")
        except Exception as e:
            print(f"Error: Subscription failed: {str(e)}")
            self.connected = False

    def on_data(self, wsapp, message):
        """Handle incoming WebSocket data."""
        try:
            if isinstance(message, dict):
                data = message
            else:
                data = json.loads(message)
            
            with data_lock:
                live_data.append(data)
            print(f"{data}")
        except json.JSONDecodeError as e:
            print(f"Error: JSON decoding error: {str(e)}")
        except Exception as e:
            print(f"Error: Unexpected error parsing message: {str(e)}")

    def on_error(self, wsapp, error):
        """Handle WebSocket errors."""
        print(f"Error: WebSocket encountered an error: {str(error)}")
        self.retry_connection()

    def on_close(self, wsapp):
        """Handle WebSocket close event."""
        print("Warning: WebSocket connection closed.")
        self.connected = False
        self.retry_connection()

    def retry_connection(self):
        """Retry the WebSocket connection."""
        # print("Info: Retrying WebSocket connection...")
        self.connected = False
        if self.thread and self.thread.is_alive():
            self.thread.join()

        self.thread = Thread(target=self.initialize_connection, daemon=True)
        self.thread.start()
        time.sleep(2)
        if token_list:
            print(f"Subscribing to updated token list: {token_list}")
            self.sws.subscribe(correlation_id, mode, token_list)
        # print("Info: WebSocket reconnected.")

    def stop_connection(self):
        """Stop WebSocket connection."""
        if self.sws:
            self.sws.close_connection()


# Initialize LiveDataStream
data_stream = LiveDataStream()


@app.route('/live-data', methods=['GET'])
def get_live_data():
    """Fetch the live data."""
    with data_lock:
        return jsonify(live_data), 200


@app.route('/update-tokens', methods=['POST'])
def update_tokens():
    global token_list
    try:
        data = request.get_json()
        new_tokens = data.get('token_list', [])

        with data_lock:
            token_list = new_tokens
            save_tokens_to_file(token_list)

        print("Retrying WebSocket connection after updating tokens.")
        data_stream.retry_connection()

        return jsonify({"message": "Token list updated successfully", "token_list": token_list}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400



def start_websocket_stream():
    """Start the WebSocket connection in a separate thread."""
    if data_stream.obj:
        data_stream.thread = Thread(target=data_stream.initialize_connection, daemon=True)
        data_stream.thread.start()
        print("Info: WebSocket streaming started in a separate thread.")
    else:
        print("Error: Failed to start WebSocket streaming due to authentication error.")


if __name__ == '__main__':
    load_initial_tokens()
    start_websocket_stream()

    app.debug = True
    app.run(port=5000)
