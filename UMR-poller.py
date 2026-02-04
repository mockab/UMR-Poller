#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8

"""
Author       : %USER%
Email        : %MAIL%
Version      : 0.1
Created      : %FDATE%
Last Modified:
Host Machine : %HOST%
Description  : %HERE%
"""

import argparse, logging, os, sys
import json, requests, yaml, ssl
import schedule, threading
from pathlib import Path
import contextlib
from http.client import HTTPConnection
from csv_logger import CsvLogger
from time import sleep
from concurrent.futures import ThreadPoolExecutor

from UMRtools import UMRrouter

def exc_hndlr(etype, value, tb):
    logger.critical(
        "Uncaught exception: {0}".format(str(value)),
        exc_info=(etype, value, tb))

    if not args.stdo:
        import traceback
        traceback.print_exception(etype, value, tb)

    if os.isatty(1) and os.isatty(2):
        import pdb

        print('')
        #pdb.post_mortem(tb) #Uncomment to enable PDB postmortem

def parse_args():
    def _str2bool(v):
        if v.lower() in ('yes', 'true', 't', 'y', '1'):
            return True
        elif v.lower() in ('no', 'false', 'f', 'n', '0'):
            return False
        else:
            raise argparse.ArgumentTypeError('Boolean value expected.')

    parser = argparse.ArgumentParser(prog = "UMR Poller",description = "Script to poll Ubiquiti UMR routers for signal strength and log periodically for analysis.")

    parser.add_argument(
        '--debug',
        nargs='?',
        const=1,
        type=_str2bool,
        default=False,
        help='Debug Mode')
    parser.add_argument(
        '--sslWarnDisable',
        nargs='?',
        const=1,
        type=_str2bool,
        default=False,
        help='Disable SSL Certificate warnings')
    parser.add_argument(
        '--gpsdEnable',
        nargs='?',
        const=1,
        type=_str2bool,
        default=False,
        help='Enable gpsd location logging')
    parser.add_argument(
        '--cprofile',
        nargs='?',
        const=1,
        type=_str2bool,
        default=False,
        help='Run main with cProfile')
    parser.add_argument(
        '--stdo',
        nargs='?',
        const=1,
        type=bool,
        default=True,
        help='Enable output to console')
    parser.add_argument(
        '--pdb',
        nargs='?',
        const=1,
        type=bool,
        default=False,
        help='Enable PDB')
    parser.add_argument(
        '--syslog',
        nargs='?',
        const=1,
        type=bool,
        default=False,
        help='Enable output to syslog')
    parser.add_argument(
        '--logdir',
        nargs='?',
        const=1,
        type=str,
        default='./logs/',
        help='set log dir, default is ./logs/')
    parser.add_argument(
        '--config',
        nargs='?',
        const=1,
        type=str,
        default='./config.yml',
        help='set config file, default is ./config.yml')
    parser.add_argument(
        '--output',
        nargs='?',
        const=1,
        type=str,
        default='./output/output.csv',
        help='set output file, default is ./output/output.csv')

    return parser.parse_known_args()

def logger_init(logname=os.path.basename(__file__)[:-3]):
    from logging import Formatter
    import time

    if args.debug:
        loglvl = logging.DEBUG
        fmt = '%(asctime)s\t%(levelname)s\t%(name)s\t%(filename)s::%(funcName)s():%(lineno)-3s\t%(message)s'
    else:
        loglvl = logging.INFO
        fmt = '%(asctime)s\t%(levelname)s\t%(message)s'

    logging.Formatter.converter = time.gmtime
    logging.Formatter.default_msec_format = '%s.%03d'

    logdir = "./logs/" if not os.path.isdir(args.logdir) else args.logdir
    app_log = "%s/%s.log" % (logdir, logname)

    if not os.path.exists(logdir):
        os.makedirs(logdir)

    logging.basicConfig(filename=app_log, level=loglvl, format=fmt)
    logging.captureWarnings(True)

    global logger
    logger = logging.getLogger()

    if args.stdo:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(loglvl)

        if os.isatty(1) and os.isatty(2):
            from copy import copy

            class ColoredFormatter(Formatter):
                RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(31,38)

                MAPPING = {
                    'WARNING'  : YELLOW,
                    'INFO'     : CYAN,
                    'DEBUG'    : BLUE,
                    'CRITICAL' : RED+10,
                    'ERROR'    : RED,
                }

                PREFIX = '\033['
                RESET = '\033[0m'
                def __init__(self, pattern):
                    Formatter.__init__(self, pattern)

                def format(self, record):
                    colored_record = copy(record)
                    levelname = colored_record.levelname
                    seq = self.MAPPING.get(levelname, self.WHITE)
                    colored_levelname = ('{0}1m{0}{1}m{2}{3}') \
                        .format(self.PREFIX, seq, levelname, self.RESET)
                    colored_record.levelname = colored_levelname
                    return Formatter.format(self, colored_record)

            cf = ColoredFormatter(fmt)
            console.setFormatter(cf)
        else:
            console.setFormatter(Formatter(fmt))
        logger.addHandler(console)

    if args.pdb:
        import pdb
        def info(tye, value, tb):
            if os.isatty(1) and os.isatty(2):
                logger.info('pdb triggered..')
                import traceback
                traceback.print_exception(tye, value, tb)
                print
                pdb.post_mortem(tb)
            else:
                logger.error('Cant start PDB without TTY')

        if os.isatty(1) and os.isatty(2):
            sys.excepthook = info
            pdb.set_trace()
        else:
            logger.error('Cant start PDB without TTY')

    if args.syslog:
        from logging.handlers import SysLogHandler
        syslog = SysLogHandler(address='/dev/log', facility=SysLogHandler.LOG_LOCAL5)
        syslog.setLevel(loglvl)
        syslog.setFormatter(logging.Formatter(fmt))

        logger.addHandler(syslog)

def debug_requests_on():
    '''Switches on logging of the requests module.'''
    HTTPConnection.debuglevel = 1

    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True

def debug_requests_off():
    '''Switches off logging of the requests module, might be some side-effects'''
    HTTPConnection.debuglevel = 0

    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.WARNING)
    requests_log.propagate = False

def logItemsFromTarget(target, logItems):
    if target.authState > 0:
        logItems.append(target.infoHigh['signal_level'])
        logItems.append(target.infoHigh['latency_max_ms'])
        logItems.append(target.infoHigh['latency_packet_loss_count'])
        logItems.append(target.infoHigh['lte_state'])
        logItems.append(target.infoHigh['rssi'])
        logItems.append(target.infoHigh['rsrq'])
        logItems.append(target.infoHigh['rsrp'])
        logItems.append(target.infoHigh['rx_channel'])
        logItems.append(target.infoHigh['tx_channel'])
        logItems.append(target.infoHigh['band'])
    else:
        for i in range(10):
            logItems.append('n/a')

def pollTarget(target):
    if target.authState == 0:
        logger.info('Target '+target.name+' on '+target.addr+' unauthorised, logging in.')
        target.connect()

    if target.authState > 0:
        target.InfoHighDump()

def iterateLoop():
    logItems = []

    with ThreadPoolExecutor(max_workers=3) as e:
        futures = []
        for target in pollingTargets:
            futures.append(e.submit(pollTarget, target))

    if gpsdEnable:
        location = gpsd.get_current()

        # print time, if we have it
        if location.mode >= 2:
            logItems.append(location.time)
            logItems.append("%.6f" % (location.lat))
            logItems.append("%.6f" % (location.lon))
            logItems.append("%.2f" % (location.hspeed))
        else:
            logItems.append('n/a')
            logItems.append('n/a')
            logItems.append('n/a')
            logItems.append('n/a')

    for target in pollingTargets:
            logItemsFromTarget(target, logItems)

    logger.debug(f'New output entry: {logItems}')
    csvlogger.logData(logItems)

def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    job_thread.start()

def main():
    logger.info('UMR Poller started.')
    logger.debug('Arguments: ')
    logger.debug(args)
    configFile = Path(args.config)
    sslWarnDisable = args.sslWarnDisable
    global gpsdEnable
    gpsdEnable = False
    global maxWorkerThreads
    maxWorkerThreads = 3
    global scheduleDelay
    scheduleDelay = 15

    global pollingTargets
    pollingTargets = []

    try:
        configFile_abs_path = configFile.resolve(strict=True)
    except FileNotFoundError:
        logger.error('Config file '+args.config+' not found, exiting.')
        exit()
    else:
        logger.info('Config file '+args.config+' found, loading values.')
        with open(configFile,"r") as config_file:
            configuration=yaml.load_all(config_file,Loader=yaml.SafeLoader)
            for data in configuration:
                entries = data['routers']
                for entry in entries:
                    pollingTargets.append(UMRrouter(entry['name'],entry['ipAddr'],entry['password'],entry['freq'],entry['SSLVerify'],True))
                globalOptions = data['global']
                if "sslWarnDisable" in globalOptions:
                    sslWarnDisable = globalOptions['sslWarnDisable']
                if "gpsdEnable" in globalOptions:
                    gpsdEnable = globalOptions['gpsdEnable']
                if "maxWorkerThreads" in globalOptions:
                    maxWorkerThreads = globalOptions['maxWorkerThreads']
                if "schedule" in globalOptions:
                    scheduleDelay = globalOptions['schedule']

    if sslWarnDisable:
        logger.info('sslWarnDisable set to True, disabling InsecureRequestWarning')
        try:
            from requests.packages.urllib3.exceptions import InsecureRequestWarning
            from requests.packages.urllib3 import disable_warnings
            disable_warnings(InsecureRequestWarning)
        except ImportError:
            pass

    outFile = args.output
    delimiter = ','
    level = logging.INFO
    custom_additional_levels = ['logData']
    fmt = f'%(asctime)s{delimiter}%(message)s'
    datefmt = '%Y-%m-%dT%H:%M:%S'
    max_size = 1048576  # 1 Mebibyte
    max_files = 4  # 4 rotating files
    header = ['Systemdate']

    if gpsdEnable:
        import gpsd
        header.append('GPSdate')
        header.append('Lat')
        header.append('Long')
        header.append('HSpeed')
        global gpsd
        gpsd.connect()


    for target in pollingTargets:
        header.append(target.name+'.InfoHighDump.signal_level')
        header.append(target.name+'.InfoHighDump.latency_max_ms')
        header.append(target.name+'.InfoHighDump.latency_packet_loss_count')
        header.append(target.name+'.InfoHighDump.lte_state')
        header.append(target.name+'.InfoHighDump.rssi')
        header.append(target.name+'.InfoHighDump.rsrq')
        header.append(target.name+'.InfoHighDump.rsrp')
        header.append(target.name+'.InfoHighDump.rx_channel')
        header.append(target.name+'.InfoHighDump.tx_channel')
        header.append(target.name+'.InfoHighDump.band')

    # Creat logger with csv rotating handler
    global csvlogger
    csvlogger = CsvLogger(filename=outFile,
                          delimiter=delimiter,
                          level=logging.INFO,
                          add_level_names=custom_additional_levels,
                          add_level_nums=None,
                          fmt=fmt,
                          datefmt=datefmt,
                          max_size=max_size,
                          max_files=max_files,
                          header=header)

    try:
        schedule.every(scheduleDelay).seconds.do(run_threaded, iterateLoop)

        while 1:
            schedule.run_pending()
            sleep(1)

    except KeyboardInterrupt:
        logger.warning("Interrupt received, closing.")

    for target in pollingTargets:
        target.close()

if __name__ == "__main__":
    args, unknown_args = parse_args()
    logger_init()
    sys.excepthook = exc_hndlr

    if args.cprofile:
        import cProfile
        cProfile.run('main()', sort='cumtime')
    else:
        main()
