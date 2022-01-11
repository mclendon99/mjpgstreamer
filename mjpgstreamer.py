#! /usr/bin/python3
""" mjpgstreamer.py
    Stream mjpg to a client, e.g. github.com://mclendon99/gps_tracker
    Based loosely on github.com://soyersoyer/fmp4streamer
    Uses v4l2py on https://pypi.org/project/v4l2py/
    Requires v4l2 patch https://bugs.launchpad.net/python-v4l2/+bug/1664158

    Todo:
    - support multiple cameras

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
        logger.debug(f'Camera initialized')

    def run(self):
        logger.debug(f'Camera running')
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
        logger.debug(f'Camera stopped')
        self.frame = None
        self.consumers.clear()

    def register_queue(self, q):
        self.consumers.append(q)
        logger.debug(f'Register consumer')

    def unregister_queue(self, q):
        self.consumers.remove(q)
        logger.debug(f'Deregister consumer')

    def shutdown(self):
        self.stop()
        camera.close()
        sys.exit(0)

class HTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def start(self):
      try:
          self.serve_forever()
      except KeyboardInterrupt:
          return

    def shutdown(self):
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
                logger.warning(f'Removing streaming client {self.client_address} {str(e)}')
                try:
                  self.send_error(404)
                  self.end_headers()
                  return 0
                except Exception as e:
                  logger.info(f'Send 404 failed {self.client_address} {str(e)}')
                  return 0 # Don't kill everything. Go back and wait for new connection
            else:
              try: 
                logger.info(f'Camera shutdown detected {self.client_address} {str(e)}')
                self.send_response(404)
                self.end_headers()
                return -2
              except Exception as e:
                logger.warning(f'Send 404 failed {self.client_address} {str(e)}')
                return -2
          except KeyboardInterrupt:
                self.send_response(404)
                self.end_headers()
                self.shutdown()
                return -2
          except Exception as e:
              logger.info(f'Empty queue timeout {str(e)}')
              time.sleep(frame_budget/1000) # Wait until next frame ready
                  
    def do_GET(self):
        logger.debug(f'do_GET from {self.client_address}')
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
        logger.debug(f'do_GET Register client {self.client_address}')
        rc = self.process_camera_frames()
        logger.debug(f'do_GET Unregister client {self.client_address}')
        camera_thread.unregister_queue(self.q)
        logger.debug(f'do_GET - exit thread {self.client_address}:{rc}')
        sys.exit(rc)



class Config(configparser.ConfigParser):
    def __init__(self, configfile):
        super(Config, self).__init__({
            'width': 640,
            'height': 480,
            'fps': 30,
        })
        self.read_dict({'default': {'logfile': '/var/tmp/mjpgstreamer.log', \
                       'loglevel':'WARNING'}})

        self.read_dict({'server': {'listen': '', 'port': 8090,'keyfile':'', \
                       'certfile':''}})

        if len(self.read(configfile)) == 0:
            logger.warning(f'Couldn\'t read {configfile}, using default config')

        if len(self.sections()) == 2:
            self.add_section('/dev/video0')

        self.device = self.get_devices()[0]

    def get_devices(self):
        return [s for s in self.sections() if s != 'server' and s != 'default']

    def get_device(self):
        return self.device

    def width(self):
        return int(self[self.device]['width'])

    def height(self):
        return int(self[self.device]['height'])

    def fps(self):
        return int(self[self.device]['fps'])

    def certfile(self):
        return config['server']['certfile']

    def keyfile(self):
        return config['server']['keyfile']

    def logfile(self):
        return config['default']['logfile']

    def loglevel(self):
        return config['default']['loglevel']


def usage():
    print(f'Usage: python3 {sys.argv[0]} [--help] [--config CONFIG]\n')
    print(f'Optional arguments:')
    print(f'  -h, --help                  Show this help message and exit')
    print(f'  -i, --info                  Show video information and exit')
    print(f'  -c CONFIG, --config CONFIG  Use CONFIG as a config file, default: mjpgstreamer.conf')
    print(f'  -d D(EBUG)|I(NFO)|W(ARNING)|E(RROR)|C(RITICAL)   default: WARNING - Only D,I,W options implemented')


if __name__ == '__main__':
 
    # Command line handling
    try:
        arguments, values = getopt.getopt(sys.argv[1:], "hicd:", ["help", "info", "config=","debug="])
    except getopt.error as err:
        print(err)
        usage()
        sys.exit(-1)
    
    configfile = "mjpgstreamer.conf"
    list_info = False
    log_dict = {'D':'DEBUG',
                'I':'INFO',
                'W':'WARNING',
                'E':'ERROR',
                'C':'CRITICAL'}
    for current_argument, current_value in arguments:
        if current_argument in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif current_argument in ("-c", "--config"):
            configfile = current_value
        elif current_argument in ("-i", "--info"):
            list_info = True
        elif current_argument in( '-l', '--log'):
            loglevel = upper(arg)
            if loglevel not in log_dict:
               print(f'Invalid log argument {loglevel}')
               sys.exit(-1)
            loglevel = log_dict(loglevel)
            print(f'Selected log level:{loglevel}')
    
    # Config file handling
    # Set defaults as per config file, if any
    config = Config(configfile)

    device = config.get_device()

    logfile = config.logfile()
    loglevel = config.loglevel()

    hostname = config.get('server','listen')
    hostport = config.getint('server','port')

    height = config.height()
    width = config.width()
    fps =  config.fps()

    # Set up logging using "logger"
    # Process log level arg
    log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')

    my_handler = RotatingFileHandler(logfile, mode='a', maxBytes=5*1024*1024,
                                   backupCount=2, encoding=None, delay=0)
    my_handler.setFormatter(log_formatter)
    numericLevel = getattr(logging, loglevel,"WARNING")
    print(f'Logging:{loglevel} -> {logfile}')
    my_handler.setLevel(numericLevel)

    logger = logging.getLogger('root')
    logger.setLevel(numericLevel)
    logger.addHandler(my_handler)

    camera = Device(device)
    # Use settings from the config file
    camera.video_capture.set_format(width, height) 
    camera.video_capture.set_fps(fps) 
    # Copy what the camera thinks
    width,height,fmt = camera.video_capture.get_format()

    logger.info(f'Using device {device} {width}x{height}@{camera.video_capture.get_fps()} FPS')
    print(f'Using device {device} {width}x{height}@{camera.video_capture.get_fps()} FPS')

    if list_info:
        print(f'{width}x{height}@{camera.video_capture.get_fps()} FPS')
        info = str(camera.info)
        print(info.replace(',','\n'))
        sys.exit(0)

    camera_thread = CameraThread(camera)
    logger.debug(f'Camera starts')
    camera_thread.start()

    srvr = HTTPServer((hostname,hostport), RequestHandler)
    logger.debug(f'Server Starts - {hostname}:{hostport}')
    if len(config.keyfile()) != 0 and len(config.certfile()) != 0 :
        srvr.socket = ssl.wrap_socket(srvr.socket, \
               config.keyfile(), config.certfile(), server_side=True)

    srvr.start()
    srvr.shutdown()
    camera_thread.shutdown()
    camera_thread.join()
   
    logger.debug(f'Server Stops - {hostname}:{hostport}')
