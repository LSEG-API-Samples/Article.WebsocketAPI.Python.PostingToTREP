# Contributing Data using the Websocket API

> *"I don't want to learn an API, I just want to publish some data to Refinitiv"*

During my time on client site, I often come across a class of developer who has no need to consume Refinitiv data. They are the owners of some internally generated real-time data and they want to share that data - either for internal or external consumption by other users - but don't want to learn an API in order to share the data.

If you are one of these developers or just want to learn about contributing data to Refinitiv, carry on reading....

## Data Contribution 
Often an organisation will generate some pricing data or other values which they want to share externally with the financial markets and/or internally with their own users.

The price or other type of data is generated internally and is then submitted to the Refinitiv real-time enterprise platform - TREP. 

If it's for internal consumption only, the values will stored in a internal real-time cache - from which internal users can consume the data by requesting the relevant instrument using the internally communicated RICs (instrument names).

If it's for external consumption, the TREP system will forward the value to a contribution engine which will take care of forwarding the value to Refinitiv, who will do the necessary to publish the price on their Elektron real-time feed. External users of Elektron can then consume the data by requesting the relevant RIC codes.

I used the word '*publish*' in the opening line, but then use the term contribute thereafter. This is because many developers talk about publishing when they mean contribute. In the TREP world, '*publishing*' means something different which is outside the scope of this guide. 

## Posting (or Inserting) data
The programmatic functionality used for contributing data is referred to as ***Posting*** - and was also referred to as ***Inserting*** with our legacy APIs.

Until recently, if you wanted to perform a Post (or an Insert), you would have to spend some time learning one of our APIs in order to carry out the necessary steps to
 * Connect to the server
 * Login with your credentials
 * Encode the payload for Post into an API specific object / format
 * Submit the Post to the server
 * Optionally process an acknowledgement message to confirm the Post was accepted

 Many of these client developers would just take a sample application and just hack it for their Contribution needs - but would not have the time to understand how that application worked.
 
 With our new Websocket interface, which is exposed on recent versions of our TREP system, this process has become much simpler. You do not need to learn API specifics - you can use standards based Websocket connectivity and JSON formatting.  
 There is some Refinitiv specific knowledge you will need to appreciate - namely the format of the JSON message you need to encode for the server Login request and the format of the Post message payload itself.  
 
 Although you can use any programming language which supports JSON and websocket connectivity, I am going to use Python in this guide.
 
 ## Prerequisites
 In order to work through this guide and successfully post some data to either Refinitiv or your internal cache, you will need the following on your PC:
  * Python installation - I have tested my code below with Python v3.7  
  * The 'websocket-client' Python module installed
  * Download of the example source code attached to this article
  
 You will also need to obtain the following from your internal Market Data team:
  * Access to TREP a system with a v3.2.1 or higher version of the ADS component (the server you will connect to)
  * The `Hostname` for the ADS and the `Port` number for the websocket interface on the ADS
  * A `DACS username` with the correct permissions to Post (contribute) data to the following:
     * The name of a `Service` (source) to Post to
     * One or more test `RICs` (instrument names) that you can Post to safely  

## Getting connected & Logged in

Assuming you have met all the above prerequisites, the first thing we need to do is to establish a Websocket connection to the ADS server.

### Create Websocket connection to server

We want to create a *long-lived* connection to the server so we use WebSocketApp (from the `websocket-client` module) which is a wrapper around the Websocket that provides an *event driven* interface. 

We do this by calling the `connect()` method I have defined in my example:

```python
    wsa = connect("myADS",15000, "umer.nalla")    
```
I am passing in the hostname of `myADS`, port number `15000` and my `DACS` username. The username is not required at this point, but the method will store this in a global variable for use later. You will obviously need to replace these values with the ones you have obtained from your Market Data team.

```python
   def connect(hostname, port, username, pos = socket.gethostbyname(socket.gethostname()), appid = 256):
    
    """ Called to connect to server """
    
    global app_id, user, position,web_socket_app
    # appid may be allocated by your Market Data team, otherwise default to 256
    app_id = appid
    user = username
    position = pos
    # the above values are stored for later usage when we attempt login.

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
```

The first thing to note is the connection address `ws_address` is formed using the hostname and port e.g. `myADS:15000` where `myADS` is the hostname and `15000` is the port on which the ADS is listening for websocket connection requests.

Next we create a `WebsocketApp` instance and provide the callback methods that will be called for the following events types:

* Once the websocket is open – `on_open`
* When the websocket is closed– `on_close`
* If an error occurs – `on_error`
* When messages are received from the ADS – `on_message`

Note also that we set the `subprotocols` as `tr_json2` – to ensure that the `Sec-WebSocket-Protocol` header value of the Websocket connection is `tr_json2` - which is what the ADS is expecting.

If you decide to use a different websocket library / language the above code will no doubt vary somewhat - but the key points is that we need to handle the above event types.

Once we call the above connect method, we then wait for the websocket connection to be established and a successful login response:
```python
print ("Waiting for Login response")
 while not logged_in and (not shutdown_app):
     time.sleep(1)
```

### Login to ADS once Websocket is open

Once the websocket connection between our application and the ADS is established, the first thing we want to do is send a Login Request to the ADS.

```python
def on_open(ws):
    """ Called when handshake is complete and websocket is open. Now send login """
    global web_socket_open
    web_socket_open = True
    send_login_request(ws)
```

So, once the websocket is open, the `on_open` callback should be invoked by the WebSocketApp. Here we set a global flag to indicate the websocket is open and then encode and send a JSON Login Request message to the ADS.

```python
def send_login_request(ws, is_refresh_token=False):
    """ Generate a login request and send """
    # Set values for TREP login
    # Note StreamID is 1 and the Domain is Login
    login_json = {
        'ID': 1,
        'Domain': 'Login',
        'Key': {
            'Name': '',
            'Elements': {
                'ApplicationId': '',
                'Position': ''
            }
        }
    }

    login_json['Key']['Name'] = user
    login_json['Key']['Elements']['ApplicationId'] = app_id
    login_json['Key']['Elements']['Position'] = position
    
     ws.send(json.dumps(login_json))
```

So we create a JSON object and set the following values:

* Stream `ID` – Unique identifier for each request (& response) between your application and server, use value of 1 for the Login request
* Username – often referred to as a `DACS` username (DACS is the authentication and entitlement system used by TREP).
* ApplicationID – value allocated by your Market Data team, otherwise use default value of 256
* Position – the local IP address / hostname of the PC that the application is running on

Some organisations DACS policy insist on a non-default ApplicationID to perform a successful login – so please check with your Market Data team on the requirements.

We then send the JSON message over the websocket to the ADS.

The outgoing `login_json` object should look something like:

```json
"Domain":"Login",
  "ID":1,
  "Key":{
    "Elements":{
      "ApplicationId":"256",
      "Position":"101.43.2.193"
    },
    "Name":"umer.nalla"
  }
```

Once the Login request has been sent, we can expect an asynchronous response from the server in the form of a JSON message over the Websocket.

A successful **Login Refresh message** from ADS will look something like:
```json
"Domain":"Login",
 "Elements":{
   "MaxMsgSize":61430,
   "PingTimeout":30
 },
 "ID":1,
 "Key":{
   "Elements":{
     "AllowSuspectData":1,
     "ApplicationId":"256",
     "SupportViewRequests":1
   },
   "Name":"umer.nalla"
 },
 "State":{
   "Data":"Ok",
   "Stream":"Open",
   "Text":"Login accepted by host centos7-2."
 },
 "Type":"Refresh"
```
A few things to note:
* Stream `ID` of 1 which corresponds to the value we used in the Login Request Message
* `Data` State of `OK` and `Stream` State of `Open` - confirmation the login request was accepted
* Type value of `Refresh` - the ADS sends a `Refresh` as the initial response to a successful request

If the Login Request was rejected by the ADS we would see something like:
```json
{
   "ID": 1,
   "Type": "Status",
   "Domain": "Login",
   "Key": {
     "Name": "fred"
   },
   "State": {
     "Stream": "Closed",
     "Data": "Suspect",
     "Code": "UserUnknownToPermSys",
     "Text": "fred, unknown to system."
   }
 }
```
So, for a failed Login, note the following:
* Stream `ID` of 1 as per the Login Request we sent
* `Type` is `Status` (as opposed to Refresh)
* `Stream` State is `Closed` (not Open)
* `Data` State is `Suspect` (not OK)

IF you do receive a Status type response, then contact your internal Market Data team with the details of the Status message including the `Code` and `Text` values.

If you recall, we previously specified a callback to handle messages we receive over the websocket: 
```python
def on_message(ws, message):
    """ Called when message received, parse message into JSON for processing """
    print("RECEIVED: ")
    message_json = json.loads(message)
    print(json.dumps(message_json, sort_keys=True, indent=2, separators=(',', ':')))
    for singleMsg in message_json:
        process_message(ws, singleMsg)
```
By default the ADS can send more than one JSON message within a single websocket message. So, we iterate through each one and call the `process_message` method for each one:
```python
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
```
The `process_message` method is doing a few things based on the message type:
* If a `Refresh` type message is received, we set the `logged_in` flag to indicate a successful login.
* If a `Status` or `Error` message is received we mark the application for a shutdown. 
* When the ADS sends us a `Ping` message, we send a `Pong` response - to confirm that application is  still running.

Assuming a successful Login response, back in the `_main_` method, the wait loop should have exited as a result of `logged_in` flag being set to True.
So, we can now go ahead and start Posting data to the ADS.

## Posting Data to the ADS

As I mentioned at the start, this guide is addressing developers who do not need to consume any data from TREP - just Post. The appropriate Posting technique for this type of requirement is known as '**Off-Stream Posting**'. For developers who want to consume the instruments they are Posting to, there is also a technique known as 'On-Stream Posting' - see end of this guide for a link to a tutorial which covers both techniques.

In computer science the term stream is typically defined as something like 'a sequence of data items made available over a period of time - with each item arriving individually (rather than in a batch)'

When we logged into the ADS we established a Stream with an ID of 1 - i.e. any Login related data between the application and the ADS would be identified with an ID of 1. 

### Off-Stream Posting

For an **Off-Stream Post** we don’t need to subscribe to (and open a stream for) the item we want to post to. Indeed the item may not even exist and we may want to use the Post to create the item. 

Instead we are going to use the one stream we already have open - i.e. the Login stream to send our Posts.

So, assuming the login request was successful  – we can send an Off-Stream Post using the Login Stream ID of 1.

```python
svcname = "NIPROV"  # Service to Post on - Check with your Market Data team for correct value
ric = "UMER.TST"    # RIC to Post / Contribute data to - Check with your Market Data team for Test RICs

bid = 22.1          # A few dummy starting values
ask = 24.5
trdprc = 23.3

# Use a python dict to store our FieldName(key) + Value pairs
fields = { 'BID' : bid, 'ASK' : ask, 'TRDPRC_1' : trdprc, 'GEN_TEXT16' : 'some text' }

# Send our Refresh message to create the RIC or refresh the fields of an existing RIC
send_mp_offstream_post(svcname,ric, fields, True)

```
In the above code we specify our service name, test RIC code, we create a dict with a few fields with dummy values and then we call our method to send a Refresh type post.

```python
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
        'PostUserInfo': {       # Ask you Market Data team if this is mandated by your organisation
            'Address':position,  # Use IP address as the Post User Address.
            'UserID':os.getpid() # Using process ID as the Post User Id - your MD team may provide an actual ID
        },
        'Message': {
            'ID': 0,
            'Type':'Refresh' if refresh else 'Update',
            'Fields':fields
        }
    }
```
The first thing to note is that there is an outer Post type message, containing an internal Refresh Type message. In addition to this, note the following:
* Stream `ID` of 1 - i.e. the Login Stream which should be open
* `Type` of `Post` of the outer message
* The Key consists of 
    * `Service` as provided by your Market Data team
    * `Name` - the RIC code of the instrument to Post, as provided by your Market Data team 
* `Ack` = true to request an Acknowledgement from the ADS for this Post
* `PostID` - this value should be unique for each Post we send - we can extract it from the Ack responses to identify which Post the Ack relates to. 
* `PostUserInfo` - an `Address` and `UserID` may be required by your organisation for audit purpose (otherwise you can omit these values)
* The inner `Message` contains the actual data you wish to Post 
  * `ID` is 0 - we are Posting a value and so we don't need to establish a new Stream
  * `Type` - to create a new item or refresh all fields this should be set to `Refresh` - otherwise use `Update` with a partial set of fields
  * `Fields` - provide a dict containing the field name (key) + value pairs for the fields you want to contribute data to

Calling the above method should result in the following JSON message being sent to the ADS:
```json
{
  "Ack":true,
  "Domain":"MarketPrice",
  "ID":1,
  "Key":{
    "Name":"UMER.TST",
    "Service":"NIPROV"
  },
  "Message":{
    "Fields":{
      "ASK":24.5,
      "BID":22.1,
      "GEN_TEXT16":"some text",
      "TRDPRC_1":23.3
    },
    "ID":0,
    "Solicited":false,
    "State":{
      "Data":"Ok",
      "Stream":"Open"
    },
    "Type":"Refresh"
  },
  "PostID":1,
  "PostUserInfo":{
    "Address":"10.44.12.152",
    "UserID":7408
  },
  "Type":"Post"
}
```
Assuming the Post is accepted, we should get an asynchronous Ack response from the ADS:
````json
{
    "AckID":1,
    "ID":1,
    "Key":{
      "Name":"UMER.TST",
      "Service":"NIPROV"
    },
    "Type":"Ack"
}
````
Note the AckID of 1 which corresponds to the **PostID** of 1 we specified in the Post message we just sent to the server. We can use this value to identify which Post the Ack relates to. Therefore, we should use unique PostIds for each Post message we send.

As this is just an example, the rest of the \__main__ method simply sends Update type messages with random price values at a timed interval. Obviously, you will send the Refresh and Updates as and when required. 

### Post a Refresh or an Update?

In the example above I initially posted a Refresh, follows by Updates at time intervals – purely for demonstration purposes. However, your choice of which to use will depend on your requirements:

* If you want to create a new item in the cache service you can Post a Refresh payload  
* To add or remove the actual Fields contained within an item you would Post a Refresh with the revised Field list  
* If you experienced some temporary data issue which is now resolved and want to force consumers to overwrite any locally cached fields, send a Refresh. This ensures any existing consumers of your data get a clean set of values for all the fields  
* To change values for one or more fields of an existing item you can Post an Update payload  

Note that if we try to post an Update to a non-existent item we will get an **Ack** response but with a **NakCode** e.g. if we try to post to a non-existent RIC ‘DAVE.TST’ we get:

```json
{
    "ID": 1,
    "Type": "Ack",
    "AckID": 1,
    "NakCode": "SymbolUnknown",
    "Text": "F44: Unable to find item on post update.",
    "Key": {
      "Service": "NIPROV",
      "Name": "DAVE.TST"
    }
  }
```

That concludes this guide - to summarise:
* If you want to Contribute data to an internal cache or to Refinitiv, without the need to consume data you can use the Websocket interface to achieve this in a relatively straightforward manner
* If you want to Consume and Contribute data, you can still apply much of the above learning to achieve this by using On-Stream Posts - as described in the Tutorial link below
* You should be able to implement the above using any language which supports Websockets and the ability to encode JSON messages


### References

<a href="https://developers.refinitiv.com/elektron/websocket-api/learning?content=63483&type=learning_material_item" target="_blank">Websocket API tutorials</a>  
<a href="https://developers.refinitiv.com/elektron/websocket-api/learning?content=63573&type=learning_material_item" target="_blank">Contributing Data to TREP tutorial</a> - which include **On-Stream** Posting.


