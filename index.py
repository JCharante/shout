import os
from flask import Flask, request, redirect
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

account_sid = os.environ['TWILIO_ACCOUNT_SID']
auth_token = os.environ['TWILIO_AUTH_TOKEN']
client = Client(account_sid, auth_token)

app = Flask(__name__)


@app.route("/sms", methods=['GET', 'POST'])
def incoming_sms():
    body = request.values.get('Body', None)
    message = client.messages \
        .create(
        body=f"From {request.values.get('From', 'someone')}: {request.values('Body', '')}",
        from_=os.environ['SHOUT_NUM'],
        to=os.environ['TRANG_NUM']
    )
    resp = MessagingResponse()
    resp.message("I don't know how to reply to your text message")

    return str(resp)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
