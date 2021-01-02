import os, re
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTShadowClient

import logging
import time
import json
import argparse

# read 1W temperature sensor.
# The sensor's id is supposed to be 28
# return two values:
# 1. True or False
#    True - success
#    False - Failure
# 2. temperature reading
def read1WTemp():
    basePath = '/sys/bus/w1/devices/'
    #basePath = os.getcwd()
    fullPath = ''
    tempReading = 999999
    for entry in os.listdir(basePath):
        #print(entry)
        fullPath = os.path.join(basePath, entry)
        #print(fullPath)
        if os.path.isdir(fullPath):
             if (entry[0] == '2') and (entry[1] == '8') and (entry[2] == '-'):
                fullPath = os.path.join(fullPath, 'temperature')
                print(fullPath) 

                try:
                    tempFileFd = open(fullPath, 'r')
                except:
                    print("Open temp file fail\n")
                    return False,tempReading

                try:                    
                    tempReading = int(re.sub("[^0-9]", "", tempFileFd.read()))
                except ValueError:
                    print("I/O operation on read temperature file.")
                    tempFileFd.close()
                    return False,tempReading

                return True, tempReading/1000.0
                tempFileFd.close()
                    
    
    return False,tempReading            

# The following functions are lifted from the following aws website with some modification.
# https://docs.aws.amazon.com/iot/latest/developerguide/iot-moisture-raspi-setup.html
# The original code reads temprature and moisture from I2C
# This file reads temperature from 1 wire instead.

# Shadow JSON schema:
#
# {
#   "state": {
#       "desired":{
#           "temp":<INT VALUE>            
#       }
#   }
# }

# Function called when a shadow is updated
def customShadowCallback_Update(payload, responseStatus, token):

    # Display status and data from update request
    if responseStatus == "timeout":
        print("Update request " + token + " time out!")

    if responseStatus == "accepted":
        payloadDict = json.loads(payload)
        print("~~~~~~~~~~~~~~~~~~~~~~~")
        print("Update request with token: " + token + " accepted!")
        print("temperature: " + str(payloadDict["state"]["reported"]["temp"]))
        print("~~~~~~~~~~~~~~~~~~~~~~~\n\n")

    if responseStatus == "rejected":
        print("Update request " + token + " rejected!")

# Function called when a shadow is deleted
def customShadowCallback_Delete(payload, responseStatus, token):

     # Display status and data from delete request
    if responseStatus == "timeout":
        print("Delete request " + token + " time out!")

    if responseStatus == "accepted":
        print("~~~~~~~~~~~~~~~~~~~~~~~")
        print("Delete request with token: " + token + " accepted!")
        print("~~~~~~~~~~~~~~~~~~~~~~~\n\n")

    if responseStatus == "rejected":
        print("Delete request " + token + " rejected!")


# Read in command-line parameters
def parseArgs():

    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--endpoint", action="store", required=True, dest="host", help="Your AWS IoT custom endpoint")
    parser.add_argument("-r", "--rootCA", action="store", required=True, dest="rootCAPath", help="Root CA file path")
    parser.add_argument("-c", "--cert", action="store", dest="certificatePath", help="Certificate file path")
    parser.add_argument("-k", "--key", action="store", dest="privateKeyPath", help="Private key file path")
    parser.add_argument("-p", "--port", action="store", dest="port", type=int, help="Port number override")
    parser.add_argument("-n", "--thingName", action="store", dest="thingName", default="Bot", help="Targeted thing name")
    parser.add_argument("-id", "--clientId", action="store", dest="clientId", default="basicShadowUpdater", help="Targeted client id")

    args = parser.parse_args()
    return args


# Configure logging
# AWSIoTMQTTShadowClient writes data to the log
def configureLogging():

    logger = logging.getLogger("AWSIoTPythonSDK.core")
    logger.setLevel(logging.DEBUG)
    streamHandler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    streamHandler.setFormatter(formatter)
    logger.addHandler(streamHandler)

# Parse command line arguments
args = parseArgs()

if not args.certificatePath or not args.privateKeyPath:
    parser.error("Missing credentials for authentication.")
    exit(2)

# If no --port argument is passed, default to 8883
if not args.port: 
    args.port = 8883


# Init AWSIoTMQTTShadowClient
myAWSIoTMQTTShadowClient = None
myAWSIoTMQTTShadowClient = AWSIoTMQTTShadowClient(args.clientId)
myAWSIoTMQTTShadowClient.configureEndpoint(args.host, args.port)
myAWSIoTMQTTShadowClient.configureCredentials(args.rootCAPath, args.privateKeyPath, args.certificatePath)

# AWSIoTMQTTShadowClient connection configuration
myAWSIoTMQTTShadowClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTShadowClient.configureConnectDisconnectTimeout(10) # 10 sec
myAWSIoTMQTTShadowClient.configureMQTTOperationTimeout(5) # 5 sec

# Connect to AWS IoT
myAWSIoTMQTTShadowClient.connect()

# Create a device shadow handler, use this to update and delete shadow document
deviceShadowHandler = myAWSIoTMQTTShadowClient.createShadowHandlerWithName(args.thingName, True)

# Delete current shadow JSON doc
deviceShadowHandler.shadowDelete(customShadowCallback_Delete, 5)

# Read data from temperature sensor and update shadow
while True:
    # read temperature from the temperature sensor
    tempStatus, temp = read1WTemp()
    if(tempStatus):
        # Display temp readings
        print("Temperature: {}".format(temp))
    
        # Create message payload
        payload = {"state":{"reported":{"temp":str(temp)}}}

        # Update shadow
        deviceShadowHandler.shadowUpdate(json.dumps(payload), customShadowCallback_Update, 5)
    else:
        print("Read Temp failed\n")
    time.sleep(1)

# Example
# python3 tempSensor.py --endpoint yourEndpoint --rootCA certs/Amazon-root-CA-1.pem --cert certs/device.pem.crt --key certs/private.pem.key --thingName MyIotThing --clientId RaspberryPi