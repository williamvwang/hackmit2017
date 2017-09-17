import os
import sys
import json

import requests
from flask import Flask, request

app = Flask(__name__)
app.config.from_pyfile('settings.cfg')  # load tokens from env


@app.route('/', methods=['GET'])
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


if __name__ == '__main__':
    app.run(debug=True)
