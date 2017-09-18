import os
import sys
import json
import threading
import time
import requests
from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

amadeus_key = os.environ["AMADEUS_API_KEY"]

next_event = None

class POI:

    def __init__(self, location, time, trip):
        self.location = location
        self.time = time
        self.completed = False
        self.trip = trip
        self.feedback = {
            'emotion': '',
            'adjective': '',
            'memory': ''
        }

    def add_feedback(self, classification, answer):
        self.feedback[classification] = answer

    def mark_complete(self):
        self.completed = True

class Trip:

    def __init__(self, name, user_id):
        self.trip_name = name
        self.visits = []
        self.user = user_id

    def add_location(self, location, time):
        poi = POI(location, time, self)
        global next_event
        if next_event is None:
            next_event = poi
        elif next_event.completed:
            next_event = poi
        elif poi.time < next_event.time:
            next_event = poi
        self.visits.append(poi)
        self.visits.sort(key = lambda x: x.time)
        
all_trips = {}
current_trip = {}


    
		

@app.route('/', methods=['GET'])
def verify():
    # when the endpoint is registered as a webhook, it must echo back
    # the 'hub.challenge' value it receives in the query arguments
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Nyaa ~", 200

# app states by userID
_state = {}
_current_logistics = {}

def check_completed_trip(sender_id):
    completed = True
    trip = current_trip[sender_id]
    for poi in trip.visits:
        if not poi.completed:
            completed = False
            break
    return completed

def run_event():
    send_message(next_event.trip.user, 'Congrats! You visisted ' + next_event.location)
    # TODO: randomize question asked
    send_message(next_event.trip.user, 'How did you feel about your experience?')
    _state[next_event.trip.user] = 5.5
    _current_logistics[next_event.trip.user]['type'] = 'emotion'
    _current_logistics[next_event.trip.user]['current_poi'] = next_event
    
    _state[next_event.trip.user] = 5.5
    #handle_text(next_event.trip.user, _state[next_event.trip.user], "")
    

def select_next_event():
    global next_event
    for key, value in current_trip.iteritems():
        for poi in value.visits:
            if next_event is None or (poi.time < next_event.time and not poi.completed):
                next_event = poi

def run_schedule():
    while True:
        if next_event is None:
            time.sleep(1)
        else:
            while datetime.datetime.now() < next_event.time:
                time.sleep(1)
            run_event()
            next_event = None

schedule_thread = threading.Thread(target = run_schedule)
schedule_thread.start()

def format_flight(result):
    outbound_flight = result["itineraries"][0]["outbound"]["flights"][0]
    outbound_time = outbound_flight["departs_at"]
    outbound_loc = outbound_flight["origin"]["airport"]
    outbound_dest = outbound_flight["destination"]["airport"]
    outbound_flightnum = outbound_flight["marketing_airline"] + " " + outbound_flight["flight_number"]

    inbound_flight = result["itineraries"][0]["inbound"]["flights"][0]
    inbound_time = inbound_flight["departs_at"]
    inbound_loc = inbound_flight["origin"]["airport"]
    inbound_dest = inbound_flight["destination"]["airport"]
    inbound_flightnum = inbound_flight["marketing_airline"] + " " + inbound_flight["flight_number"]

    total_price = result["fare"]["total_price"]

    return "%s-->%s at %s on Flight# %s\n%s-->%s at %s on Flight# %s\nTotal Cost: $%s" % (
        outbound_loc, outbound_dest, outbound_time, outbound_flightnum,
        inbound_loc, inbound_dest, inbound_time, inbound_flightnum,
        total_price
    )

# message handlers

def handle_text(sender_id, user_state, message_text):
    if message_text.rstrip().lower() == 'restart':
        _state[sender_id] = -1
        user_state = -1
        send_message(sender_id, 'Restarted!')
    # start anew
    if user_state == -1:
        send_message(sender_id, 'Meow ~ I am TravelCat! \nTo start planning a trip, say "start trip"')
        _state[sender_id] = 0
    # user is greeted
    elif user_state == 0:
        if message_text.rstrip().lower() == 'start trip':
            send_message(sender_id, 'What would you like to call this trip?')
            _state[sender_id] = 0.5
        else:
            send_message(sender_id, "That's not a valid command nyaa >:(")
    elif user_state == 0.5:
        name = message_text.rstrip()
        trip = Trip(name, sender_id)
        current_trip[sender_id] = trip
        if sender_id not in all_trips:
            all_trips[sender_id] = [trip]
        elif all_trips[sender_id] is None:
            all_trips[sender_id] = [trip]
        else:
            all_trips[sender_id] = all_trips[sender_id].append(trip)
        send_message(sender_id, 'Mrow ~ where would you like to go? Send a location pin!')
    # destination entered, awaiting dates
    elif user_state == 2:
        dates = message_text.rstrip().split(" ")
        if len(dates) != 2:
            send_message(sender_id, "Please enter two dates >:(")
        else:
            try:
                start_date = datetime.strptime(dates[0], '%m/%d/%y')
                end_date = datetime.strptime(dates[1], '%m/%d/%y')
            except ValueError:
                send_message(sender_id, "Please format your dates correctly >:(")
            else:
                if end_date < start_date:
                    send_message(sender_id, "Aho, you can't go back in time >:(")
                else:
                    # store dates
                    _current_logistics[sender_id]["start_date"] = start_date.strftime("20%y-%m-%d")
                    _current_logistics[sender_id]["end_date"] = end_date.strftime("20%y-%m-%d")
                    send_message(sender_id, "Great! Would you like to search for flights or points of interest?")
                    _state[sender_id] = 3 
    # flights or PoI?
    elif user_state == 3:
        if 'flights' in message_text.lower():
            flights = find_flights(
                _current_logistics[sender_id]["origin"][0], _current_logistics[sender_id]["origin"][1],
                _current_logistics[sender_id]["destination"][0], _current_logistics[sender_id]["destination"][1],
                _current_logistics[sender_id]["start_date"], _current_logistics[sender_id]["end_date"]
            )
            results = map(
                lambda result: format_flight(result),
                flights
            )
            for i in xrange(len(results)):
                send_message(sender_id, 
                    ("Here are your direct flight choices:\n" + results[i]) if i == 0 else results[i]
                )
        elif 'poi' in message_text.lower() or 'points of interest' in message_text.lower():
            send_message(sender_id, "What is the maximum distance (in miles) you are willing to travel from your destination pin?")
            _state[sender_id] = 3.5
    # setting PoI radius
    elif user_state == 3.5:
        if message_text.isdigit():
            radius = int(float(message_text) / 1.609344)
            _current_logistics[sender_id]["radius"] = radius
            raw_points = find_POI(_current_logistics[sender_id]["destination"][0], _current_logistics[sender_id]["destination"][1], radius)
            points = map(
                lambda point: {
                    "title" : point["title"], 
                    "grade" : point["grades"]["yapq_grade"], 
                    "short_description": point["details"]["short_description"],
                    "long_description": point["details"]["description"]
                },
                raw_points
            )
            _current_logistics[sender_id]["points"] = points
            for i in xrange(len(points)):
                send_message(sender_id,
                    ("%s. %s (%s/5 stars):\n%s" % (str(i + 1), points[i]["title"], str(points[i]["grade"]), points[i]["short_description"]))
                )
            send_message(
                sender_id,
                'Enter:\n' +
                '\t"more <num>" to learn more about point of interest <num>\n' +
                '\t"add <num>" to add point of interest <num> to the trip\n' +
                '\t"stop add" to finish adding points of interest'
            )
            _state[sender_id] = 4
    elif user_state == 4:
        command = message_text.rstrip().lower().split(" ")
        if len(command) > 2:
            send_message(sender_id, "invalid command ugu")
        elif command[0] == "add":
            if command[1].isdigit():
                _current_logistics[sender_id]["poi_id"] = int(command[1]) - 1
                send_message(
                    sender_id,
                    'When would you like to visit? (format as "MM/DD/YY HH:MM AM or PM")'
                )
                _state[sender_id] = 4.5
            else:
                send_message(sender_id, "Please enter location index as a number")
                send_message(
                    sender_id,
                    'Enter:\n' +
                    '\t"more <num>" to learn more about point of interest <num>\n' +
                    '\t"add <num>" to add point of interest <num> to the trip\n' +
                    '\t"stop add" to finish adding points of interest'
                )
        elif command[0] == "more":
            if command[1].isdigit():
                more_poi = _current_logistics[sender_id]["points"][int(command[1]) - 1]
                send_message(
                    sender_id,
                    more_poi["title"] + ":"
                )
                split_description = (more_poi["long_description"][0 + i: 600 + i] for i in range(0, len(more_poi["long_description"]), 600))
                for text in split_description:
                    send_message(sender_id, text)
            else:
                send_message(sender_id, "Please enter location index as a number")
            send_message(
            sender_id,
                'Enter:\n' +
                '\t"more <num>" to learn more about point of interest <num>\n' +
                '\t"add <num>" to add point of interest <num> to the trip\n' +
                '\t"stop add" to finish adding points of interest'
            )

        elif command[0] == "stop" and command[1] == "add":
            send_message(sender_id, "Your schedule is as follows:")
            for i in xrange(len(current_trip[sender_id].visits)):
                poi_entry = current_trip[sender_id].visits[i]
                send_message(sender_id, poi_entry.location + poi_entry.time.strftime(" on %b %d, %Y at %I:%M %p"))
            send_message(sender_id, "Enjoy your trip! Hope it's as purrfect as me")
            _state[sender_id] = 5
            run_event()
    elif user_state == 4.5:
        try:
            date = datetime.strptime(message_text.rstrip(), '%m/%d/%y %I:%M %p')
        except ValueError:
            send_message(sender_id, "Please format your dates correctly >:(")
        else:
            poi_id = _current_logistics[sender_id]["poi_id"]
            poi = _current_logistics[sender_id]["points"][poi_id]["title"]
            current_trip[sender_id].add_location(poi, date)
            send_message(sender_id, poi + " has been added!")
            _state[sender_id] = 4
            send_message(sender_id,
                'Enter:\n' +
                '\t"more <num>" to learn more about point of interest <num>\n' +
                '\t"add <num>" to add point of interest <num> to the trip\n' +
                '\t"stop add" to finish adding points of interest'
            )

    elif user_state == 5.5:
        answer = message_text.rstrip().lower()
        _current_logistics[sender_id]['current_poi'].add_feedback(_current_logistics[sender_id]['type'], answer)
        _current_logistics[sender_id]['current_poi'].mark_complete()
        send_message(sender_id, "Your response has been recorded!")
        if check_completed_trip(sender_id):
            _state[sender_id] = 6
        else:
            _state[sender_id] = 5
            select_next_event()
            run_event()
    elif user_state == 6:
        for i in xrange(len(current_trips[sender_id].visits)):
            if i == 0:
                send_message(
                    sender_id, 
                    "First, you visited " + 
                    current_trips[sender_id].visits[i].location +
                    ". You thought it was " +
                    current_trips[sender_id].visits[i].feedback["emotion"] + "."
                )
            elif i == len(current_trips[sender_id].visits) - 1:
                send_message(
                    sender_id, 
                    "Finally, you visited " + 
                    current_trips[sender_id].visits[i].location +
                    ". You thought it was " +
                    current_trips[sender_id].visits[i].feedback["emotion"] + "."
                )
            else:
                send_message(
                    sender_id, 
                    "Then, you visited " + 
                    current_trips[sender_id].visits[i].location +
                    ". You thought it was " +
                    current_trips[sender_id].visits[i].feedback["emotion"] + "."
                )
        send_message(sender_id, "It sounds like you had a great trip. Come back and chat with me again!")
        _state[sender_id] = -1

def handle_attachments(sender_id, user_state, message):    
    # Location
    if message["attachments"][0]["type"] == "location":
        if user_state == 0.5:
            location = message["attachments"][0]["payload"]["coordinates"]
            _state[sender_id] = 1
            # store destination location
            _current_logistics[sender_id] = {"destination" : (location["lat"], location["long"])}
            send_message(sender_id, 
                'Arigatou nyaa!\n\n' + 
                'Where will you be traveling from?')
        elif user_state == 1:
            location = message["attachments"][0]["payload"]["coordinates"]
            _state[sender_id] = 2
            # store origin location
            _current_logistics[sender_id]["origin"] = (location["lat"], location["long"])
            send_message(sender_id, 
                'Thank mew very much!\n\n' + 
                'What are your preferred leaving and returning dates? (format as "MM/DD/YY MM/DD/YY")')



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

    log("sending message to {recipient}: {text}".format(recipient=recipient_id, text=message_text.encode('utf-8')))

    params = {
        "access_token": os.environ["PAGE_ACCESS_TOKEN"]
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text.encode('utf-8')
        }
    })
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
    if r.status_code != 200:
        log(r.status_code)
        log(r.text)


def log(message):  # simple wrapper for logging to stdout on heroku
    print str(message)
    sys.stdout.flush()

def find_airport(lat, lon):
    nearest_airport_url = 'https://api.sandbox.amadeus.com/v1.2/airports/nearest-relevant'
    payload = {
        'apikey': amadeus_key,
        'latitude': lat,
        'longitude': lon
    }
    r = requests.get(nearest_airport_url, params = payload)
    return r.json()[0]['airport']

def find_flights(lat_start, long_start, lat_end, long_end, start_date, end_date):
    low_fare_url = 'https://api.sandbox.amadeus.com/v1.2/flights/low-fare-search'
    start_airport = find_airport(lat_start, long_start)
    end_airport = find_airport(lat_end, long_end)
    payload = {
        'apikey': amadeus_key,
        'origin': start_airport,
        'destination': end_airport,
        'departure_date': start_date,
        'return_date': end_date,
        'nonstop' : True,
        'number_of_results': 3
    }
    r = requests.get(low_fare_url, params = payload)
    print r.json()
    return r.json()['results']

def find_POI(lat, lon, radius):
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
