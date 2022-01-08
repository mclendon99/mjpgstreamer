#! /usr/bin/python3
""" mjpgstreamer.py
    Stream mjpg to a client, e.g. github.com://mclendon99/gps_tracker
    Based on github.com://soyersoyer/fmp4streamer

    Todo:
    - handle multiple html connections to any camera
    - support multiple cameras

"""

__author__ = "McLendon"
__license__ = """
"""

import os,logging, getopt, time, errno, sys, timeit, socketserver,configparser

from http.server import BaseHTTPRequestHandler,HTTPServer
from threading import Thread
from v4l2py import Device



import socket
def get_my_ip_address():
    ss = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ss.settimeout(0)
    try:
        ss.connect(('10.11.255.255',1))
        ip = ss.getsockname()[0]
    except Exception:
        ip = '127.0.1.1'
    finally:
        ss.close()
    return ip

myIPAddress = get_my_ip_address()
myHostName = str(socket.gethostname())

class HTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def start(self):
      try:
          self.serve_forever()
      except KeyboardInterrupt:
          pass
      finally:
          self.server_close()

class CameraThread(Thread):
    def __init__(self, camera):
        super(CameraThread, self).__init__()
        self.camera = camera
    def start(self):
        self.camera.video_capture.start()
    def stop(self):
        self.camera.video_capture.stop()

class RequestHandler(BaseHTTPRequestHandler):
    def process_frames(self):
        frame_budget = 1000 / fps
        # If the camera is stopped, this will stop since there are no more frames
        for frame in camera:
            try:
                 start = timeit.default_timer()
                 self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
                 stop = timeit.default_timer()
                 delay = (stop - start) * 1000  # Delay in ms
                 if (delay > 0):
                    time.sleep(delay/1000) # Wait until next frame ready
            except Exception as e:
                 print(f'{time.asctime()}Removed streaming client {self.client_address} {str(e)}')
                 try:
                    self.send_error(404)
                    self.end_headers()
                 except Exception as e:
                    print(f'{time.asctime()}Send 404 failed {self.client_address} {str(e)}')

    def do_GET(self):
        print(f'{time.asctime()} do_GET from {self.client_address}')
        self.send_response(200)
        self.send_header('Age','0')
        self.send_header('Expires','0')
        self.send_header('Cache-Control', 'no-cache,no-store,must-revalidate')
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.process_frames()
        print(f'{time.asctime()} do_GET - done looping for {self.client_address}')
        sys.exit(0)

class Config(configparser.ConfigParser):
    def __init__(self, configfile):
        super(Config, self).__init__({
            'width': 640,
            'height': 480,
            'fps': 30,
        })
        self.read_dict({'server': {'listen': '', 'port': 8090}})

        if len(self.read(configfile)) == 0:
            logging.warning(f'Couldn\'t read {configfile}, using default config')

        if len(self.sections()) == 1:
            self.add_section('/dev/video0')

        self.device = self.get_devices()[0]

    def get_devices(self):
        return [s for s in self.sections() if s != 'server']

    def get_device(self):
        return self.device

    def width(self):
        return int(self[self.device]['width'])

    def height(self):
        return int(self[self.device]['height'])

    def fps(self):
        return int(self[self.device]['fps'])

def usage():
    print(f'usage: python3 {sys.argv[0]} [--help] [--list-controls] [--config CONFIG]\n')
    print(f'optional arguments:')
    print(f'  -h, --help                  show this help message and exit')
    print(f'  -l, --list-controls         list the v4l2 controls and values for the camera')
    print(f'  -c CONFIG, --config CONFIG  use CONFIG as a config file, default: mp4streamer.conf')


if __name__ == '__main__':
    # Some defaults
    hostName = ''
    hostPort = 8090
    height = 480
    width = 640
    fps = 30
    list_controls = False
    configfile = "mjpgstreamer.conf"

    try:
        arguments, values = getopt.getopt(sys.argv[1:], "hlc:", ["help", "list-controls","config="])
    except getopt.error as err:
        print(err)
        usage()
        sys.exit(-1)
    
    configfile = "mp4streamer.conf"
    
    for current_argument, current_value in arguments:
        if current_argument in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif current_argument in ("-l", "--list-controls"):
            list_controls = True
        elif current_argument in ("-c", "--config"):
            configfile = current_value
    
    config = Config(configfile)
    device = config.get_device()

    print(f'{time.asctime()} Using device {device}')

    camera = Device(device)
    if list_controls:
        print(camera.video_capture.get_format())
        print(camera.video_capture.get_fps(),' FPS')
        info = str(camera.info)
        print(info.replace(',','\n'))
        sys.exit(0)

    cameraThread = CameraThread(camera)

    hostname = config.get('server','listen')
    hostport = config.getint('server','port')

    srvr = HTTPServer((hostname,hostport), RequestHandler)
    print(f'{time.asctime()} Server Starts - {hostname}:{hostport}')

    srvr.start()
    cameraThread.join();
   
    print(f'{time.asctime()} Server Stops - {hostName}:{hostPort}')
