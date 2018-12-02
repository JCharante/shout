import os
from sqlalchemy import Column, Integer, String, Boolean, create_engine, Text, DATETIME, JSON, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from random import randint
from uuid import uuid4
import geopy.distance
import http.client
import urllib.parse
import re

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
    longitude = Column(Float)
    latitude = Column(Float)


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

def unshorten_url(url):
    parsed = urllib.parse.urlparse(url)
    h = http.client.HTTPConnection(parsed.netloc)
    resource = parsed.path
    if parsed.query != "":
        resource += "?" + parsed.query
    h.request('HEAD', resource )
    response = h.getresponse()
    if response.status//100 == 3 and response.getheader('Location'):
        return unshorten_url(response.getheader('Location')) # changed to process chains of short urls
    else:
        return url


@app.route('/')
def index():
    return render_template('index.html')


@app.route("/web/create_session", methods=['GET', 'POST'])
def web_create_session():
    session = DBSession()

    secretCode = generateSecret()
    sessionId = str(uuid4())

    response = dict()
    response['sessionId'] = sessionId
    response['secretCode'] = secretCode

    jsonData = request.get_json()

    if request.method == 'POST' and jsonData is not None:
        latitude = jsonData.get('latitude', -1)
        longitude = jsonData.get('longitude', -1)
        if latitude != -1 and type(latitude) == type(-72.3):
            session.add(WebSessionV1(
                sessionId=sessionId,
                secretCode=secretCode,
                pairedWithPhoneNumber=False,
                phoneNumber='',
                latitude=latitude,
                longitude=longitude
            ))
        else:
            session.add(WebSessionV1(
                sessionId=sessionId,
                secretCode=secretCode,
                pairedWithPhoneNumber=False,
                phoneNumber='',
                latitude=-1,
                longitude=-1
            ))
    else:
        session.add(WebSessionV1(
            sessionId=sessionId,
            secretCode=secretCode,
            pairedWithPhoneNumber=False,
            phoneNumber=''
        ))
    session.commit()
    session.close()
    return jsonify(**response)


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
        response = MessagingResponse()
        if textBody.lower() == "!signup":
            session.add(UserV1(
                phoneNumber=phoneNumberFromTwilio,
                shoutRange=2000,
                haveSignedUp=True,
                longitude=-1,
                latitude=-1
            ))
            session.commit()
            session.close()
            response.message("\n".join([
                f"Thanks for signing up. Your shout range is {2000}m.",
                "Before you can send or receive shouts, you must set your location. Visit shout.jcharante.com to set your location.",
                "If you need help, reply w/ !help"
            ]))
            return str(response)
        else:
            session.add(UserV1(
                phoneNumber=phoneNumberFromTwilio,
                shoutRange=2000,
                haveSignedUp=False,
                longitude=-1,
                latitude=-1
            ))
            session.commit()
            session.close()
            response.message("Hey this is Shout! Do you want to sign up to send or receive shouts? If so, reply w/ !signup")
            return str(response)

    if userInDB.haveSignedUp is False:
        if textBody is not None:
            if textBody.lower() == "!signup":
                userInDB.haveSignedUp = True
                rangeInMeters = userInDB.shoutRange
                session.commit()
                session.close()
                response = MessagingResponse()
                response.message("\n".join([
                    f"Thanks for signing up. Your shout range is {rangeInMeters}m.",
                    "Before you can send or receive shouts, you must set your location. Visit shout.jcharante.com to set your location.",
                    "If you need help, reply w/ !help"
                ]))
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
            if web_session.longitude is not -1 and web_session.latitude is not -1:
                userInDB.latitude = web_session.latitude
                userInDB.longitude = web_session.longitude
            session.commit()
            session.close()
            response = MessagingResponse()
            response.message("Connected to Web Companion!")
            return str(response)
        else:
            session.close()
            response = MessagingResponse()

            response.message('\n'.join([
                "Here are the following commands:",
                "!help - get a list of commands",
                "!code ____ - enter a code from the web companion",
                "____ shout something to those in range",
                "",
                "If you want to update your location, you must currently use the web companion. Visit shout.jcharante.com"
            ]))
            return str(response)

    # user is signed up and is trying to send a shout

    phoneNumbersInRange = []
    if userInDB.shoutRange == -1:
        # User has global shout privileges
        for user in session.query(UserV1).filter_by(haveSignedUp=True).all(): # type: UserV1
            phoneNumbersInRange.append(user.phoneNumber)
    else:
        if userInDB.longitude == -1:
            session.close()
            response = MessagingResponse()
            response.message("Sorry, you must set your location first. Reply w/ !help for a list of commands.")
            return str(response)
        shouterCoord = (userInDB.latitude, userInDB.longitude)
        for user in session.query(UserV1).filter_by(haveSignedUp=True).all(): # type: UserV1
            userCoord = (user.latitude, user.longitude)
            if geopy.distance.vincenty(shouterCoord, userCoord).m < userInDB.shoutRange:
                phoneNumbersInRange.append(user.phoneNumber)
    session.close()
    for phoneNumber in phoneNumbersInRange:
        message = client.messages.create(
            body=textBody,
            from_=os.environ['SHOUT_NUM'],
            to=phoneNumber
        )
    response = MessagingResponse()
    response.message(f"Shout sent to {len(phoneNumbersInRange)} people nearby")
    return str(response)

if __name__ == "__main__":
    app.run(threaded=True, host='0.0.0.0', port=5000, debug=True)
