import subprocess # for piping
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

class RequestHandler(BaseHTTPRequestHandler):
    def _writeheaders(self):
        self.send_response(200) # 200 OK http response
        self.send_header('Content-type', 'video/mp4')
        self.end_headers()

    def do_HEAD(self):
        self._writeheaders()

    def do_GET(self):
        self._writeheaders()

        DataChunkSize = 10000

        command = '(echo "--video boundary--"; ffmpeg -f v4l2 -i /dev/video2 -preset ultrafast -codec copy  \
                          -f mpegts -segment_format_options movflags=+faststart pipe:1'
        print("running command: %s" % (command, ))
        p = subprocess.Popen(command, stdout=subprocess.PIPE, bufsize=-1, shell=True)

        print("starting polling loop.")
        while(p.poll() is None):
            print "looping... "
            stdoutdata = p.stdout.read(DataChunkSize)
            self.wfile.write(stdoutdata)

        print("Done Looping")

        print("dumping last data, if any")
        stdoutdata = p.stdout.read(DataChunkSize)
        self.wfile.write(stdoutdata)

if __name__ == '__main__':
    serveraddr = ('', 8090) # connect to port 8090
    srvr = HTTPServer(serveraddr, RequestHandler)
    srvr.serve_forever()
