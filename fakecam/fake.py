import os
import cv2
import numpy as np
import requests
import pyfakewebcam
from signal import signal, SIGINT
from sys import exit

import threading
from bottle import route, run, template, static_file

# setup access to the *real* webcam
cap = cv2.VideoCapture('/dev/video0')
height, width = 720, 1280
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
cap.set(cv2.CAP_PROP_FPS, 30)

# In case the real webcam does not support the requested mode.
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

# The scale factor for image sent to bodypix
sf = 0.5

# setup the fake camera
fake = pyfakewebcam.FakeWebcam('/dev/video20', width, height)

# declare global variables
background = None
use_hologram = False
background_image = 'background.jpg'

def load_images():
    global background
    global background_image

    # load the virtual background
    image = cv2.imread(os.path.join('/data/images', background_image))
    image = cv2.resize(image, (width, height))

    background = image

def get_mask(frame, bodypix_url='http://127.0.0.1:9000'):
    frame = cv2.resize(frame, (0, 0), fx=sf, fy=sf)
    _, data = cv2.imencode(".png", frame)
    r = requests.post(
        url=bodypix_url,
        data=data.tobytes(),
        headers={'Content-Type': 'application/octet-stream'})
    mask = np.frombuffer(r.content, dtype=np.uint8)
    mask = mask.reshape((frame.shape[0], frame.shape[1]))
    mask = cv2.resize(mask, (0, 0), fx=1/sf, fy=1/sf,
                      interpolation=cv2.INTER_NEAREST)
    return mask

def post_process_mask(mask):
    mask = cv2.dilate(mask, np.ones((20,20), np.uint8) , iterations=1)
    mask = cv2.blur(mask.astype(float), (30,30))
    return mask

def shift_image(img, dx, dy):
    img = np.roll(img, dy, axis=0)
    img = np.roll(img, dx, axis=1)
    if dy>0:
        img[:dy, :] = 0
    elif dy<0:
        img[dy:, :] = 0
    if dx>0:
        img[:, :dx] = 0
    elif dx<0:
        img[:, dx:] = 0
    return img

def hologram_effect(img):
    # add a blue tint
    holo = cv2.applyColorMap(img, cv2.COLORMAP_WINTER)

    # add a halftone effect
    bandLength, bandGap = 2, 3
    for y in range(holo.shape[0]):
        if y % (bandLength+bandGap) < bandLength:
            holo[y,:,:] = holo[y,:,:] * np.random.uniform(0.1, 0.3)

    # add some ghosting
    holo_blur = cv2.addWeighted(holo, 0.2, shift_image(holo.copy(), 5, 5), 0.8, 0)
    holo_blur = cv2.addWeighted(holo_blur, 0.4, shift_image(holo.copy(), -5, -5), 0.6, 0)

    # combine with the original color, oversaturated
    out = cv2.addWeighted(img, 0.5, holo_blur, 0.6, 0)
    return out    

def get_frame(cap, background):
    global use_hologram

    _, frame = cap.read()
    # fetch the mask with retries (the app needs to warmup and we're lazy)
    # e v e n t u a l l y c o n s i s t e n t
    mask = None
    while mask is None:
        try:
            mask = get_mask(frame)
        except:
            print("mask request failed, retrying")

    mask = post_process_mask(mask)

    if use_hologram:
        frame = hologram_effect(frame)

    # composite the background
    for c in range(frame.shape[2]):
        frame[:,:,c] = frame[:,:,c] * mask + background[:,:,c] * (1 - mask)

    # transparent
    # frame = cv2.addWeighted(frame, 0.9, background, 0.1, 0)

    return frame

@route('/')
def index():
    images = [f for f in os.listdir('/data/images') if os.path.isfile(os.path.join('/data/images', f))]
    images = [img for img in images if img.endswith('.jpg')]

    return template('''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Fake Background</title>
    <style>
    .thumbnail {
        max-width: 128px;
        max-height: 96px;
        margin: 4px;
    }
    body {
        font: 14px sans-serif;
        background: #FFFFFF;
    }
    div {
        padding: 4px;
    }
    p {
        background: #E0F0FF;
        padding: 4px;
        border: 1px solid #202040;
    }
    </style>
</head>
<body>
    <div>
    <p>
        <input type="checkbox" id="hologram" name="hologram" value="hologram" onchange="set_hologram(this.checked);"/>
        <label for="hologram">Hologram Effect</label>
    </p>
    <p>
    % for image in images:
        <img class="thumbnail" src="/images/{{image}}" onclick="set_background('{{image}}');" />
    % end
    </p>
    </div>
    <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.4.1/jquery.min.js"></script>
    <script type="text/javascript">
        function set_hologram(checked) {
            var state = checked ? 'on' : 'off';
            $.ajax({type: 'POST', url: '/hologram/' + state});
        }
        function set_background(name) {
            $.ajax({type: 'POST', url: '/background/' + name});
        }
    </script>
</body>
</html>
    ''', images=images)

@route('/images/<filename:path>')
def send_static(filename):
    return static_file(filename, root='/data/images')

@route('/hologram/<state>', method='POST')
def do_hologram(state):
    global use_hologram
    use_hologram = state == 'on'
    return 'hologram {}'.format(state)

@route('/background/<filename>', method='POST')
def do_background(filename):
    global background_image
    background_image = filename
    load_images()
    return 'change background to {}'.format(background_image)

def webui():
    run(host='localhost', port=8077)

if __name__ == '__main__':
    ui = threading.Thread(target=webui)
    ui.start()

    load_images()

    print('Running...')
    print('Please press CTRL-C to exit.')
    # frames forever
    while True:
        frame = get_frame(cap, background)
        # fake webcam expects RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        fake.schedule_frame(frame)
