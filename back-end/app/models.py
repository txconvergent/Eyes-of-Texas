from app import app, db, bcrypt
from sqlalchemy.ext.hybrid import hybrid_property
from geoalchemy2 import Geography
import datetime
import jwt
import json


favorites_events = db.Table('favorites_events', db.Model.metadata,
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('event_id', db.Integer, db.ForeignKey('events.id'), primary_key=True)
)


class User(db.Model):
    """
    Table schema
    """
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    registered_on = db.Column(db.DateTime, nullable=False)
    username = db.Column(db.String(255), unique=True, nullable=False)
    favorites = db.relationship("Event", secondary=favorites_events, lazy='dynamic')

    buckets = db.relationship('Bucket', backref='bucket', lazy='dynamic')

    def __init__(self, email, password, username):
        self.email = email
        self.password = bcrypt.generate_password_hash(password, app.config.get('BCRYPT_LOG_ROUNDS')) \
            .decode('utf-8')
        self.registered_on = datetime.datetime.now()
        self.username = username

    def save(self):
        """
        Persist the user in the database
        :param user:
        :return:
        """
        db.session.add(self)
        db.session.commit()
        return self.encode_auth_token(self.id)

    def encode_auth_token(self, user_id):
        """
        Encode the Auth token
        :param user_id: User's Id
        :return:
        """
        try:
            payload = {
                'exp': datetime.datetime.utcnow() + datetime.timedelta(days=app.config.get('AUTH_TOKEN_EXPIRY_DAYS'),
                                                                       seconds=app.config.get(
                                                                           'AUTH_TOKEN_EXPIRY_SECONDS')),
                'iat': datetime.datetime.utcnow(),
                'sub': user_id
            }
            return jwt.encode(
                payload,
                app.config['SECRET_KEY'],
                algorithm='HS256'
            )
        except Exception as e:
            return e


    def favorite_event(self, event_id):
        #TODO: check what happens if user has already favorited this event
        event = Event.query.filter_by(id=event_id).first()
        if event:
            self.favorites.append(event)
            db.session.commit()
            return True
        return False


    def remove_favorite(self, event_id):
        #TODO: check what happens if user has never favorited this event
        event = Event.query.filter_by(id=event_id).first()
        if event:
            self.favorites.remove(event)
            db.session.commit()
            return True
        return False


    @staticmethod
    def decode_auth_token(token):
        """
        Decoding the token to get the payload and then return the user Id in 'sub'
        :param token: Auth Token
        :return:
        """
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms='HS256')
            is_token_blacklisted = BlackListToken.check_blacklist(token)
            if is_token_blacklisted:
                return 'Token was Blacklisted, Please login In'
            return payload['sub']
        except jwt.ExpiredSignatureError:
            return 'Signature expired, Please sign in again'
        except jwt.InvalidTokenError:
            return 'Invalid token. Please sign in again'

    @staticmethod
    def get_by_id(user_id):
        """
        Filter a user by Id.
        :param user_id:
        :return: User or None
        """
        return User.query.filter_by(id=user_id).first()

    @staticmethod
    def get_by_email(email):
        """
        Check a user by their email address
        :param email:
        :return:
        """
        return User.query.filter_by(email=email).first()


    def reset_password(self, new_password):
        """
        Update/reset the user password.
        :param new_password: New User Password
        :return:
        """
        self.password = bcrypt.generate_password_hash(new_password, app.config.get('BCRYPT_LOG_ROUNDS')) \
            .decode('utf-8')
        db.session.commit()


class BlackListToken(db.Model):
    """
    Table to store blacklisted/invalid auth tokens
    """
    __tablename__ = 'blacklist_token'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    token = db.Column(db.String(255), unique=True, nullable=False)
    blacklisted_on = db.Column(db.DateTime, nullable=False)

    def __init__(self, token):
        self.token = token
        self.blacklisted_on = datetime.datetime.now()

    def blacklist(self):
        """
        Persist Blacklisted token in the database
        :return:
        """
        db.session.add(self)
        db.session.commit()

    @staticmethod
    def check_blacklist(token):
        """
        Check to find out whether a token has already been blacklisted.
        :param token: Authorization token
        :return:
        """
        response = BlackListToken.query.filter_by(token=token).first()
        if response:
            return True
        return False


event_category = db.Table('event_category', db.Model.metadata,
    db.Column('category_id', db.Integer, db.ForeignKey('categories.id'), primary_key=True),
    db.Column('event_id', db.Integer, db.ForeignKey('events.id'), primary_key=True)
)


class Event(db.Model):
    """
    Class that represents events
    """
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    title = db.Column(db.String(128), nullable=False)
    location = db.Column(Geography(geometry_type='POINT', srid=4326))
    time_of_event = db.Column(db.DateTime, nullable=False)
    time_posted = db.Column(db.DateTime, nullable=False)
    desc = db.Column(db.String)
    sponsored = db.Column(db.Boolean)
    votes = db.relationship("Vote", lazy='dynamic')

    #TODO: check what happens SQL injection with long and lat
    #TODO: check what happens if string is too long, empty etc

    def __init__(self, user_id, title, time_event, desc, lng, lat, categories, sponsored=False):
        self.user_id = user_id
        self.title = title
        self.time_posted = datetime.datetime.utcnow()
        self.location = 'POINT(%f %f)' % (lng, lat)
        self.time_of_event = datetime.datetime.strptime(time_event, "%Y-%m-%dT%H:%M:%SZ")
        self.desc = desc
        self.sponsored = sponsored
        for category in categories:
            cat = Category.query.filter_by(name=category).first()
            if cat:
                self.categories.append(cat)
            else:
                cat = Category(name=category)
                self.categories.append(cat)
        


    def save(self):
        db.session.add(self)
        db.session.commit()


    @hybrid_property
    def vote_count(self):
        #return len(self.children)   # @note: use when non-dynamic relationship
        return self.votes.count()# @note: use when dynamic relationship

    @vote_count.expression
    def vote_count(cls):
        return (db.select([db.func.count(User.id)]).
                where(Event.id == cls.id).
                label("votes")
                )


    def json(self, current_user):
        from app.event.helper import list_categories
        return {
            "id": self.id,
            "poster": User.query.filter_by(id=self.user_id).first().username,
            "title": self.title,
            "longitude": db.session.scalar(self.location.ST_X()),
            "latitude": db.session.scalar(self.location.ST_Y()),
            "time_of_event": self.time_of_event.isoformat(),
            "time_posted": self.time_posted.isoformat(),
            "desc": self.desc,
            "sponsored": self.sponsored,
            "votes": self.vote_count,
            "user_has_voted": Vote.user_voted(self.id, current_user.id),
            "categories": list_categories(self.categories)
        }






class Category(db.Model):
    """
    Class that represents the various categories an event can have
    """
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(20), unique=True, nullable=False)
    events = db.relationship("Event", secondary=event_category, backref="categories", lazy='dynamic')

    #TODO: see what happens if you try to create a duplicate category

    def __init__(self, name):
        self.name = name
        

    def save(self):
        db.session.add(self)
        db.session.commit()


    @staticmethod
    def get_list():
        list = []
        for category in Category.query:
            list.append(category.name)
        return list


    @staticmethod
    def create_category(name):
        category = Category(name)
        category.save()




class Vote(db.Model):
    """
    Class that keeps track of upvotes"""
    __tablename__ = 'votes'
    __table_args__ = (
        db.PrimaryKeyConstraint('event_id', 'user_id'),
    )

    #TODO: add primary key?

    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)

    def __init__(self, event_id, user_id):
        self.event_id = event_id
        self.user_id = user_id


    def save(self):
        db.session.add(self)
        db.session.commit()


    @staticmethod
    def upvote(event_id, user_id):
        vote = Vote.query.filter_by(user_id=user_id, event_id=event_id).first()
        if not vote:
            vote = Vote(event_id=event_id, user_id=user_id)
            vote.save()
            return True
        return False
    

    @staticmethod
    def remove_vote(event_id, user_id):
        vote = Vote.query.filter_by(user_id=user_id, event_id=event_id)
        if vote:
            vote.delete()
            db.session.commit()
            return True
        return False


    @staticmethod
    def user_voted(event_id, user_id):
        return db.session.query(Vote.query.filter_by(user_id=user_id, event_id = event_id).exists()).scalar()







class Bucket(db.Model):
    """
    Class to represent the BucketList model
    """
    __tablename__ = 'buckets'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_at = db.Column(db.DateTime, nullable=False)
    modified_at = db.Column(db.DateTime, nullable=False)
    items = db.relationship('BucketItem', backref='item', lazy='dynamic')

    def __init__(self, name, user_id):
        self.name = name
        self.user_id = user_id
        self.create_at = datetime.datetime.utcnow()
        self.modified_at = datetime.datetime.utcnow()

    def save(self):
        """
        Persist a bucket in the database
        :return:
        """
        db.session.add(self)
        db.session.commit()

    def update(self, name):
        """
        Update the name of the Bucket
        :param name:
        :return:
        """
        self.name = name
        db.session.commit()

    def delete(self):
        """
        Delete a Bucket from the database
        :return:
        """
        db.session.delete(self)
        db.session.commit()

    def json(self):
        """
        Json representation of the bucket model.
        :return:
        """
        return {
            'id': self.id,
            'name': self.name,
            'createdAt': self.create_at.isoformat(),
            'modifiedAt': self.modified_at.isoformat()
        }


class BucketItem(db.Model):
    """
    BucketItem model class
    """

    __tablename__ = 'bucketitems'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    bucket_id = db.Column(db.Integer, db.ForeignKey('buckets.id'))
    create_at = db.Column(db.DateTime, nullable=False)
    modified_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, name, description, bucket_id):
        self.name = name
        self.description = description
        self.bucket_id = bucket_id
        self.create_at = datetime.datetime.utcnow()
        self.modified_at = datetime.datetime.utcnow()

    def save(self):
        """
        Persist Item into the database
        :return:
        """
        db.session.add(self)
        db.session.commit()

    def update(self, name, description=None):
        """
        Update the records in the item
        :param name: Name
        :param description: Description
        :return:
        """
        self.name = name
        if description is not None:
            self.description = description
        db.session.commit()

    def delete(self):
        """
        Delete an item
        :return:
        """
        db.session.delete(self)
        db.session.commit()

    def json(self):
        """
        Json representation of the model
        :return:
        """
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'bucketId': self.bucket_id,
            'createdAt': self.create_at.isoformat(),
            'modifiedAt': self.modified_at.isoformat()
        }
