SO I will need to make this backend appropriate because I am building a smart doorbell with facial recognition. SO I will be have two separate flask backend server, the first is the one that will be hosted or deployed online that communicates with the fronted interface. The second is the backend server that will be running on the raspberrypi microprocessor that now fetches all the images of the user from the cloud and does facial recognition using DeepFace and the webcam.

The web_backend folder and the raspberry_pi backend folder.
For the web_backend, I was using mysql before but now I want to move to supabase (postgres) and the images wil be uploaded on supabase also. For the notification, I want to use email (SendGrid) and twillio whatsapp api.
For the raspberry_pi backend, it connect's to the web_backend route where it pulls the user images from supabase and does the deepface validation and also send livestream to the web_backend route which connects to the frontend or (I kind of don't know how it will play out yet) and then an lcd texts for display on the smart doorbell device that tells user every action going on, then a relay to open the door is recognized and also a relay to close the door if not recognized or the frontend button tells it to do and a button to make the call. I also have mantine buttons on the frontend to close the door too. I am using a raspberrypi webcam and also a buzzer too. help me write those codes for me

flask-socketio
python-socketio
