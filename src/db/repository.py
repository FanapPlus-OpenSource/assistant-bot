# -*- coding: utf-8 -*-

from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime, timedelta
from .models import User, Car, Event, ActivityLog
from shared import State
from .utils import todict


class MongoRepository(object):
    def __init__(self):
        # ToDo use connection config
        self.client = MongoClient('localhost:27017')


class UserRepository(MongoRepository):
    def __init__(self):
        super().__init__()
        self.collection = self.client.assistant_bot.users

    def add_user(self, user: User):
        self.collection.insert_one(todict(user))

    def find_user(self, user_id):
        user = self.collection.find_one({'user_id': user_id})
        return User.from_dict(user) if user is not None else None

    def get_users(self):
        cursor = self.collection.find().sort('username', ASCENDING)
        users = map(lambda u: User.from_dict(u), cursor)
        return list(users)

    def find_participants(self, event_id):
        user_filter = {'user_state': {'$elemMatch': {
            'event_id': event_id, 'state': State.REGISTERED.name}}}
        cursor = self.collection.find(user_filter).sort('username', ASCENDING)
        users = map(lambda u: User.from_dict(u), cursor)
        return list(users)

    def remove_car(self, user_id):
        update_result = self.collection.update_one({'user_id': user_id},
                                                   {'$unset': {'car': ''}})
        return update_result.modified_count

    def add_car(self, user_id, model: str, plate_number: str):
        car = Car(plate_number, model)
        return self.collection.update_one({'user_id': user_id},
                                          {'$set': {'car': car.__dict__}})

    def participate(self, user_id, active_event_id):
        self.__update_user_state(user_id, State.REGISTERED, active_event_id)

    def withdraw(self, user_id, active_event_id):
        self.__update_user_state(user_id, State.UNREGISTERED, active_event_id)

    def __update_user_state(self, user_id: str, state: State,
                            active_event_id: str):
        query = {"user_id": user_id,
                 "user_state": {
                     "$elemMatch": {"event_id": active_event_id}
                 }}
        update = {"$set": {
            "user_state.$.modified_on": datetime.now(),
            "user_state.$.state": state.name}}

        res = self.collection.update_one(query, update)
        if res.matched_count < 1:
            res = self.collection.update_one(
                {"user_id": user_id},
                {"$push": {
                    "user_state": {
                        "modified_on": datetime.now(),
                        "state": state.name,
                        "event_id": active_event_id
                    }
                }})


class EventRepository(MongoRepository):
    def __init__(self):
        super().__init__()
        self.collection = self.client.assistant_bot.events

    def find_active_event(self):
        now = datetime.now()
        event_filter = {'$and': [
            {'is_active': True},
            {'from_time': {'$lte': now}},
            {'to_time': {'$gte': now}}
        ]}

        active_event = self.collection.find_one(event_filter)
        if active_event is not None:
            return Event.from_dict(active_event)

        return None

    def find_latest_event(self):
        try:
            event = self.collection.find().sort("to_time", DESCENDING)\
                    .limit(1).next()
        except StopIteration:
            return None

        return Event.from_dict(event)

    def add_event(self, duration):
        now = datetime.now()
        event_id = str(now.year)+'-'+str(now.month) + '-'+str(now.day)+'-' + \
            str(now.hour)+str(now.minute)+str(now.second)+str(now.microsecond)
        event = Event(now, now+timedelta(hours=duration),
                      event_id, datetime.now(), True)
        self.collection.insert_one(todict(event))

    def deactive_event(self):
        event_filter = {"is_active": True}
        update = {"$set": {"is_active": False}}
        result = self.collection.update_one(event_filter, update)
        if result.matched_count > 0:
            return True
        else:
            return False


class ActivityLogRepository(MongoRepository):
    def __init__(self):
        super().__init__()
        self.collection = self.client.assistant_bot.activity_logs

    def log_action(self, activity_log: ActivityLog):
        self.collection.insert_one(todict(activity_log))
