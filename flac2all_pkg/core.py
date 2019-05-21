# -*- coding: utf-8 -*-
# vim: ts=4 ai expandtab

from aac import aacplus
from vorbis import vorbis
from flac import flac
from mp3 import lameMp3 as mp3
from opus import opus
from ffmpeg import ffmpeg

import threading as mt

import os
import queue
import zmq
import time


modeError = Exception("Error understanding mode. Is mode valid?")
# The modetable holds all the "modes" (read: formats we can convert to), in the format:
# [ "codec_name", "description" ]. The codec name is what the end_user will issue to
# flac2all as a mode command, so no spaces, or other special characters, and we will
# keep it lowercase
modetable = [
    ["mp3", "Lame mp3 encoder"],
    ["vorbis", "Ogg vorbis encoder"],
    ["aacplus", "aac-enc encoder"],
    ["opus", "Opus Encoder"],
    ["flac", "FLAC encoder"],
    ["test", "FLAC testing procedure"],
]
# Add the ffmpeg codecs to the modetable, we prefix "f:", so end user knows to use the ffmpeg
# options
modetable.extend([["f:" + x[0], x[1]] for x in ffmpeg("", None).codeclist()])


# 1. Set up the zmq context to receive tasks
zcontext = zmq.Context()


# Classes

class transcoder():
    def __init__(self):
        pass

    def runworker(self, host_target):
        # Task socket, recieves tasks
        tsock = zcontext.socket(zmq.PULL)
        tsock.connect("tcp://%s:2019" % host_target)

        # Comm socket, for communicating with task server
        csock = zcontext.socket(zmq.PUSH)
        csock.connect("tcp://%s:2020" % host_target)

        # Send EHLO command indicating we are ready
        csock.send_json(["EHLO"])

        # Process tasks until EOL received
        while True:
            infile, mode, opts = tsock.recv_json()
            if infile == "EOL":
                csock.send_json(["EOLACK"])
                time.sleep(0.1)
                tsock.close()
                csock.close()
                return 0

            # We send the result back up the chain
            result = self.encode(infile, mode, opts)
            csock.send_json(result)

    def encode(self, infile, mode, opts):
        # Return format:
        # [¬
        #   $infile,¬
        #   $outfile,¬
        #   $format,¬
        #   $error_status,¬
        #   $return_code,¬
        #   $execution_time¬
        # ]
        outfile = infile.replace(opts['dirpath'], os.path.join(opts['outdir'], mode))
        outpath = os.path.dirname(outfile)
        try:
            if not os.path.exists(outpath):
                os.makedirs(outpath)
        except OSError as e:
            # Error 17 means folder exists already. We can reach this
            # despite the check above, due to a race condition when a
            # bunch of spawned processes all try to mkdir at once.
            # So if Error 17, continue, otherwise re-raise the exception
            if e.errno != 17:
                raise(e)

        if mode == "mp3":
            encoder = mp3(opts['lameopts'])
        elif mode == "ogg" or mode == "vorbis":
            encoder = vorbis(opts)
        elif mode == "aacplus":
            encoder = aacplus(opts['aacplusopts'])
        elif mode == "opus":
            encoder = opus(opts['opusencopts'])
        elif mode == "flac":
            encoder = flac(opts['flacopts'])
        elif mode == "test":
            pass  # 'test' is special as it isn't a converter, it is handled below
        elif mode[0:2] == "f:":
            codec = mode[2:]  # Get the codec we want
            encoder = ffmpeg(opts['ffmpegopts'], codec)
        else:
            return [
                infile,
                outfile,
                mode,
                "ERROR: Not understanding mode '%s' is mode valid?" % mode,
                1,
                -1
            ]
        if mode == "test":
            encoder = flac(opts['flacopts'])
            encf = encoder.flactest
        else:
            encf = encoder.convert

        outfile = outfile.replace('.flac', '')
        if opts['overwrite'] is False:
            if os.path.exists(outfile + "." + mode):
                # return code is 0 because an existing file is not an error
                return [infile, outfile, "Output file already exists, skipping", mode, 0, -1]
        print("Converting: \t %-40s  target: %8s " % (
            infile.
            split('/')[-1],
            mode
        ))
        return encf(infile, outfile)


class encode_thread(mt.Thread, transcoder):
    def __init__(self, threadID, name, taskq, opts, logq):
        mt.Thread.__init__(self)
        transcoder.__init__(self)
        self.threadID = threadID
        self.name = name
        self.taskq = taskq
        self.opts = opts
        self.logq = logq

    def run(self):
        while not self.taskq.empty():
            try:
                # Get the task, with one minute timeout
                task = self.taskq.get(timeout=60)
            except queue.Empty:
                # No more tasks after 60 seconds, we can quit
                return True

            infile = task[0]
            dirpath = task[1]
            outdir = task[2]
            mode = task[3].lower()
            self.logq.put(self.encode(infile, dirpath, outdir, mode, self.opts), timeout=10)