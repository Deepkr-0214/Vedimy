import os
import sys

# Get the absolute path to the backend directory
root_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(root_dir, 'backend')

# Add backend to Python path so modules like 'extensions' and 'routes' can be imported
sys.path.insert(0, backend_dir)

# Change the current working directory to backend so that local DB files and static assets resolve correctly
os.chdir(backend_dir)

from app import create_app
from extensions import socketio

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting Vedimy Server from {backend_dir}...")
    print(f"👉 OPEN YOUR BROWSER HERE: http://127.0.0.1:{port}")
    print(f"👉 OR CLICK HERE: http://localhost:{port}\n")
    app = create_app()
    socketio.run(app, debug=True, host='0.0.0.0', port=port)
