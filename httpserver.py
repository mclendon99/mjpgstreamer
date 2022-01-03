#! /usr/bin/python3
import subprocess # for piping
from http.server import BaseHTTPRequestHandler, HTTPServer

class RequestHandler(BaseHTTPRequestHandler):
    def _writeheaders(self):
        self.send_response(200) # 200 OK http response
        self.send_header('Transfer-Encoding', 'chunked')
        self.send_header('Content-type', 'video/mp4')
        self.end_headers()

    def do_HEAD(self):
        self._writeheaders()

    def do_GET(self):
        self._writeheaders()

        DataChunkSize = 10000
        command = '(echo "--video boundary--"; ffmpeg -f v4l2 -i /dev/video2 -vcodec libx264 -preset ultrafast -tune zerolatency -b:v 900k  -f mpegts -r 30 pipe:1)'
#        command = '(echo "--video boundary--"; ffmpeg -f v4l2 -fflags +genpts -r 30 -i /dev/video2 -vcodec libx264 -preset veryfast -codec copy  -f segment -segment_format mp4 -segment_time 10 -segment_format_options movflags=+faststart -f mpegts -r 30 pipe:1)'
#        command = '(echo "--video boundary--"; ffmpeg movie=/dev/video2:f=video4linux -codec copy -f segment -segment_format mp4 -segment_time 10 -segment_format_options movflags=+faststart -f mpegts -r 30 pipe:1)'
        print("running command: %s" % (command, ))
        p = subprocess.Popen(command, stdout=subprocess.PIPE, bufsize=-1, shell=True)

        print("starting polling loop.")
        while(p.poll() is None):
            stdoutdata = p.stdout.read(DataChunkSize)
            self.wfile.write(stdoutdata)

        print("Done Looping")

        print("dumping last data, if any")
        stdoutdata = p.stdout.read(DataChunkSize)
        self.wfile.write(stdoutdata)

if __name__ == '__main__':
    serveraddr = ('', 8090) # connect to port 8090
    srvr = HTTPServer(serveraddr, RequestHandler)
    try:
       srvr.serve_forever()
    except KeyboardInterrupt:
       pass

    srvr.server_close()
    print("Server stopped")
