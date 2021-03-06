
### MJPGStreamer

MJPGStreamer is a streamer that can stream MJPG (obviously) from a USB or standard camera. It is based loosely on soyersoyers [FMP4Streamer][1] 'cause he's a decent coder and I could borrow lot's of his infrastructure/design.  Most of the functional insides have been rewritten.

The [v4l2py][2] library was also used. Be sure to patch the v4l2 library as indicated here [V4L2 patch][3]

#### Features
- Lightweight - around 12% CPU on a single core 500 MHz ARMv7 capturing 640x480 30fps
  - UVC driver adds another 5%
- Built using Python3.7 on a Beaglebone Black 5.10.87-bone59
- Based on v4l2py 0.6.0 [2]
- Supports multiple browser connections
- Supports USB uv4l cameras
 - Be sure to apply the patch [V4L2 patch][3]
- Highly threaded 
  - Each browser connection get it's own thread
  - Each camera (only supports one now) gets it's own thread
- Robust
  - Try blocks everywhere
  - Lot's of logging
- Configurable via config file
- COmmand line options override configuration options which override default options

The config file has multiple sections:

The default section is labeled [default]. It takes two parameters: lofile and loglevel.
Loglevel is a text string indicating the logging level: D(EBUG)|I(NFO)|W(ARNING)|E(RROR)|C(RITICAL)
Loglevel may also be configured on the command line using the -d option.

The logfile, if configured, sets a rotating file log. If not configured, stdout is used.
logfile=/var/tmp/mjpgstreamer.log
loglevel='WARNING'

The [server] section configures a server to listen and the port number on which it listens for HTTP GETS. If both the keyfile (private key) and certfile (certificate) parameters are configured, the server will listen for HTTPS requests.

The lasst section contains the [/path/to/video_device]. One may also configure the width, height, and frames per second (fps). These parameters are sent to the3 video device. The video device is then queried for it's actual settings.


#### Todo
- Support configuration of multiple servers on different ports, e.g. HTTP and HTTPS simultaneously
- Support multiple cameras (because why not)
- Test on the RPI with the MIPI camera

[1]https://github.com/soyersoyer/fmp4streamer
[2]https://pypi.org/project/v4l2py/
[3]https://bugs.launchpad.net/python-v4l2/+bug/1664158 
-
