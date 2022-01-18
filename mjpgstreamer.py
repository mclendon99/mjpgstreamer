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

import os,logging, getopt, time, errno, sys, timeit, socketserver, configparser,  io, ssl
from logging.handlers import RotatingFileHandler
from queue import Queue
from http.server import BaseHTTPRequestHandler,HTTPServer
import threading
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

class CameraThread(threading.Thread):
    def __init__(self, camera):
        super(CameraThread, self).__init__()
        self.camera = camera
        self.consumers = []
        logger.debug(f'Camera initialized')

    def run(self):
        logger.debug(f'Camera running')
        frame_budget = 1000 / config.fps()
        try:
            for frame in self.camera:
               start = timeit.default_timer()
               for c in self.consumers:
                   c.put(frame)
               stop = timeit.default_timer()
               diff = frame_budget - (stop - start) * 1000  # Delay in ms
               if (diff > 0):
                  time.sleep(diff/1000) # Wait until next frame ready
        except KeyboardInterrupt:
            pass

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


# Set defaults for anything that can be found in the config file
# Priority is command line, config file, and lowest is default
class Config(configparser.ConfigParser):
    def __init__(self, configfile):
        super(Config,self).__init__()
        # Default the fixed sections
        self.read_dict({'DEFAULT': {
                          'logfile': '',
                          'loglevel':'WARNING'},
                        'server': {
                          'listen': '', 
                          'port': 8080,
                          'keyfile': '', 
                          'certfile': ''}})
        # Now read the config file values
        if len(self.read(configfile)) == 0:
            print(f'Couldn\'t read {configfile}. Using default configuration')
            # Force a video device even if no config file
            self.add_section('/dev/video0')


        # Can be other than /dev/video0
        self.device = self.get_devices()[0]

        self.read_dict({self.device : {
                          'width': 640,
                          'height': 480,
                          'fps': 30 }})

    def get_devices(self):
        return [s for s in self.sections() if s != 'server' and s != 'default']

    def get_device(self):
        return self.device

    def height(self):
        return int(self[self.device]['height'])

    def width(self):
        return int(self[self.device]['width'])

    def fps(self):
        return int(self[self.device]['fps'])

    def logfile(self):
        return config['default']['logfile']

    def loglevel(self):
        return config['default']['loglevel']

    def listen(self):
        return config['server']['listen']

    def port(self):
        return int(config['server']['port'])

    def certfile(self):
        return config['server']['certfile']

    def keyfile(self):
        return config['server']['keyfile']



def usage():
    print(f'Usage: python3 {sys.argv[0]} [--help] [--config CONFIG]\n')
    print(f'Optional arguments:')
    print(f'  -h, --help                  Show this help message and exit')
    print(f'  -i, --info                  Show video information and exit')
    print(f'  -c CONFIG, --config CONFIG  Use CONFIG as a config file, default: mjpgstreamer.conf')
    print(f'  -l D(EBUG)|I(NFO)|W(ARNING)|E(RROR)|C(RITICAL)   default: WARNING - Only D,I,W options implemented')


if __name__ == '__main__':
 
    # Command line handling
    try:
        arguments, values = getopt.getopt(sys.argv[1:], "hic:l:", ["help", "info", "config=","log="])
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
    loglevel_cmd = False
    for current_argument, current_value in arguments:
        if current_argument in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif current_argument in ("-c", "--config"):
            configfile = current_value
        elif current_argument in ("-i", "--info"):
            list_info = True
        elif current_argument in( '-l', '--log'):
            loglevel = current_value.upper()
            
            if len(loglevel) == 1: 
                if loglevel in log_dict.keys():
                    loglevel = log_dict[loglevel]
                else:
                    print(f'Invalid log argument {loglevel}')
                    sys.exit(-1)
            loglevel_cmd = True   # Override the config
            print(f'Selected log level:{loglevel}')
            
    
    # Config file handling
    # Set defaults as per config file, if any
    config = Config(configfile)

    # Set up logging using "logger"
    # Process log level arg
    logfile = config.logfile()
    if loglevel_cmd is False:
       loglevel = config.loglevel()

    if len(logfile) != 0:
        log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
        my_handler = RotatingFileHandler(logfile, mode='a', maxBytes=5*1024*1024,
                                   backupCount=2, encoding=None, delay=0)
        my_handler.setFormatter(log_formatter)
        numericLevel = getattr(logging, loglevel,"WARNING")
        my_handler.setLevel(numericLevel)

        logger = logging.getLogger(__name__)
        logger.setLevel(numericLevel)
        logger.addHandler(my_handler)
    else:
        logging.basicConfig()
        logger = logging.getLogger(__name__)
        numericLevel = getattr(logging, loglevel,"WARNING")
        logger.setLevel(numericLevel)

    camera = Device(config.get_device())
    # Use settings from config 
    camera.video_capture.set_format(config.width(), config.height()) 
    camera.video_capture.set_fps(config.fps()) 
    # Copy what the camera thinks
    width,height,fmt = camera.video_capture.get_format()
    fps = camera.video_capture.get_fps()
    config[config.get_device()]['height'] = str(height)
    config[config.get_device()]['width'] = str(width)
    config[config.get_device()]['fps'] = str(fps)

    logger.info(f'Using camera {config.get_device()} {width}x{height}@{fps} FPS')

    if list_info:
        print(f'{width}x{height}@{fps} FPS')
        info = str(camera.info)
        print(info.replace(',','\n'))
        sys.exit(0)

    camera_thread = CameraThread(camera)
    logger.debug(f'Camera starts')
    camera_thread.start()

    srvr = HTTPServer((config.listen(),config.port()), RequestHandler)
    logger.debug(f'Server Starts - {config.listen()}:{config.port()}')
    if config.keyfile() is not None and config.certfile() is not None :
        logger.debug(f'Using SSL/HTTPS - {config.keyfile()}:{config.certfile()}')
        srvr.socket = ssl.wrap_socket(srvr.socket, \
               config.keyfile(), config.certfile(), server_side=True)

    srvr.start()
    srvr.shutdown()
    camera_thread.shutdown()
    camera_thread.join()
   
    logger.debug(f'Server Stops - {hostname}:{hostport}')
