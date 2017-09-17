import os
import sys
import json
import threading
import time
import requests
from flask import Flask, request
from datetime import datetime

app = Flask(__name__)
app.config.from_pyfile('settings.cfg')  # load tokens from env

amadeus_key = app.config["AMADEUS_API_KEY"]

@app.route('/', methods=['GET'])

class POI:

	def __init__(self, location, time):
		self.location = location
		self.time = time
        self.completed = False
		self.feedback = {
			'emotion': '',
			'adjective':'',
			'memory':''
		}

class Trip:

	def __init__(self, name):
		self.tripName = name
		self.visits = []

    def addLocation(self, location, time):
        poi = POI(location, time)
        visits.append(poi)
        visits.sort(key = lambda x: x.time)
        
nextEvent = None

def runSchedule():
    while True:
        if nextEvent is None:
            time.sleep(1)
        else:
            while datetime.datetime.now() < nextEvent.time:
                time.sleep(1)
            runEvent(nextEvent)
            nextEvent = None

scheduleThread = threading.Thread(target = runSchedule)
scheduleThread.start()
    
		

def verify():
    # when the endpoint is registered as a webhook, it must echo back
    # the 'hub.challenge' value it receives in the query arguments
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == app.config["VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world", 200

# app states by userID
_state = {}
_current_logistics = {}


# message handlers

def handle_text(sender_id, user_state, message_text):
    # start anew
    if user_state == -1:
        send_message(sender_id, 'uwau ~ i am tripbot-chan nyaa! \nto start planning a trip, say "start trip" :3')
        _state[sender_id] = 0
    # user is greeted
    elif user_state == 0:
        if message_text.rstrip().lower() == 'start trip':
            send_message(sender_id, 'where would you like to go? send a location pin owo')
        else:
            send_message(sender_id, "that's not a valid command nyaa >:(")
    # destination entered, awaiting dates
    elif user_state == 2:
        dates = message_text.rstrip().split(" ")
        if len(dates) != 2:
            send_message(sender_id, "please enter two dates >:(")
        else:
            try:
                start_date = datetime.strptime(dates[0], '%m/%d/%y')
                end_date = datetime.strptime(dates[1], '%m/%d/%y')
            except ValueError:
                send_message(sender_id, "please format your dates correctly baka >:(")
            else:
                if end_date < start_date:
                    send_message(sender_id, "aho, you can't go back in time >:(")
                else:
                    # store dates
                    _current_logistics[sender_id]["start_date"] = start_date
                    _current_logistics[sender_id]["end_date"] = end_date
                    send_message(sender_id, "would you like to search for flights or points of interest?")
                    _state[sender_id] = 3 
    # flights or PoI?
    elif user_state == 3:
        if 'flights' in message_text.lower():
            # flights = findFlights(
            #         _current_logistics[sender_id]["origin"][0], _current_logistics[sender_id]["origin"][1],
            #         _current_logistics[sender_id]["destination"][0], _current_logistics[sender_id]["destination"][1],
            #         _current_logistics[sender_id]["start_date"], _current_logistics[sender_id]["end_date"]
            #     )
            send_message(sender_id, "zoooooom")
        elif 'poi' in message_text.lower():
            send_message(sender_id, "what is the maximum distance (in miles) you are willing to travel from your destination pin?")
            _state[sender_id] = 3.5
    # setting PoI radius
    elif user_state == 3.5:
        if message_text.isdigit():
            radius = int(float(message_text) / 1.609344)
            _current_logistics[sender_id]["radius"] = radius
            raw_points = findPOI(_current_logistics[sender_id]["destination"][0], _current_logistics[sender_id]["destination"][1], radius)
            points = map(
                lambda point: {
                    "title" : point["title"], "grade" : point["grades"]["yapq_grade"], "short_description": point["details"]["short_description"]
                },
                raw_points
            )
            _current_logistics[sender_id]["points"] = points
            for i in xrange(len(points)):
                send_message(sender_id,
                    ("%s. %s (%s/5 stars):\n%s" % (str(i + 1), points[i]["title"], str(points[i]["grade"]), points[i]["short_description"]))
                )
            

def handle_attachments(sender_id, user_state, message):    
    # Location
    if message["attachments"][0]["type"] == "location":
        if user_state == 0:
            location = message["attachments"][0]["payload"]["coordinates"]
            _state[sender_id] = 1
            # store destination location
            _current_logistics[sender_id] = {"destination" : (location["lat"], location["long"])}
            send_message(sender_id, 
                "your desired destination is (" + str(location["lat"]) + ", " + str(location["long"]) + ").\n\n" + 
                'where will you be traveling from?')
        elif user_state == 1:
            location = message["attachments"][0]["payload"]["coordinates"]
            _state[sender_id] = 2
            # store origin location
            _current_logistics[sender_id]["origin"] = (location["lat"], location["long"])
            send_message(sender_id, 
                "your desired origin is (" + str(location["lat"]) + ", " + str(location["long"]) + ").\n\n" + 
                'what are your preferred leaving and returning dates? (format as "MM/DD/YY MM/DD/YY")')



@app.route('/', methods=['POST'])
def webhook():

    # endpoint for processing incoming messaging events

    data = request.get_json()
    # log(data)  # you may not want to log every incoming message in production, but it's good for testing
    print "-----------------------------\n"

    if data["object"] == "page":
        for entry in data["entry"]:
            for event in entry["messaging"]:
                if event.get("message"):  # someone sent us a message

                    # log(event)

                    sender_id = event["sender"]["id"]        # the facebook ID of the person sending you the message
                    recipient_id = event["recipient"]["id"]  # the recipient's ID, which should be your page's facebook ID
                    message = event["message"]

                    # print type(sender_id)
                    if sender_id == '143661809573052':
                        continue

                    # If new user, add them to state mapping
                    if sender_id not in _state:
                        _state[sender_id] = -1

                    # Grab current user's current state
                    user_state = _state[sender_id]

                    # Text Message
                    if "text" in message:
                        message_text = message["text"]  # the message's text

                        print 'message:', message_text

                        # Branch based on user state
                        handle_text(sender_id, user_state, message_text)

                    # Attachments
                    elif "attachments" in message:
                        handle_attachments(sender_id, user_state, message)

                # do we even need these
                if event.get("delivery"):  # delivery confirmation
                    pass
                if event.get("optin"):  # optin confirmation
                    pass
                if event.get("postback"):  # user clicked/tapped "postback" button in earlier message
                    pass

    return "ok", 200


def send_message(recipient_id, message_text):

    log("sending message to {recipient}: {text}".format(recipient=recipient_id, text=message_text))

    params = {
        "access_token": app.config["PAGE_ACCESS_TOKEN"]
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    })
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
    if r.status_code != 200:
        log(r.status_code)
        log(r.text)


def log(message):  # simple wrapper for logging to stdout on heroku
    print str(message)
    sys.stdout.flush()

def findAirport(lat, lon):
    nearest_airport_url = 'https://api.sandbox.amadeus.com/v1.2/airports/nearest-relevant'
    payload = {
        'apikey': amadeus_key,
        'latitude': lat,
        'longitude': lon
    }
    return r.json()[0]['airport']

def findFlights(lat_start, long_start, lat_end, long_end, start_date, end_date):
    low_fare_url = 'https://api.sandbox.amadeus.com/v1.2/flights/low-fare-search'
    start_airport = findAirport(lat_start, long_start)
    end_airport = findAirport(lat_end, long_end)
    payload = {
        'apikey': amadeus_key,
        'origin': start_airport,
        'destination': end_airport,
        'departure_date': start_date,
        'return_date': end_date
    }
    r = requests.get(low_fare_url, params = payload)
    return r.json()

def findPOI(lat, lon, radius):
    geosearch_url = 'https://api.sandbox.amadeus.com/v1.2/points-of-interest/yapq-search-circle'
    max_results = 5
    payload = {
        'apikey': amadeus_key,
        'latitude': lat,
        'longitude': lon,
        'radius': radius,
        'number_of_results': max_results
    }
    r = requests.get(geosearch_url, params = payload)
    return r.json()['points_of_interest']
    
    


if __name__ == '__main__':
    app.run(debug=True)
