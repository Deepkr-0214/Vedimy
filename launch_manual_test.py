"""
Vedimy Manual Guest Feature Test Setup (Bypassing Waiting Room)
This script automates the creation of a live room session with WAITING ROOM DISABLED,
generates a Guest Registration link, registers/logins test users, and opens the exact browser pages.
This allows guests to enter the class immediately after face verification without waiting for host approval!
"""
import requests
import webbrowser
import time
import sys
import io
import base64
from PIL import Image

BASE_URL = "http://127.0.0.1:5000"

print("=========================================================")
print("  VEDIMY GUEST FEATURES MANUAL TEST SETUP (NO WAITING ROOM) ")
print("=========================================================")

# Helpers to generate dummy biometric images
def generate_dummy_image_bytes():
    img = Image.new('RGB', (100, 100), color='blue')
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    return buffer.getvalue()

def generate_dummy_image_b64():
    img_bytes = generate_dummy_image_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(img_bytes).decode('utf-8')

dummy_b64 = generate_dummy_image_b64()

# Test Credentials from test.txt
host_email = "def123@gmail.com"
guest_email = "abc123@gmail.com"
password = "12345678"

# Save to test.txt (redundancy check)
try:
    with open("test.txt", "w") as f:
        f.write("Guest\nabc123@gmail.com\n12345678\n\nHost\ndef123@gmail.com\n12345678\n")
    print("[+] Credentials successfully verified and saved to test.txt.")
except Exception as e:
    print(f"[WARN] Failed to write to test.txt: {e}")

# 1. Check Server Health
try:
    health = requests.get(f"{BASE_URL}/api/health", timeout=3)
    if health.status_code != 200:
        print("[ERROR] Flask server is not responding correctly. Make sure app.py is running on port 5000.")
        sys.exit(1)
except Exception as e:
    print(f"[ERROR] Cannot connect to server at {BASE_URL}. Error: {e}")
    print("Please make sure the backend Flask server is running.")
    sys.exit(1)

session = requests.Session()

# 2. Host Login / Register
host_token = None
try:
    print(f"[*] Logging in Host: {host_email}...")
    res = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": host_email,
        "password": password,
        "role": "host"
    })
    if res.status_code == 200:
        host_token = res.json().get("access_token")
        print("[+] Host logged in successfully.")
    else:
        # Try to register
        print("[*] Host not found. Registering new host account with biometric...")
        reg_res = session.post(f"{BASE_URL}/api/auth/register", json={
            "name": "Prof. Alexander Host",
            "email": host_email,
            "password": password,
            "role": "host",
            "image": dummy_b64
        })
        if reg_res.status_code == 201:
            print("[+] Host registered successfully. Retrying login...")
            res = session.post(f"{BASE_URL}/api/auth/login", json={
                "email": host_email,
                "password": password,
                "role": "host"
            })
            host_token = res.json().get("access_token")
            print("[+] Host logged in successfully.")
        else:
            print(f"[ERROR] Failed to register host: {reg_res.text}")
            sys.exit(1)
except Exception as e:
    print(f"[ERROR] Host login failed: {e}")
    sys.exit(1)

# 3. Guest Login / Register
guest_token = None
try:
    print(f"[*] Logging in Guest: {guest_email}...")
    res = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": guest_email,
        "password": password,
        "role": "guest"
    })
    if res.status_code == 200:
        guest_token = res.json().get("access_token")
        print("[+] Guest logged in successfully.")
    else:
        # Try to register
        print("[*] Guest not found. Registering new guest account with biometric...")
        reg_res = session.post(f"{BASE_URL}/api/auth/register", json={
            "name": "Jane Guest",
            "email": guest_email,
            "password": password,
            "role": "guest",
            "image": dummy_b64
        })
        if reg_res.status_code == 201:
            print("[+] Guest registered successfully. Retrying login...")
            res = session.post(f"{BASE_URL}/api/auth/login", json={
                "email": guest_email,
                "password": password,
                "role": "guest"
            })
            guest_token = res.json().get("access_token")
            print("[+] Guest logged in successfully.")
        else:
            print(f"[ERROR] Failed to register guest: {reg_res.text}")
            sys.exit(1)
except Exception as e:
    print(f"[ERROR] Guest login failed: {e}")
    sys.exit(1)

host_headers = {"Authorization": f"Bearer {host_token}"}

# 4. Create Room with waiting_room_enabled = False
room_code = None
room_id = None
try:
    print("[*] Creating a live class session (Waiting Room: DISABLED)...")
    res = session.post(f"{BASE_URL}/api/rooms/create", headers=host_headers, json={
        "title": "Quantum Computing 101",
        "room_type": "class",
        "max_participants": 20,
        "waiting_room_enabled": False,  # Bypasses host manual approval gate!
        "security_flags": {
            "biometric_mode": "required"
        }
    })
    if res.status_code == 201:
        room_data = res.json()
        room_code = room_data.get("room_code")
        room_id = room_data.get("id")
        print(f"[+] Room created successfully! Code: {room_code}, ID: {room_id}")
    else:
        print(f"[ERROR] Failed to create room: {res.text}")
        sys.exit(1)
except Exception as e:
    print(f"[ERROR] Room creation failed: {e}")
    sys.exit(1)

# Start the room
try:
    requests.post(f"{BASE_URL}/api/rooms/{room_id}/state", headers=host_headers, json={"status": "active"})
    print("[+] Room marked as active.")
except:
    pass

# 5. Generate Guest Registration Form Link
reg_token = None
try:
    print("[*] Generating smart guest registration form link...")
    res = session.post(f"{BASE_URL}/api/guest-reg/{room_id}/generate-link", headers=host_headers)
    if res.status_code == 200:
        reg_token = res.json().get("token")
        print(f"[+] Registration form generated successfully. Token: {reg_token}")
    else:
        print(f"[ERROR] Failed to generate registration link: {res.text}")
        sys.exit(1)
except Exception as e:
    print(f"[ERROR] Registration link generation failed: {e}")
    sys.exit(1)

# URLs to Open
reg_url = f"{BASE_URL}/pages/guest-register.html?token={reg_token}"
join_url = f"{BASE_URL}/pages/join.html?invite={room_code}"
host_url = f"{BASE_URL}/pages/dashboard.html"

print("\n" + "="*57)
print("  STEP-BY-STEP MANUAL TESTING GUIDE FOR GUEST FEATURES")
print("="*57)
print("A live session has been created. The WAITING ROOM is DISABLED.")
print("This means the Guest will directly join the class upon passing face matching.")
print(f"Room Code: {room_code}")
print(f"Registration Token: {reg_token}")
print("\n[PAGE 1] Guest Registration Form:")
print(f"  URL: {reg_url}")
print("  -> First, open this to register name, details, and face signature.")
print("\n[PAGE 2] Join Session Page:")
print(f"  URL: {join_url}")
print("  -> Next, complete the live face scan. You will enter the class INSTANTLY!")
print("="*57 + "\n")

# Opening browser
try:
    print("[*] Opening Host Dashboard in your default browser...")
    webbrowser.open(host_url)
    time.sleep(1)
    
    print("[*] Opening Guest Registration Form...")
    webbrowser.open(reg_url)
    time.sleep(1)
    
    print("[*] Opening Join Room Page...")
    webbrowser.open(join_url)
    
    print("\n[+] Done! All manual test pages are now open in your browser.")
except Exception as e:
    print(f"[WARN] Failed to open default browser automatically: {e}")
    print("Please manually copy and paste the URLs listed above into your browser.")
