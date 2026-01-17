import smtplib
from email.mime.text import MIMEText
from datetime import datetime

class EmailService:
    def __init__(self, user, password):
        self.user = user
        self.password = password
    
    def send_report(self, to_email, analysis_data, camera_url):
        """Send HTML formatted crowd report"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status_color = 'red' if analysis_data['status'] == 'HIGH CROWD' else 'green'
        
        html_body = f"""
        <div style='font-family: Arial; max-width: 600px; margin: 0 auto; padding: 20px;'>
            <h2 style='color: {status_color}; text-align: center;'>🚨 Crowd Analysis Report</h2>
            <div style='background: #f8f9fa; padding: 25px; border-radius: 12px; border-left: 5px solid {status_color};'>
                <p><strong>📅 Timestamp:</strong> {timestamp}</p>
                <p><strong>👥 People Count:</strong> <span style='font-size: 1.4em;'>{analysis_data['count']}</span></p>
                <p><strong>📊 Density:</strong> <span style='color: {status_color}; font-size: 1.4em; font-weight: bold;'>{analysis_data['density']}%</span></p>
                <p><strong>🆓 Free Space:</strong> {analysis_data['free_space']}%</p>
                <p><strong>⚠️ Status:</strong> <span style='color: {status_color}; font-size: 1.2em; font-weight: bold;'>{analysis_data['status']}</span></p>
                <hr>
                <p><strong>📹 Camera URL:</strong><br><code>{camera_url}</code></p>
            </div>
            <p style='text-align: center; color: #666; margin-top: 20px;'>Crowd Management System</p>
        </div>
        """
        
        msg = MIMEText(html_body, 'html')
        msg['Subject'] = f'🚨 Crowd Report - {analysis_data["status"]} ({analysis_data["density"]}% density)'
        msg['From'] = self.user
        msg['To'] = to_email
        
        try:
            with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"Email error: {e}")
            return False
