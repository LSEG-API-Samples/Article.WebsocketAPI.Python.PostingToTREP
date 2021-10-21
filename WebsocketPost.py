# -*- coding: utf-8 -*-
"""
Created on Thu May 23 15:40:42 2019

@author: Umer Nalla, Refinitiv
"""

#|-----------------------------------------------------------------------------
#|            This source code is provided under the Apache 2.0 license      --
#|  and is provided AS IS with no warranty or guarantee of fit for purpose.  --
#|                See the project's LICENSE.md for details.                  --
#|           Copyright Refinitiv 2021. All rights reserved.            --
#|-----------------------------------------------------------------------------


#!/usr/bin/env python
""" Simple example of posting Market Price JSON data using Websockets """

import time
import socket
import json
import websocket
import threading
import os
import random

# Global Default Variables
user = 'umer.nalla'
app_id = '256'
position = socket.gethostbyname(socket.gethostname())

# Global Variables
web_socket_app = None
web_socket_open = False
logged_in = False
shutdown_app = False
post_id = 1 # use unique Post ID for each Post message, so we can correlate with ACK msg

def process_message(ws, message_json):
    global shutdown_app

    """ Extract Message Type and Domain"""
    message_type = message_json['Type']
    if 'Domain' in message_json:
        message_domain = message_json['Domain']
    # check for a Login Refresh response to confirm successful login
    if message_type == "Refresh" and message_domain == "Login":
        global logged_in
        logged_in = True
        print ("LOGGED IN")
    elif message_type == "Ping":
        pong_json = { 'Type':'Pong' }
        ws.send(json.dumps(pong_json))
        print("SENT:")
        print(json.dumps(pong_json, sort_keys=True, indent=2, separators=(',', ':')))
    elif message_type == "Status" and message_domain == "Login":
        # A Login Status message usually indicates a problem - so report it and shutdown
        if message_json['State']['Stream'] != "Open" or message_json['State']['Data'] != "Ok":
            print("LOGIN REQUEST REJECTED.")
            shutdown_app = True
    elif message_type == "Error":
            shutdown_app = True

def send_mp_offstream_post(svc,riccode, fields, refresh = False):
    global post_id
    """ Send an off-stream post message containing market-price content """
    mp_post_json = {
        'ID': 1,
        'Type':'Post',
        'Key': {
            'Service': svc,
            'Name': riccode
        },
        'Ack':True,
        'PostID':post_id,
        'Message': {
            'ID': 0,
            'Type':'Refresh' if refresh else 'Update',
            'Fields':fields
        }
    }

    # If sending a Refresh type Message, indicate this Post was un-solicited
    # and also set Stream + Data state to Open and OK respectively
    if refresh:
        mp_post_json['Message']['Solicited'] = False
        mp_post_json['Message']['State']= {'Stream': 'Open','Data': 'Ok'}

    web_socket_app.send(json.dumps(mp_post_json))
    print("SENT:")
    print(json.dumps(mp_post_json, sort_keys=True, indent=2, separators=(',', ':')))
    
    # the AckID in the AckMsg we get back will correspond to the above PostID
    # now increment it for the next Post
    post_id += 1

def send_login_request(ws):
    """ Generate a login request and send """
    login_json = {
        'ID': 1,
        'Domain': 'Login',
        'Key': {
            'Name': user,
            'Elements': {
                'ApplicationId': app_id,
                'Position': position
            }
        }
    }

    ws.send(json.dumps(login_json))
    print("SENT:")
    print(json.dumps(login_json, sort_keys=True, indent=2, separators=(',', ':')))


def on_message(ws, message):
    """ Called when message received, parse message into JSON for processing """
    
    print("RECEIVED: ")
    message_json = json.loads(message)
    print(json.dumps(message_json, sort_keys=True, indent=2, separators=(',', ':')))

    # if Msg Packing is enabled on the server(Default setting)
    # you can receive multiple JSON messages within a single Websocket message
    for singleMsg in message_json:
        process_message(ws, singleMsg)


def on_error(ws, error):
    """ Called when websocket error has occurred """
    print(error)
    global shutdown_app
    shutdown_app = True

def on_close(ws):
    """ Called when websocket is closed """
    global web_socket_open
    print("WebSocket Closed")
    web_socket_open = False

def on_open(ws):
    """ Called when handshake is complete and websocket is open, send login """
    print("WebSocket successfully connected!")
    global web_socket_open
    web_socket_open = True
    send_login_request(ws)

def connect(hostname, port, username, pos = socket.gethostbyname(socket.gethostname()), appid = 256):
    """ Called to connect to server """
    global app_id, user, position,web_socket_app
    # appid may be allocated by your Market Data team, otherwise default to 256
    app_id = appid
    user = username
    position = pos

    # Start websocket handshake
    ws_address = "ws://{}:{}/WebSocket".format(hostname, port)
    print("Connecting to WebSocket " + ws_address + " ...")
    web_socket_app = websocket.WebSocketApp(ws_address, header=['User-Agent: Python'],
                                        on_message=on_message,
                                        on_error=on_error,
                                        on_close=on_close,
                                        subprotocols=['tr_json2'])
    
    # callback for once websocket is open - which will send the Login request
    web_socket_app.on_open = on_open

    # Create Thread for WebsocketApp processing
    wst = threading.Thread(target=web_socket_app.run_forever)
    wst.start()

    return web_socket_app

if __name__ == "__main__":

    #Create Websocket Connection to the ADS 
    wsa = connect("myADS",15000, "umer.nalla")    
    
    print ("Waiting for Login response")
    try:
        while not logged_in and (not shutdown_app):
            time.sleep(1)
    except KeyboardInterrupt:
            wsa.close()


    # Logged in 
    if logged_in:
        svcname = "NIPROV"  # Service to Post on - Check with your Market Data team for correct value
        ric = "UMER.TST"    # RIC to Post / Contribute data to - Check with your Market Data team 
        bid = 22.1          # dummy starting values
        ask = 24.5
        trdprc = 23.3
        
        # Use a python dict to store our FieldName(key) + Value pairs
        fields = { 'BID' : bid, 'ASK' : ask, 'TRDPRC_1' : trdprc,'GEN_TEXT16' : 'some text' }
        print ("Ready to Post")
        # Send our Refresh message to create the RIC or refresh the fields of an existing RIC
        send_mp_offstream_post(svcname,ric, fields, True)

        # You would replace the following code with something more realistic to Post values as and when required
        # Get ready to generate some random numbers to contribute for our price field values
        secure = random.SystemRandom()
        # set delay to send our next post with random values
        next_post_time = time.time() + 10
        
        try:
            while web_socket_open and logged_in and (not shutdown_app):
                time.sleep(1)
                # When ready to post next updates, generate some more random values
                if next_post_time != 0 and time.time() > next_post_time:
                    bid = round(bid + secure.uniform(0.3, 0.5),2)
                    trdprc = round(bid + secure.uniform(0.2, 0.5),2)
                    ask = round(trdprc + secure.uniform(0.6, 0.9),2)
                    fields = { 'BID' : bid, 'ASK' : ask, 'TRDPRC_1' : trdprc }
                    # Send an Update message with our updated price field values
                    send_mp_offstream_post(svcname,ric,fields)
                    # set random time for next post
                    next_post_time = time.time() + random.randint(5,30)
        except KeyboardInterrupt:
            pass
        finally:
            wsa.close()
    else:
        wsa.close()



