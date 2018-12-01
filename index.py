import os
from flask import Flask, request, redirect
from twilio.rest import Client

account_sid = os.environ['TWILIO_ACCOUNT_SID']
auth_token = os.environ['TWILIO_AUTH_TOKEN']
client = Client(account_sid, auth_token)

app = Flask(__name__)


@app.route("/sms", methods=['GET', 'POST'])
def incoming_sms():
    body = request.values.get('Body', None)
    message = client.messages \
        .create(
        body=f"Hey {request.values.get('from', 'someone')} visited https://zeit-python-demo.jcharante.com",
        from_=os.environ['SHOUT_NUM'],
        to=os.environ['TRANG_NUM']
    )
    return "I don't know how to reply to your text message"

if __name__ == "__main__":
    app.run(debug=True)
