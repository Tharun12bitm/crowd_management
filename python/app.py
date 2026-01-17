from flask import Flask, request, jsonify, render_template, send_file
from config import Config
from utils.crowd_analyzer import CrowdAnalyzer
from utils.email_service import EmailService
import requests
import os
import io
import base64
import cv2
import numpy as np
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import time

app = Flask(__name__)
app.config.from_object(Config)

analyzer = CrowdAnalyzer()
email_service = None
if app.config['EMAIL_USER'] and app.config['EMAIL_PASS']:
    email_service = EmailService(
        app.config['EMAIL_USER'], 
        app.config['EMAIL_PASS']
    )
else:
    print("⚠️  Email credentials not configured. Email reports will be disabled.")

def analyze_crowd_contours(frame):
    """Simple estimation of crowd density based on motion and contours."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (15, 15), 0)
    _, thresh = cv2.threshold(blurred, 50, 255, cv2.THRESH_BINARY)
    
    # Find contours (moving objects / people-like blobs)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    crowd_count = len(contours)
    
    # Estimate density and free space (rough approximation)
    total_area = frame.shape[0] * frame.shape[1]
    crowd_area = sum(cv2.contourArea(c) for c in contours)
    density = (crowd_area / total_area) * 100
    free_space = 100 - density
    
    return crowd_count, density, free_space

def send_email_report(receiver_email, report):
    """Send the crowd analysis report to the given email address."""
    sender_email = app.config.get('EMAIL_USER', '')
    sender_password = app.config.get('EMAIL_PASS', '')
    
    if not sender_email or not sender_password:
        print("⚠️  Email credentials not configured")
        return False
    
    print(f"📧 Attempting to send email from {sender_email} to {receiver_email}...")
    
    msg = MIMEText(report)
    msg["Subject"] = "Crowd Monitoring Report"
    msg["From"] = sender_email
    msg["To"] = receiver_email
    
    try:
        print("🔌 Connecting to Gmail SMTP server...")
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            print("🔐 Starting TLS...")
            server.starttls()
            print("🔑 Logging in...")
            server.login(sender_email, sender_password)
            print("📤 Sending email...")
            server.send_message(msg)
            print("✅ Email sent successfully!")
            print(f"📬 Check {receiver_email} inbox or spam folder!")
            return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication Error: {e}")
        print("⚠️  Check:")
        print("   1. App Password is correct")
        print("   2. 2-Step Verification is enabled")
        print("   3. Using App Password, not regular password")
        return False
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

from flask import Response

@app.route('/video')
def video():
    """Proxy MJPEG stream from camera to client"""
    camera_url = request.args.get('url')
    if not camera_url:
        return jsonify({'error': 'Camera URL required'}), 400

    try:
        # Open the upstream stream and keep it open while we yield chunks
        r = requests.get(camera_url, stream=True, timeout=30)
        r.raise_for_status()

        content_type = r.headers.get('content-type', 'multipart/x-mixed-replace; boundary=frame')

        def generate():
            try:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        yield chunk
            except Exception as e:
                print(f"Stream error while yielding: {e}")

        return Response(generate(), content_type=content_type)
    except Exception as e:
        print(f"Stream setup error: {e}")
        return jsonify({'error': 'Failed to open stream'}), 400


@app.route('/snapshot')
def snapshot():
    """Fetch a single snapshot image from the camera and return raw image bytes"""
    camera_url = request.args.get('url')
    if not camera_url:
        return jsonify({'error': 'Camera URL required'}), 400
    try:
        r = requests.get(camera_url, timeout=10)
        r.raise_for_status()
        content_type = r.headers.get('content-type', 'image/jpeg')
        return Response(r.content, mimetype=content_type)
    except Exception as e:
        print(f"Snapshot error: {e}")
        return jsonify({'error': 'Failed to fetch snapshot'}), 400


@app.route('/probe')
def probe():
    """Probe camera URL to determine content type"""
    camera_url = request.args.get('url')
    if not camera_url:
        return jsonify({'error': 'Camera URL required'}), 400
    try:
        # Try the provided URL and a small set of common MJPEG endpoints
        candidates = [camera_url]
        # common variants for IP Webcam / MJPEG-capable devices
        suffixes = ['/video', '/mjpeg', '/stream', '/video.cgi', '/axis-cgi/mjpg/video.cgi', '/videostream.cgi']
        for s in suffixes:
            if camera_url.endswith('/'):
                candidates.append(camera_url.rstrip('/') + s)
            else:
                candidates.append(camera_url + s)

        tried = []
        for url in candidates:
            try:
                r = requests.get(url, stream=True, timeout=6)
                r.raise_for_status()
                content_type = r.headers.get('content-type', '')
                tried.append({'url': url, 'content_type': content_type, 'status': r.status_code})
                is_mjpeg = 'multipart' in content_type
                is_image = content_type.startswith('image')
                if is_mjpeg or is_image:
                    return jsonify({
                        'original_url': camera_url,
                        'resolved_url': url,
                        'content_type': content_type,
                        'is_mjpeg': is_mjpeg,
                        'is_image': is_image,
                        'tried': tried
                    })
            except Exception as e:
                tried.append({'url': url, 'error': str(e)})

        return jsonify({'error': 'Failed to probe camera URL', 'tried': tried}), 400
    except Exception as e:
        print(f"Probe error: {e}")
        return jsonify({'error': 'Failed to probe camera URL', 'exception': str(e)}), 400

@app.route('/api/analyze', methods=['POST'])
def analyze_crowd():
    """Simplified analysis endpoint (no email required)."""
    data = request.get_json() or {}
    camera_url = data.get('camera_url')

    if not camera_url:
        return jsonify({'error': 'Missing camera URL'}), 400

    try:
        # Fetch image from camera
        print(f"📷 Fetching from: {camera_url}")
        response = requests.get(camera_url, timeout=15, stream=True)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")

        # Handle MJPEG streams: extract first frame
        if "multipart" in content_type:
            boundary = content_type.split("boundary=")[-1]
            frame_data = b''
            in_frame = False
            for chunk in response.iter_content(chunk_size=1024):
                if boundary.encode() in chunk:
                    in_frame = not in_frame
                    if not in_frame and frame_data:
                        break
                if in_frame:
                    frame_data += chunk
            nparr = np.frombuffer(frame_data, np.uint8)
        else:
            nparr = np.frombuffer(response.content, np.uint8)

        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            error_msg = f'Cannot decode image from camera. Content type: {content_type}, Size: {len(response.content)} bytes'
            print(f"❌ {error_msg}")
            return jsonify({'error': error_msg}), 400

        # Use the simple contour-based analyzer for a minimal system
        crowd_count, density, free_space = analyze_crowd_contours(frame)
        status = 'HIGH CROWD' if density > 50 else 'NORMAL'

        analysis = {
            'count': int(crowd_count),
            'density': round(float(density), 2),
            'free_space': round(float(free_space), 2),
            'status': status
        }

        # Convert frame to base64 for display
        _, buffer = cv2.imencode('.jpg', frame)
        frame_base64 = base64.b64encode(buffer).decode('utf-8')

        message = f"{('🚨' if status == 'HIGH CROWD' else '✅')} {analysis['count']} people | {analysis['density']}% density | {analysis['status']}"

        return jsonify({
            'success': True,
            'data': analysis,
            'message': message,
            'frame': f'data:image/jpeg;base64,{frame_base64}'
        })

    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout connecting to {camera_url}")
        return jsonify({'error': 'Camera timeout - check connection'}), 408
    except requests.exceptions.ConnectionError as e:
        print(f"🔌 Connection error: {e}")
        return jsonify({'error': 'Cannot connect to camera URL'}), 400
    except Exception as e:
        print(f"💥 Analysis failed: {str(e)}")
        return jsonify({'error': f'Analysis failed: {str(e)}'}, 500)

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'server': 'Crowd Management System'})

if __name__ == '__main__':
    print("🚀 Starting Crowd Management System...")
    print(f"📱 Frontend: http://{app.config['HOST']}:{app.config['PORT']}")
    print("✅ Backend APIs ready!")
    app.run(host=app.config['HOST'], port=app.config['PORT'], debug=True)