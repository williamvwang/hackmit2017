import os
import sys
import json

import requests
from flask import Flask, request

app = Flask(__name__)
app.config.from_pyfile('settings.cfg')  # load tokens from env

amadeus_key = app.config["AMADEUS_API_KEY"]

@app.route('/', methods=['GET'])

class POI:

	def __init__(self, location, time):
		self.location = location
		self.time = time
		self.feedback = {
			'emotion': '',
			'adjective':'',
			'memory':''
		}


class Trip:

	def __init__(self, name):
		self.tripName = name
		self.visits = []
		

def verify():
    # when the endpoint is registered as a webhook, it must echo back
    # the 'hub.challenge' value it receives in the query arguments
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == app.config["VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world", 200


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

                    log(event)

                    sender_id = event["sender"]["id"]        # the facebook ID of the person sending you the message
                    recipient_id = event["recipient"]["id"]  # the recipient's ID, which should be your page's facebook ID
                    message = event["message"]

                    # Text Message
                    if "text" in message:
                        message_text = message["text"]  # the message's text
                        send_message(sender_id, "uwau ~")

                    # Attachments
                    elif "attachments" in message:

                        # Location
                        if message["attachments"][0]["type"] == "location":
                            location = message["attachments"][0]["payload"]["coordinates"]
                            send_message(sender_id, "You dropped a pin at (" + str(location["lat"]) + ", " + str(location["long"]) + ").")

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
    return r.get_json[0]['airport']

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
    return r.get_json

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
    return r.get_json['points_of_interest']
    
    


if __name__ == '__main__':
    app.run(debug=True)
