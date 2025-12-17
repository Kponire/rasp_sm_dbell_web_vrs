import json
import uuid
from flask import Blueprint, Response, request, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from config import Config
import requests
from datetime import datetime
import maileroo
import os
from models import Device, User, db, Notification
try:
    from notifications_service import send_email as sg_send_email, send_whatsapp
except Exception:
    sg_send_email = None
    send_whatsapp = None

notifications_bp = Blueprint('notifications', __name__)

# Initialize Supabase client
# supabase: Client = create_client(
#     Config.SUPABASE_URL,
#     Config.SUPABASE_KEY
# )

def extract_name_from_image_url(image_url: str) -> str:
    """
    Extract person name from Supabase image URL
    Expected format: https://supabase.com/storage/v1/object/public/{bucket}/{user_id}/{person_name}/{filename}
    """
    try:
        # Extract the path after the bucket name
        parts = image_url.split('/')
        bucket_index = parts.index('public') + 1 if 'public' in parts else -1
        
        if bucket_index > 0 and bucket_index + 1 < len(parts):
            # The structure is: bucket/user_id/person_name/filename
            person_name = parts[bucket_index + 2]  # Skip bucket and user_id
            return person_name.replace('_', ' ').title()
    except:
        pass
    return "Unknown"

def send_email_notification(user_email: str, device_name: str, person_name: str, 
                           status: str, image_url: str, confidence: float = None):
    """Send email notification with descriptive message"""
    if not Config.EMAIL_ENABLED:
        print("[INFO] Email notifications disabled")
        return False
    
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    if status == "recognized":
        subject = f"✅ Door Access: {person_name} Recognized"
        body = f"""
        <h2>Face Recognized at Your Door</h2>
        <p><strong>Device:</strong> {device_name}</p>
        <p><strong>Person:</strong> {person_name}</p>
        <p><strong>Time:</strong> {timestamp}</p>
        <p><strong>Status:</strong> Access Granted</p>
        <p><strong>Confidence:</strong> {confidence:.1%} if confidence else 'N/A'</p>
        <br>
        <p>This person was recognized and granted access to your property.</p>
        <p><img src="{image_url}" alt="Captured Image" style="max-width: 400px; border-radius: 8px;"></p>
        """
    else:
        subject = f"⚠️ Security Alert: Unknown Person Detected"
        body = f"""
        <h2>Unknown Person Detected at Your Door</h2>
        <p><strong>Device:</strong> {device_name}</p>
        <p><strong>Status:</strong> Access Denied</p>
        <p><strong>Time:</strong> {timestamp}</p>
        <br>
        <p>An unrecognized person was detected at your door. Please review the image below.</p>
        <p><img src="{image_url}" alt="Captured Image" style="max-width: 400px; border-radius: 8px;"></p>
        """
    
    # Try SendGrid first
    if os.getenv('SENDGRID_API_KEY') and sg_send_email:
        try:
            sg_send_email(user_email, subject, body)
            return True
        except Exception as e:
            print(f"[WARN] SendGrid send failed: {e}")
    
    # Fallback to Maileroo
    try:
        client = maileroo.Maileroo(api_key=Config.MAILERO_API_KEY)
        email = {
            'from': Config.MAILERO_SENDER,
            'to': user_email,
            'subject': subject,
            'html': body
        }
        client.send_email(email)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False

def send_whatsapp_notification(phone_number: str, device_name: str, person_name: str, 
                              status: str, image_url: str, confidence: float = None):
    """Send WhatsApp notification with descriptive message"""
    if not Config.WHATSAPP_ENABLED:
        print("[INFO] WhatsApp notifications disabled")
        return False
    
    if not phone_number:
        print("[WARN] No phone number provided for WhatsApp notification")
        return False
    
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    if status == "recognized":
        message = f"""
✅ *Door Access Notification*
        
*Person:* {person_name}
*Device:* {device_name}
*Time:* {timestamp}
*Status:* Access Granted
*Confidence:* {confidence:.1%} if confidence else 'N/A'
        
This person was recognized and granted access to your property.
        
View image: {image_url}
        """
    else:
        message = f"""
⚠️ *Security Alert - Unknown Person*
        
*Device:* {device_name}
*Time:* {timestamp}
*Status:* Access Denied - Unknown Face
        
An unrecognized person was detected at your door. Please review immediately.
        
View image: {image_url}
        """
    
    try:
        # Clean phone number (remove any non-digit characters except +)
        clean_phone = ''.join(c for c in phone_number if c.isdigit() or c == '+')
        if not clean_phone.startswith('+'):
            clean_phone = f"+{clean_phone}"
        
        send_whatsapp(clean_phone, message.strip())
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send WhatsApp: {e}")
        return False

def send_email(to_email, subject, body):
    if not Config.EMAIL_ENABLED:
        print("[INFO] Email notifications disabled")
        return False
    # Prefer SendGrid if configured
    if os.getenv('SENDGRID_API_KEY') and sg_send_email:
        try:
            sg_send_email(to_email, subject, body)
            return True
        except Exception as e:
            print(f"[WARN] SendGrid send failed: {e}")
    try:
        client = maileroo.Maileroo(api_key=Config.MAILERO_API_KEY)
        email = {
            'from': Config.MAILERO_SENDER,
            'to': to_email,
            'subject': subject,
            'text': body
        }
        client.send_email(email)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False

def send_push_notification(message):
    if not Config.PUSH_ENABLED:
        print("[INFO] Push notifications disabled")
        return False
    try:
        response = requests.post(Config.PUSH_WEBHOOK_URL, json={'message': message})
        return response.status_code == 200
    except Exception as e:
        print(f"[ERROR] Failed to send push notification: {e}")
        return False

def initiate_call():
    if not Config.CALL_ENABLED:
        print("[INFO] Call notifications disabled")
        return False, {'error': 'Calls disabled'}
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
        'apiKey': Config.AT_API_KEY,
    }
    payload = {
        'username': Config.AT_USERNAME,
        'to': Config.OWNER_PHONE_NUMBER,
        'from': Config.AT_VIRTUAL_NUMBER,
        'callBackUrl': f"{Config.BASE_URL}/api/notifications/at_voice_callback",
    }
    try:
        # If Twilio WhatsApp is configured, send a WhatsApp message instead of voice call
        if os.getenv('TWILIO_ACCOUNT_SID') and send_whatsapp:
            try:
                send_whatsapp(Config.OWNER_PHONE_NUMBER, f"Unknown face detected at your door at {datetime.utcnow().isoformat()}")
                return True, {'method': 'whatsapp'}
            except Exception as e:
                print(f"[WARN] Twilio WhatsApp failed: {e}")
        response = requests.post("https://voice.africastalking.com/call", headers=headers, data=payload)
        response.raise_for_status()
        return True, response.json()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to initiate call: {e}")
        return False, {'error': str(e)}

@notifications_bp.route('/device', methods=['POST'])
def receive_device_notification():
    """Receive notification from Raspberry Pi device"""
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Extract data from request
    device_id = data.get('deviceId')
    status = data.get('status')  # 'recognized' or 'unrecognized'
    image_url = data.get('imageUrl')
    confidence = data.get('confidence')
    
    if not all([device_id, status, image_url]):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        device_id = uuid.UUID(device_id)
    except ValueError:
        return jsonify({"error": "Invalid device ID format"}), 400
    
    # Get device and owner information
    device = Device.query.filter_by(id=device_id).first()
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    
    user = User.query.get(device.owner_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Extract person name from image URL if recognized
    person_name = "Unknown"
    if status == "recognized":
        person_name = extract_name_from_image_url(image_url)
    
    # Create notification record
    notification = Notification(
        id=uuid.uuid4(),
        user_id=user.id,
        person_name=person_name,
        status=status,
        confidence=confidence,
        image_url=image_url,
        timestamp=datetime.utcnow()
    )
    
    db.session.add(notification)
    db.session.commit()
    
    # Send notifications
    email_sent = send_email_notification(
        user.email, 
        device.name, 
        person_name, 
        status, 
        image_url, 
        confidence
    )
    
    whatsapp_sent = send_whatsapp_notification(
        user.phone,
        device.name,
        person_name,
        status,
        image_url,
        confidence
    )
    
    return jsonify({
        'message': 'Notification received and processed',
        'notification_id': str(notification.id),
        'email_sent': email_sent,
        'whatsapp_sent': whatsapp_sent,
        'person_name': person_name
    }), 200

@notifications_bp.route('', methods=['GET'])
@jwt_required()
def get_notifications():
    """Get all notifications for the current user"""
    user_identity_raw = get_jwt_identity()
    user_identity = json.loads(user_identity_raw)
    user_id = user_identity['id']

    try:
        user_id = uuid.UUID(user_id)
    except ValueError:
        return jsonify({"error": "Invalid user ID format"}), 400
    
    notifications = Notification.query.filter_by(user_id=user_id).order_by(Notification.timestamp.desc()).all()
    
    return jsonify([{
        'id': str(n.id),
        'personName': n.person_name,
        'timestamp': n.timestamp.isoformat() if n.timestamp else None,
        'status': n.status,
        'imageUrl': n.image_url or 'https://placehold.co/400',
        'confidence': n.confidence * 100 if n.confidence else None,
        'device': n.device.name if n.device else 'Unknown Device'
    } for n in notifications]), 200

# Add this route to your existing notification.py

@notifications_bp.route('/call', methods=['POST'])
def initiate_doorbell_call():
    """Initiate a call when doorbell button is pressed"""
    data = request.get_json()
    device_id = data.get('deviceId')
    
    if not device_id:
        return jsonify({'error': 'deviceId required'}), 400

    try:
        device_id = uuid.UUID(device_id)
    except ValueError:
        return jsonify({"error": "Invalid device ID format"}), 400
    
    # Get device and owner information
    from models import Device, User
    device = Device.query.filter_by(id=device_id).first()
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    
    user = User.query.get(device.owner_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Check if user has phone number
    if not user.phone:
        return jsonify({'error': 'User phone number not available'}), 400
    
    # Initiate call using Africa's Talking
    try:
        import requests
        
        # Africa's Talking API credentials
        username = Config.AT_USERNAME
        api_key = Config.AT_API_KEY
        virtual_number = Config.AT_VIRTUAL_NUMBER
        print(api_key)
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'apiKey': api_key,
        }
        
        payload = {
            'username': username,
            'to': user.phone,
            'from': virtual_number,
            'callBackUrl': f"{Config.BASE_URL}/api/notifications/at_voice_callback",
        }
        
        response = requests.post("https://voice.africastalking.com/call", 
                                headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        
        call_data = response.json()
        
        # Log the call initiation
        print(f"[INFO] Call initiated for device {device_id} to {user.phone}")
        
        return jsonify({
            'message': 'Call initiated successfully',
            'call_data': call_data,
            'to': user.phone,
            'device_name': device.name
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Failed to initiate call: {e}")
        return jsonify({'error': 'Failed to initiate call', 'details': str(e)}), 500

# Update the AT voice callback to handle doorbell calls
@notifications_bp.route('/at_voice_callback', methods=['POST'])
def at_main_voice_callback():
    call_status = request.form.get('status')
    
    if call_status == 'Active':
        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="en-US-Wavenet-F" speakingRate="1.1">
        Hello, this is your smart doorbell system. Someone is at your door. 
        Please check your mobile app for live video feed and to unlock the door if needed.
    </Say>
    <Pause length="2"/>
    <Say voice="en-US-Wavenet-F">
        Press 1 to speak through the doorbell. Press 2 to unlock the door. 
        Press 3 to end this call.
    </Say>
    <GetDigits timeout="30" finishOnKey="#" callbackUrl="{callback_url}/handle_digits">
        <Say>Please enter your choice.</Say>
    </GetDigits>
</Response>""".format(callback_url=f"{Config.BASE_URL}/api/notifications")
    
    elif call_status == 'Completed' or call_status == 'Busy' or call_status == 'NoAnswer':
        xml_response = """<?xml version="1.0" encoding="UTF-8"?><Response/>"""
    else:
        xml_response = """<?xml version="1.0" encoding="UTF-8"?><Response/>"""
    
    return Response(xml_response, mimetype='text/xml')

@notifications_bp.route('/handle_digits', methods=['POST'])
def handle_digits():
    """Handle DTMF digits from the call"""
    digits = request.form.get('digits')
    call_session_id = request.form.get('sessionId')
    
    if digits == '1':
        # Enable two-way audio (requires additional setup)
        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Two-way audio enabled. You can now speak to the person at the door.</Say>
    <Record maxLength="30" finishOnKey="#" playBeep="true"/>
    <Say>Recording ended. The call will now end.</Say>
    <Reject/>
</Response>"""
    
    elif digits == '2':
        # Unlock the door
        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Unlocking the door. Please check your app for confirmation.</Say>
    <Dial phoneNumbers="+2547XXXXXXXX" maxDuration="30"/> <!-- You can add a webhook here to trigger door unlock -->
    <Say>Door unlocked. The call will now end.</Say>
    <Reject/>
</Response>"""
    
    elif digits == '3':
        # End call
        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Ending the call. Goodbye.</Say>
    <Reject/>
</Response>"""
    
    else:
        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Invalid option. Goodbye.</Say>
    <Reject/>
</Response>"""
    
    return Response(xml_response, mimetype='text/xml')    

@notifications_bp.route('/settings', methods=['GET'])
@jwt_required()
def get_notification_settings():
    return jsonify({
        'email_enabled': Config.EMAIL_ENABLED,
        'push_enabled': Config.PUSH_ENABLED,
        'call_enabled': Config.CALL_ENABLED
    }), 200

@notifications_bp.route('/settings', methods=['PUT'])
@jwt_required()
def update_notification_settings():
    data = request.get_json()
    Config.EMAIL_ENABLED = data.get('email_enabled', Config.EMAIL_ENABLED)
    Config.PUSH_ENABLED = data.get('push_enabled', Config.PUSH_ENABLED)
    Config.CALL_ENABLED = data.get('call_enabled', Config.CALL_ENABLED)
    return jsonify({'message': 'Notification settings updated'}), 200

@notifications_bp.route('/at_old_voice_callback', methods=['POST'])
def at_voice_callback():
    call_status = request.form.get('status')
    xml_response = """<?xml version="1.0" encoding="UTF-8"?><Response/>"""
    
    if call_status == 'Active':
        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>An unknown face has been detected at your doorbell. The call will now end for security purposes.</Say>
    <Reject/>
</Response>"""
    return Response(xml_response, mimetype='text/xml')