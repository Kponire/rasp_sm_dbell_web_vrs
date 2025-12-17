from flask_socketio import Namespace, emit, disconnect
import cv2
import numpy as np
from datetime import datetime
import threading

device_frames = {}
device_frames_lock = threading.Lock()

class VideoStreamNamespace(Namespace):

    def on_connect(self):
        print("[WS] Client connected")

    def on_disconnect(self):
        print("[WS] Client disconnected")

    def on_register_device(self, data):
        device_id = data.get("deviceId")
        if not device_id:
            disconnect()
            return

        with device_frames_lock:
            device_frames[device_id] = {
                "frame": None,
                "timestamp": None
            }

        self.device_id = device_id
        print(f"[WS] Device registered: {device_id}")

    def on_video_frame(self, data):
        """
        data = {
            deviceId: str,
            frame: bytes (JPEG)
        }
        """
        device_id = data.get("deviceId")
        frame_bytes = data.get("frame")

        if not device_id or not frame_bytes:
            return

        with device_frames_lock:
            device_frames[device_id] = {
                "frame": frame_bytes,
                "timestamp": datetime.utcnow()
            }

        # Emit to frontend viewers
        emit(
            "video_frame",
            {
                "deviceId": device_id,
                "frame": frame_bytes
            },
            broadcast=True
        )
