import os
import io
import uuid
from typing import List, Dict, Optional
from supabase import create_client, Client
from config import Config
import mimetypes

def get_client() -> Client:
    """Get Supabase client instance"""
    if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
        raise RuntimeError('SUPABASE_URL and SUPABASE_KEY must be set in environment')
    return create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

def upload_to_supabase(bucket: str, path: str, file_bytes: bytes, content_type: str = None) -> Dict:
    sup = get_client()

    if not content_type:
        content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'

    try:
        res = sup.storage.from_(bucket).upload(
            path,
            file_bytes,
            {"content-type": content_type}
        )

    except Exception as e:
        raise RuntimeError(f"Storage upload failed: {str(e)}")


    public_url = sup.storage.from_(bucket).get_public_url(path)

    return {
        "success": True,
        "path": path,
        "public_url": public_url,
        "bucket": bucket
    }

def list_files_in_bucket(bucket: str, prefix: str = '') -> List[Dict]:
    """List files in a bucket with optional prefix"""
    sup = get_client()
    try:
        list_res = sup.storage.from_(bucket).list(path=prefix)
        return list_res
    except Exception as e:
        print(f"[ERROR] Failed to list files: {e}")
        return []

def get_public_url(bucket: str, path: str) -> str:
    """Get public URL for a file"""
    sup = get_client()
    return sup.storage.from_(bucket).get_public_url(path)

def delete_file(bucket: str, path: str) -> bool:
    """Delete file from Supabase storage"""
    sup = get_client()
    try:
        res = sup.storage.from_(bucket).remove([path])
        return True
    except Exception as e:
        print(f"[ERROR] Failed to delete file: {e}")
        return False

# Image-specific functions
def upload_watchlist_image(user_id: str, device_id: str, watchlist_id: str, 
                          watchlist_name: str, file_bytes: bytes, 
                          filename: str, content_type: str = 'image/jpeg') -> Dict:
    """Upload watchlist image to Supabase images bucket"""
    # Sanitize watchlist name for filename
    safe_watchlist_name = "".join(c for c in watchlist_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_watchlist_name = safe_watchlist_name.replace(' ', '_')
    
    # Generate unique filename
    file_ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
    unique_filename = f"{watchlist_id}_{safe_watchlist_name}_{uuid.uuid4().hex[:8]}.{file_ext}"
    
    # Path format: deviceID/watchlistId_watchlistName.ext
    path = f"{device_id}/{unique_filename}"
    
    return upload_to_supabase('images', path, file_bytes, content_type)

def upload_captured_face(device_id: str, person_name: str, status: str, 
                        file_bytes: bytes, filename: str = None) -> Dict:
    """Upload captured face to Supabase captured-faces bucket"""
    # Generate filename
    timestamp = uuid.uuid4().hex[:8]
    safe_person_name = "".join(c for c in person_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_person_name = safe_person_name.replace(' ', '_')
    
    if not filename:
        filename = f"{safe_person_name}_{status}_{timestamp}.jpg"
    
    # Path format: deviceID/timestamp_person_status.ext
    path = f"{device_id}/{filename}"
    
    return upload_to_supabase('captured-faces', path, file_bytes, 'image/jpeg')

def get_watchlist_images_for_device(device_id: str) -> List[Dict]:
    """Get all watchlist images for a specific device"""
    sup = get_client()
    try:
        # List all files in the device's folder
        files = sup.storage.from_('images').list(path=device_id)
        
        images = []
        for file_info in files:
            if file_info.get('name'):
                # Get public URL
                path = file_info['name']
                try:
                    public_url = sup.storage.from_('images').get_public_url(path)
                    images.append({
                        'path': path,
                        'url': public_url,
                        'filename': path.split('/')[-1] if '/' in path else path,
                        'size': file_info.get('metadata', {}).get('size'),
                        'created_at': file_info.get('created_at')
                    })
                except Exception as e:
                    print(f"[WARN] Failed to get URL for {path}: {e}")
        
        return images
    except Exception as e:
        print(f"[ERROR] Failed to get watchlist images: {e}")
        return []

def delete_watchlist_image(device_id: str, image_path: str) -> bool:
    """Delete watchlist image from Supabase"""
    # Ensure path includes device_id
    if not image_path.startswith(device_id):
        image_path = f"{device_id}/{image_path}"
    
    return delete_file('images', image_path)