# vim: ts=4 ai expandtab
import os
import re
from shell import shell
from time import time
from flac import flacdecode
from config import ipath
import subprocess as sp

# Class that deals with the opus codec


class opus:
    def __init__(self, opusencopts):
        # Work out what version of opus we have
        self.version = None  # Unknown by default

        # Opus is really all over the place, each version has different
        # switches. I guess that is what happens with new stuff
        try:
            data = sp.check_output(["%sopusenc" % ipath.opusencpath, "-V"])
        except sp.CalledProcessError:
            data = sp.check_output(["%sopusenc" % ipath.opusencpath, "-v"])

        data = re.search("\d\.\d\.\d", data).group(0)
        (release, major, minor) = map(lambda x: int(x), data.split('.'))
        self.version = (release, major, minor)
        self.opts = opusencopts

    def opusConvert(self, infile, outfile, logq):
        # As the new versions of opus support flac natively, I think that the
        # best option is to
        # use >0.1.7 by default, but support earlier ones without tagging.
        startTime = time()

        if self.version is None:
            print "ERROR! Could not discover opus version, assuming version >=\
                0.1.7. THIS MAY NOT WORK!"
            version = (9, 9, 9)
        else:
            version = self.version

        # If we are a release prior to 0.1.7, use non-tagging type conversion,
        # with warning
        if (version[0] == 0) and (version[1] <= 1) and (version[2] <= 6):
            print "WARNING: Opus version prior to 0.1.7 detected,\
                NO TAGGING SUPPORT"
            decoder = flacdecode(infile)()
            encoder = sp.Popen("%sopusenc %s - %s.opus  2> /tmp/opusLog" % (
                ipath.opusencpath,
                self.opts,
                shell().parseEscapechars(outfile),
            ),
                shell=True,
                bufsize=8192,
                stdin=sp.PIPE
            ).stdin

            # while data exists in the decoders buffer
            for line in decoder.readlines():
                encoder.write(line)  # write it to the encoders buffer

                # if there is any data left in the buffer, clear it
                decoder.flush()
                decoder.close()  # somewhat self explanetory

                encoder.flush()  # as above
                encoder.close()
            logq.put([
                infile,
                outfile,
                "opus",
                "SUCCESS_NOTAGGING",
                0,
                time() - startTime
            ])
        else:
            # Later versions support direct conversion from flac->opus, so no
            # need for the above.
            rc = os.system("%sopusenc %s --quiet %s %s.opus" % (
                ipath.opusencpath,
                self.opts,
                shell().parseEscapechars(infile),
                shell().parseEscapechars(outfile)
            ))

            if (rc != 0):
                logq.put([
                    infile,
                    outfile,
                    "opus",
                    "ERROR: error executing opusenc. Could not convert",
                    rc,
                    time() - startTime
                ])
            else:
                logq.put([
                    infile,
                    outfile,
                    "opus",
                    "SUCCESS",
                    rc,
                    time() - startTime
                ])
