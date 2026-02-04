#! /usr/bin/env python3

import argparse, logging, os, sys
import json, requests, yaml, ssl
import http.client as httplib

logger = logging.getLogger(__name__)

class UMRrouter:
    """
        Router authState options:
        -1 - Error, not reachable
         0 - Initialised and not connected
         1 - Logged in and authorised
    """
    def __init__(self, name, addr, password, freq, SSLVerify, connectOnCreate):
        self.name = name
        self.addr = addr
        self.password = password
        self.freq = freq
        self.SSLVerify = SSLVerify

        self.session = requests.Session()
        self.authState = 0
        self.deviceStatus = 0
        self.status = 0
        self.infoLow = 0
        self.infoHigh = 0
        self.infoClient = 0

        self.session.headers.update(
            {
                "Host": self.addr,
                "Accept": "*/*",
                "content-type": "application/json; charset=utf-8",
                "Origin": f"https://{self.addr}",
                "Connection": "keep-alive"
            }
        )

        logger.debug("UMRrouter created: "+f"{self.name}")

        if connectOnCreate == True:
            self.connect()

    def __str__(self):
        return json.dumps(self.__dict__)

    def close(self):
        self.session.close()

    def connect(self):
        try:
            response = self.session.post(
                "https://"+self.addr+"/ubus/call/session",
                headers={
                    "Referer": f"https://{self.addr}",
                    "Priority": "u=0",
                    "content-type": None,
                },
                json={
                    "jsonrpc":"2.0",
                    "method":"login",
                    "params":{
                        "username":"ui",
                        "password":self.password,
                        "timeout":2129920
                    }
                },
                verify=self.SSLVerify
            )
        except ssl.SSLCertVerificationError:
            logger.error("SSL Certificate unsigned: "+err)
        except httplib.BadStatusLine:
            logger.error("Bad Status Line received: "+err)
        except OSError as err:
            # print(response.json())
            logger.error(err)
            self.authState = -1
        else:
            logger.debug(response.json())
            if 'result' in response.json():
                auth = "Bearer " + response.json()["result"]["ubus_rpc_session"]
                self.session.headers.update({"authorization": auth})
                self.authState = 1
                logger.info("Login to "+self.name+" successful, auth id: "+auth)
            else:
                self.authState = -1
                logger.error("Login to "+self.name+" failed, error: "+f'{response.json()["error"]}')

    def uimqttCall(self, method):
        try:
            response = self.session.post(
                "https://"+self.addr+"/ubus/call/uimqtt",
                headers={
                    "Referer": f"https://{self.addr}",
                    "Priority": "u=0",
                    "content-type": None,
                },
                json={
                    "jsonrpc":"2.0",
                    "method": method,
                    "params":{
                    }
                },
                verify=self.SSLVerify
            )
        except ssl.SSLCertVerificationError:
            logger.error("SSL Certificate unsigned: "+err)
            return 0
        except httplib.BadStatusLine:
            logger.error("Bad Status Line received: "+err)
            return 0
        except OSError as err:
            # print(response.json())
            logger.error(err)
            self.authCode = -1
            return 0
        else:
            output = response.json()
            logger.debug(method+" request to "+self.name+" successful, result:"+f"{output['result']}")
            return output['result']

    def getDeviceStatus(self):
        newDeviceStatus = self.uimqttCall("GetDeviceStatus")
        if newDeviceStatus != 0:
            self.deviceStatus = newDeviceStatus

    def getStatus(self):
        newStatus = self.uimqttCall("GetStatus")
        if newStatus != 0:
            self.status = newStatus

    def InfoLowDump(self):
        newInfoLow = self.uimqttCall("InfoLowDump")
        if newInfoLow != 0:
            self.infoLow = newInfoLow

    def InfoHighDump(self):
        newInfoHigh = self.uimqttCall("InfoHighDump")
        if newInfoHigh != 0:
            self.infoHigh = newInfoHigh

    def InfoClientDump(self):
        newInfoClient = self.uimqttCall("InfoClientDump")
        if newInfoClient != 0:
            self.infoClient = newInfoClient
