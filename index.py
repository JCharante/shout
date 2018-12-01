import os
from sqlalchemy import Column, Integer, String, Boolean, create_engine, Text, DATETIME, JSON, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from random import randint
from uuid import uuid4

Base = declarative_base()

class UserV1(Base):
    __tablename__ = 'UserV1'
    id = Column(Integer, primary_key=True)
    phoneNumber = Column(Text)
    shoutRange = Column(Integer)
    haveSignedUp = Column(Boolean)
    longitude = Column(Float)
    latitude = Column(Float)

class WebSessionV1(Base):
    __tablename__ = 'WebSessionV1'
    id = Column(Integer, primary_key=True)
    sessionId = Column(String(36)) # uuid4
    secretCode = Column(Integer)
    pairedWithPhoneNumber = Column(Boolean)
    phoneNumber = Column(Text)


engine = create_engine(os.environ['DBA'])
Base.metadata.create_all(engine)
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

from flask import Flask, request, redirect, jsonify, render_template
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

account_sid = os.environ['TWILIO_ACCOUNT_SID']
auth_token = os.environ['TWILIO_AUTH_TOKEN']
client = Client(account_sid, auth_token)

app = Flask(__name__)

def generateSecret():
    return randint(1000, 9999)

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/web/create_session")
def web_create_session():
    session = DBSession()

    secretCode = generateSecret()
    sessionId = str(uuid4())

    response = dict()
    response['sessionId'] = sessionId
    response['secretCode'] = secretCode

    session.add(WebSessionV1(
        sessionId=sessionId,
        secretCode=secretCode,
        pairedWithPhoneNumber=False,
        phoneNumber=''
    ))
    session.commit()
    session.close()
    return jsonify(**response)

class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


@app.route('/web/update/location/gps', methods=['POST'])
def web_update_location_gps():
    session = DBSession()
    json_data = request.get_json()

    if json_data is None:
        session.close()
        return jsonify(**{
            'valid': False,
            'reason': 'No json in request'
        })
    web_session = session.query(WebSessionV1).filter_by(sessionId=json_data.get('sessionId')).first() # type: WebSessionV1

    if web_session is None:
        session.close()
        return jsonify(**{
            'valid': False,
            'reason': 'invalid sessionId'
        })

    if web_session.pairedWithPhoneNumber is False:
        session.close()
        return jsonify(**{
            'valid': False,
            'reason': 'not paired with phone number'
        })

    phoneNumber = web_session.phoneNumber
    user = session.query(UserV1).filter_by(phoneNumber=phoneNumber).first() # type: UserV1
    user.latitude = json_data.get('latitude', 0)
    user.longitude = json_data.get('longitude', 0)
    session.commit()
    session.close()

    response = dict()
    response['valid'] = True
    return jsonify(**response)

@app.route('/web/status', methods=['POST'])
def web_status():
    session = DBSession()
    json_data = request.get_json()
    if json_data is None:
        session.close()
        return jsonify(**{
            'valid': False,
            'reason': 'No json in request'
        })
    web_session = session.query(WebSessionV1).filter_by(sessionId=json_data.get('sessionId')).first() # type: WebSessionV1
    if web_session is None:
        session.close()
        return jsonify(**{
            'valid': False,
            'reason': 'invalid sessionId'
        })

    response = dict()
    response['pairedWithPhoneNumber'] = web_session.pairedWithPhoneNumber
    response['phoneNumber'] = web_session.phoneNumber

    return jsonify(**response)

@app.route("/sms", methods=['GET', 'POST'])
def incoming_sms():
    phoneNumberFromTwilio = request.values.get('From', None)
    textBody = request.values.get('Body', None)  # type: str
    if phoneNumberFromTwilio is None or textBody is None:
        return "Stop forging requests"

    session = DBSession()

    userInDB = session.query(UserV1).filter_by(phoneNumber=phoneNumberFromTwilio).first() # type: UserV1
    if userInDB is None:
        session.add(UserV1(
            phoneNumber=phoneNumberFromTwilio,
            shoutRange=-1,
            haveSignedUp=False
        ))
        session.commit()
        session.close()
        response = MessagingResponse()
        response.message("Hey this is Shout! Do you want to sign up to receive shouts? If so, reply w/ !SIGNUP")
        return str(response)

    if userInDB.haveSignedUp is False:
        if textBody is not None:
            if textBody.lower() == "!signup":
                userInDB.haveSignedUp = True
                rangeInMeters = userInDB.shoutRange
                session.commit()
                session.close()
                response = MessagingResponse()
                response.message(f"Thanks for signing up. Your shout range is {rangeInMeters}m. Text anytime to send a shout")
                return str(response)
            else:
                session.close()
                response = MessagingResponse()
                response.message("Hey, you haven't signed up yet to receive or send shouts. Please reply w/ SIGNUP")
                return str(response)

    # user is signed up, and this is a command
    if textBody[0:1] == "!":
        words = textBody.split(' ')
        if words[0] == "!code":
            secretCode = int(words[1])
            web_session = session.query(WebSessionV1).filter_by(secretCode=secretCode).first() # type: WebSessionV1
            if web_session is None:
                session.close()
                response = MessagingResponse()
                response.message("Sorry, that's not a valid code")
                return str(response)
            web_session.pairedWithPhoneNumber = True
            web_session.phoneNumber = phoneNumberFromTwilio
            session.commit()
            session.close()
            response = MessagingResponse()
            response.message("Connected to Web Companion!")
            return str(response)
        else:
            session.close()
            response = MessagingResponse()
            response.message("Here are the following commands:\n!help - get a list of commands\n!code ____ - enter a code from the web companion\n____ shout something to those in range")
            return str(response)

    # user is signed up and is trying to send a shout
    if userInDB.shoutRange == -1:
        # User has global shout privileges
        phoneNumbersInRange = []
        for User in session.query(UserV1).filter_by(haveSignedUp=True).all(): # type: UserV1
            phoneNumbersInRange.append(User.phoneNumber)
        session.close()
        for phoneNumber in phoneNumbersInRange:
            message = client.messages.create(
                body=textBody,
                from_=os.environ['SHOUT_NUM'],
                to=phoneNumber
            )
        response = MessagingResponse()
        response.message("Shout sent!")
        return str(response)
    else :
        # User has limited-range shout privileges which aren't yet implemented
        session.close()
        response = MessagingResponse()
        response.message("Sorry, only global shouts are available at the moment.")
        return str(response)


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
