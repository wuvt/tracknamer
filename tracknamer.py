#!/usr/bin/python
###############################
#      WUVT Latest Track Dump  v1.3
#               by Dan Caughran, 2008            
#               dcaughran@gmail.com                    
#
#   Modified by Jason McKillican
#
#   A _lot_ of changes by Michael Lowman
#
#        may be freely distributed forever           
# Version history:
#   .10: Version history starts!
#   1.0: Tripled the size of script.
#               Added proper logging, updating IceS, fallback text if
#               the webserver goes down, and daemonization
#   1.1: Added re-opening of logfile upon hangup
#   1.2: Added updates to RDS
#   1.3: Removed the offsets for the appended [WUVT ...], handled
#               the case of a dead ices2 server.
#   1.4: Changed invalid regex to properly work with or without [WUVT...]
###############################

#############################################
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#############################################

import urllib2, getopt, sys, signal, os, atexit, re
import traceback
from time import strftime, sleep

# Defaults
defaultmeta = "title=WUVT-FM 90.7 Blacksburg, VA\n" + \
              "artist=The world's greatest radio station\n" + \
              "album=Live Stream\n"
verbose = False
rdsactive = True
stayinfg = False
pollweb = True
logfilename = None
errorcount = 0
maxerrs = 3
ourpidfile = None
icespidfile = "/var/run/ices.pid"
url = "http://www.wuvt.vt.edu/playlists/latest_track_stream.php"
#filename = '/usr/share/icecast/web/track.txt'
filename = '/var/lib/icecast2/metadata.txt'
rdsfile = '/mnt/rds/rt.txt'
interval = 15
offfront = len("title=")
#offback = -len(" [WUVT-FM 90.7 Blacksburg, VA]")

def cleanup():
    if ourpidfile:
        os.remove(ourpidfile)

def daemonize():
    if os.fork() > 0:
        sys.exit(0)
    os.setsid()
    pid = os.fork()
    if pid > 0:
        if ourpidfile:
            f = open(ourpidfile, "w")
            f.write(str(pid))
            f.close()
        sys.exit(0)
    si = file("/dev/null", "r")
    if logfilename:
        so = file(logfilename, "a+", 1)
        se = file(logfilename, "a+", 0)
    else:
        so = file("/dev/null", "a+", 1)
        se = file("/dev/null", "a+", 0)
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

def handle_errs(myErr):
    global errorcount
    errorcount += 1
    if errorcount == maxerrs:
        resetmeta()
        updatethedamnicecastsource()
        errorcount = 0
    print >> sys.stderr, "HOLY CRAP!  Exception: ", traceback.print_exc()
    sleep(interval)

def handlesignal(sig, frame):
    if sig == signal.SIGUSR1:
        global pollweb
        pollweb = not pollweb
    elif sig == signal.SIGTERM:
        print "------ [END  ", strftime("%a, %d %b %Y %H:%M:%S %Z"), "] ------"
        sys.exit(0)
    elif sig == signal.SIGHUP:
        nso = file(logfilename, "a+", 1)
        nse = file(logfilename, "a+", 0)
        os.dup2(nso.fileno(), sys.stdout.fileno())
        os.dup2(nse.fileno(), sys.stderr.fileno())

def resetmeta():
    if verbose:
        print >> sys.stderr, "Seems we can't access the webserver."
        print >> sys.stderr, "Resetting to generic message..."
    f = open(filename, "w")
    f.write(defaultmeta)
    #f.write("title=WUVT-FM 90.7 Blacksburg, VA\n")
    #f.write("artist=\n")
    #f.write("album=Live Stream\n")
    f.close()

def makerdsinfo(rawhtml):
    if not pollweb:
        return "The World's Greatest Radio Station"
    tire = re.compile("title=([^\n]*?)( \\[WUVT\\-FM 90\\.7 Blacksburg, VA\\])?\n")
    ti = tire.search(rawhtml)
    arre = re.compile("artist=([^\n]*)")
    ar = arre.search(rawhtml)
    if ar is None or ti is None:
        print "Err loading data"
        return "The World's Greatest Radio Station"
    return ar.group(1) + " - " + ti.group(1)

def writerds(st):
    f = open(rdsfile, "w")
    f.write(st)
    f.close()

def updatethedamnicecastsource():
    if verbose:
        print >> sys.stderr, "updating ices THROUGH MURDER"
    pidfile = open(icespidfile, "r")
    pidstr = pidfile.read()
    pidfile.close()
    try:
        pid = int(pidstr)
        os.kill(pid, signal.SIGUSR1)
    except ValueError:
        print "IceS appears to be dead (invalid PID). Can't send a signal to something dead."
        return
    except OSError:
        print "IceS appears to be dead (couldn't kill). Can't send a signal to something dead."
        return

def usage():
    print sys.argv[0], "-hvrfn -l <logfile> -p <pidfile>"
    print "\t(-h | --help)\t\tis this message."
    print "\t(-v | --verbose)\tprint >> logfile,s shit to stdout whenever stuff happens."
    print "\t(-n | --noweb)\t\tpretends the web connection isn't there."
    print "\t(-l | --log)\t\tlogs to the given file."
    print "\t(-f | --foreground)\tdon't daemonize."
    print "\t(-p | --pidfile)\tsaves the pid to the given file."
    print "\t(-d | --disable-rds)\tdisables RDS updates."

try:
    opts, args = getopt.getopt(sys.argv[1:], "hvrl:fp:nd",
            ["help", "verbose", "reset", "log", "foreground", "pidfile", "noweb", "disable-rds"])
except getopt.GetoptError, err:
    print str(err)
    usage()
    sys.exit()
for opt in opts:
    if opt[0] in ("-h", "--help"):
        usage()
        sys.exit()
    elif opt[0] in ("-v", "--verbose"):
        verbose = True
    elif opt[0] in ("-n", "--noweb"):
        pollweb = False
    elif opt[0] in ("-l", "--log"):
        # The 1 means line buffered
        logfilename = opt[1]
    elif opt[0] in ("-f", "--foreground"):
        stayinfg = True
    elif opt[0] in ("-p", "--pidfile"):
        ourpidfile = opt[1]
    elif opt[0] in ("-d", "--disable-rds"):
        rdsactive = False

if ourpidfile:
    try:
        f = open(ourpidfile, "r")
        pid = int(f.read().strip())
        f.close()
    except IOError:
        pid = None
    except ValueError:
        pid = None
    if pid:
        print "Error, pid file", ourpidfile, "already present."
        print "Do not run multiple copies of this daemon."
        print "If you are certain it isn't running, remove the file."
        signal.signal(signal.SIGUSR1, handlesignal)
        sys.exit(1)

if not stayinfg:
    daemonize()
    
atexit.register(cleanup)
signal.signal(signal.SIGTERM, handlesignal)
signal.signal(signal.SIGUSR1, handlesignal)
signal.signal(signal.SIGHUP, handlesignal)
print "------ [START", strftime("%a, %d %b %Y %H:%M:%S %Z"), "] ------"
last_track = ''

while 1 != "banana":
    try:
        if pollweb:
            #get page
            page = urllib2.urlopen(url)
            rawpage = page.read()
            page.close()
        else:
            rawpage = defaultmeta
        #write text file
        if (rawpage != last_track):
            firstline = rawpage.split("\n")[0]
            if firstline == "title=WUVT-FM 90.7 Blacksburg, VA":
                print strftime("%m.%d.%y-%H:%M:%S"), "DEAD WEB SERVER"
            else:
                print strftime("%m.%d.%y-%H:%M:%S"), \
                    rawpage.split("\n")[0][offfront:]
            sys.stdout.flush()
            file = open(filename, 'w')
            file.write(rawpage)
            file.close()
            last_track = rawpage
            updatethedamnicecastsource()
            sys.stdout.flush()
            if rdsactive:
                rdsdata = makerdsinfo(rawpage)
                if verbose:
                    print rdsdata
                writerds(rdsdata)
        errorcount = 0
        #wait
        sleep(interval)
    except KeyboardInterrupt:
        print "------ [END  ", strftime("%a, %d %b %Y %H:%M:%S %Z"), "] ------"
        logfile.close()
        sys.exit(0)
    except SystemError:
        logfile.close()
        sys.exit(0)
    except RuntimeError:
        logfile.close()
        sys.exit(0)
    except urllib2.URLError:
        handle_errs(sys.exc_info())
# vim: et:ts=8:sts=4:sw=4
