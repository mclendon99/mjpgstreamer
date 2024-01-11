
### MJPGStreamer

MJPGStreamer is a streamer that can stream MJPG (obviously) from a USB or standard camera. It is based loosely on soyersoyers [FMP4Streamer](https://github.com/soyersoyer/fmp4streamer) 'cause he's a sharp coder and I could borrow lots of his design.  Most of the functional insides have been rewritten.

The [v4l2py](https://pypi.org/project/v4l2py) library was also used.

#### Features

- Lightweight - around 12% CPU on a single core 500 MHz ARMv7 capturing 640x480 30fps
  - UVC driver adds another 5%
- Tested using Python3.7 on a Beaglebone Black 5.10.87-bone59. Runs on a PI 3B or PI 4 as well.
- Based on v4l2py 0.6.0
- Supports multiple browser connections
- Supports USB uv4l cameras and RPI cameras
- Highly threaded 
  - Each browser connection get it's own thread
  - Each camera (only supports one now) gets it's own thread
- Robust
  - Try blocks everywhere
  - Lot's of logging
- Configurable via config file or command line
- Command line options override config file options which override default options

#### Discussion

The config file has multiple sections:

The default section is labeled [default]. It takes two parameters: logfile and loglevel.
Loglevel is a text string indicating the logging level: D(EBUG)|I(NFO)|W(ARNING)|E(RROR)|C(RITICAL)
Loglevel may also be configured on the command line using the -d option.

The logfile, if configured, sets a rotating file log. If not configured, stdout is used.

Example: 

    logfile=/var/tmp/mjpgstreamer.log
    loglevel='WARNING'

The [server] section configures a server to listen on the port number over which it receives HTTP GETS. If both the keyfile (private key) and certfile (certificate) parameters are configured, the server will listen for HTTPS requests.

The last section contains the [/path/to/video_device]. One may also configure the width, height, and frames per second (fps). These parameters are sent to the video device. The video device is then queried for it's actual settings.

#### Todo

- Support configuration of multiple servers on different ports, e.g. HTTP and HTTPS simultaneously. 
- Each connection has it's own thread. (done)
- Support multiple cameras (because why not)
- Test on the RPI with the MIPI camera

### References

[fmp4streamer](https://github.com/soyersoyer/fmp4streamer)

[v4l2py](https://pypi.org/project/v4l2py)
