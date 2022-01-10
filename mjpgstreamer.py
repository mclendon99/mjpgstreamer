#! /usr/bin/python3
""" mjpgstreamer.py
    Stream mjpg to a client, e.g. github.com://mclendon99/gps_tracker
    Based loosely on github.com://soyersoyer/fmp4streamer
    Uses v4l2py on https://pypi.org/project/v4l2py/
    Requires v4l2 patch https://bugs.launchpad.net/python-v4l2/+bug/1664158

    Todo:
    - support multiple cameras

__authoer__ = "McLrenndon"

"""

__author__ = "McLendon"
__license__ = """
"""

import os,logging, getopt, time, errno, sys, timeit, socketserver,configparser
from logging.handlers import RotatingFileHandler
from queue import Queue
from http.server import BaseHTTPRequestHandler,HTTPServer
from threading import Thread
import threading
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

class CameraThread(threading.Thread):
    def __init__(self, camera):
        super(CameraThread, self).__init__()
        self.camera = camera
        self.consumers = []
        logging.debug(f'Camera initialized')

    def run(self):
        logging.debug(f'Camera running')
        frame_budget = 1000 / fps
        for frame in self.camera:
           start = timeit.default_timer()
           for c in self.consumers:
               c.put(frame)
           stop = timeit.default_timer()
           diff = frame_budget - (stop - start) * 1000  # Delay in ms
           if (diff > 0):
              time.sleep(diff/1000) # Wait until next frame ready

    def stop(self):
        logging.debug(f'Camera stopped')
        self.frame = None
        self.consumers.clear()

    def register_queue(self, q):
        self.consumers.append(q)
        logging.debug(f'Register consumer')

    def unregister_queue(self, q):
        self.consumers.remove(q)
        logging.debug(f'Deregister consumer')

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

class RequestHandler(BaseHTTPRequestHandler):
    def process_camera_frames(self):
        frame_budget = 1000 / fps
        # If the camera is stopped, we close the connection
        while True:
          try:
            # This blocks waiting for a camera frame
            frame = self.q.get(block=True, timeout=5)
            if frame is not None:
              try:
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
              except Exception as e:
                logging.warning(f'Removing streaming client {self.client_address} {str(e)}')
                try:
                  self.send_error(404)
                  self.end_headers()
                  return 0
                except Exception as e:
                  logging.info(f'Send 404 failed {self.client_address} {str(e)}')
                  return 0 # Don't kill everything. Go back and wait for new connection
            else:
              try: 
                logging.info(f'Camera shutdown detected {self.client_address} {str(e)}')
                self.send_response(404)
                self.end_headers()
                return -2
              except Exception as e:
                logging.warning(f'Send 404 failed {self.client_address} {str(e)}')
                return -2
          except Exception as e:
              logging.info(f'Empty queue timeout {str(e)}')
              time.sleep(frame_budget/1000) # Wait until next frame ready
                  
    def do_GET(self):
        logging.debug(f'do_GET from {self.client_address}')
        self.send_response(200)
        self.send_header('Age','0')
        self.send_header('Expires','0')
        self.send_header('Cache-Control', 'no-cache,no-store,must-revalidate')
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.send_header('Connection', 'close')
        self.end_headers()
        ## Register our queue and start sending frames to the client
        self.q = Queue()
        camera_thread.register_queue(self.q)
        logging.debug(f'do_GET Register client {self.client_address}')
        rc = self.process_camera_frames()
        logging.debug(f'do_GET Unregister client {self.client_address}')
        camera_thread.unregister_queue(self.q)
        logging.debug(f'do_GET - exit thread {self.client_address}:{rc}')
        sys.exit(rc)

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
    print(f'  -c CONFIG, --config CONFIG  use CONFIG as a config file, default: mjpgstreamer.conf')
    print(f'  -d {DEBUG|INFO|WARNING|ERROR|CRITICAL}')


if __name__ == '__main__':
    # Some defaults
    hostName = ''
    hostPort = 8090
    height = 480
    width = 640
    fps = 30
    list_controls = False
    loglevel = "WARNING"
    configfile = "mjpgstreamer.conf"

    try:
        arguments, values = getopt.getopt(sys.argv[1:], "hlcd:", ["help", "list-controls","config=","debug="])
    except getopt.error as err:
        print(err)
        usage()
        sys.exit(-1)
    
    configfile = "mp4streamer.conf"
    for current_argument, current_value in arguments:
        if current_argument in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif opt in( '-d', '--debug'):
            loglevel = arg
            print("Using log level:"+loglevel)
        elif current_argument in ("-l", "--list-controls"):
            list_controls = True
        elif current_argument in ("-c", "--config"):
            configfile = current_value
    
    config = Config(configfile)
    device = config.get_device()

    # Process debug level arg
    log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
    # Should add this to the config file
    logFile = '/var/tmp/mjpgstreamer.log'

    my_handler = RotatingFileHandler(logFile, mode='a', maxBytes=5*1024*1024,
                                   backupCount=2, encoding=None, delay=0)
    my_handler.setFormatter(log_formatter)
    numericLevel = getattr(logging, loglevel.upper(),"WARNING")
    print("Using log level:" + str(numericLevel))
    my_handler.setLevel(numericLevel)

    app_log = logging.getLogger('root')
    app_log.setLevel(numericLevel)
    app_log.addHandler(my_handler)


    logging.info(f'Using device {device}')

    camera = Device(device)
    if list_controls:
        print(camera.video_capture.get_format())
        print(camera.video_capture.get_fps(),' FPS')
        info = str(camera.info)
        print(info.replace(',','\n'))
        sys.exit(0)

    hostname = config.get('server','listen')
    hostport = config.getint('server','port')

    camera_thread = CameraThread(camera)
    logging.debug(f'Camera starts')
    camera_thread.start()

    srvr = HTTPServer((hostname,hostport), RequestHandler)
    if (len(config.get('server', 'keyfile')) != 0 and len(config.get('server','certfile')) != 0 :
        srvr.socket = ssl.wrap_socket(srvr.socket, \
               config.get('server', 'keyfile'), config.get('server','certfile'), server_side=True)
    logging.debug(f'Server Starts - {hostname}:{hostport}')

    srvr.start()
    camera_thread.join()
   
    logging.debug(f'Server Stops - {hostName}:{hostPort}')
