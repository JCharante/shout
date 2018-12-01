import os
from sqlalchemy import Column, Integer, String, Boolean, create_engine, Text, DATETIME, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()

class UserV1(Base):
    __tablename__ = 'UserV1'
    id = Column(Integer, primary_key=True)
    phoneNumber = Column(Text)
    shoutRange = Column(Integer)
    haveSignedUp = Column(Boolean)


engine = create_engine(os.environ['DBA'])
Base.metadata.create_all(engine)
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

from flask import Flask, request, redirect
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

account_sid = os.environ['TWILIO_ACCOUNT_SID']
auth_token = os.environ['TWILIO_AUTH_TOKEN']
client = Client(account_sid, auth_token)

app = Flask(__name__)


@app.route("/sms", methods=['GET', 'POST'])
def incoming_sms():
    phoneNumberFromTwilio = request.values.get('From', None)
    if phoneNumberFromTwilio is None:
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
        response.message("Hey this is Shout! Do you want to sign up to receive shouts? If so, reply w/ SIGNUP")
        return str(response)
    if userInDB.haveSignedUp is False:
        textBody = request.values.get('Body', None) # type: str
        if textBody is not None:
            if textBody.lower() == "SIGNUP":
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


    """
    body = request.values.get('Body', None)
    message = client.messages \
        .create(
        body=f"From {request.values.get('From', 'someone')}: {request.values.get('Body', '')}",
        from_=os.environ['SHOUT_NUM'],
        to=os.environ['TRANG_NUM']
    )
    """
    session.close()
    resp = MessagingResponse()
    resp.message("I don't know how to reply to your text message")

    return str(resp)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
