# -*- coding: utf-8 -*-
__author__ = 'vadim'
import MySQLdb
from mysql.connector import errorcode
from larionov_api_app import dbService
from larionov_api_app.service import Codes
from larionov_api_app.service import response_error
from larionov_api_app.service import check_optional_params, check_required_params


def create(**data):
    try:
        check_required_params(data, ['username', 'email', 'name', 'about'])
    except Exception as e:
        return response_error(Codes.unknown_error, str(e))

    # Тут должна быть проверка на корректность данных в data
    query = "INSERT INTO User(username, email, name, about, isAnonymous) VALUES (%s, %s, %s, %s, %s)"

    if 'isAnonymous' not in data:
        data['isAnonymous'] = False

    values = (data['username'],
              data['email'],
              data['name'],
              data['about'],
              bool(data['isAnonymous']))

    db = dbService.connect()
    cursor = db.cursor()
    try:
        cursor.execute(query, values)
        data['id'] = cursor.lastrowid
        db.commit()

    except MySQLdb.Error as e:
        db.rollback()
        if e[0] == errorcode.ER_DUP_ENTRY:
            return response_error(Codes.user_exists, e)

        elif e[0] == errorcode.ER_PARSE_ERROR:
            return response_error(Codes.incorrect_query, e)

        else:
            return response_error(Codes.unknown_error, e)

    finally:
        cursor.close()
        db.close()

    user = {
        'about': data['about'],
        'email': data['email'],
        'id': data['id'],
        'isAnonymous': data['isAnonymous'],
        'name': data['name'],
        'username': data['username']
    }

    return {
        'code': Codes.ok,
        'response': user
    }


def details(get_resp=False, **data):
    query = """SELECT id, username, email, name, about, isAnonymous,
              GROUP_CONCAT(DISTINCT thread
              ORDER BY thread SEPARATOR ' ') AS subscriptions,
              GROUP_CONCAT(DISTINCT Fr.followee
              ORDER BY Fr.followee SEPARATOR ' ') AS followers,
              GROUP_CONCAT(DISTINCT Fe.follower
              ORDER BY Fe.follower SEPARATOR ' ') AS following
              FROM (SELECT * FROM User WHERE email='%s') AS Usr
              LEFT JOIN Subscriptions
              ON Usr.email=Subscriptions.user
              LEFT JOIN Followers AS Fr
              ON Usr.email=Fr.follower
              LEFT JOIN Followers AS Fe
              ON Usr.email=Fe.followee""" % data['user']

    db = dbService.connect()
    cursor = db.cursor()
    cursor.execute(query)
    user = cursor.fetchone()
    cursor.close()
    db.close()

    if user['email'] is None or len(user) == 0:
        user = {}

    else:
        if user['followers'] is None:
            user['followers'] = []
        else:
            user['followers'] = user['followers'].split()

        if user['following'] is None:
            user['following'] = []
        else:
            user['following'] = user['following'].split()

        if user['subscriptions'] is None:
            user['subscriptions'] = []
        else:
            # Строка не проходит тесты :(
            # Аналогично в forum.list_users
            user['subscriptions'] = user['subscriptions'].split()
            list_subscriptions = list()
            for elem in user['subscriptions']:
                list_subscriptions.append(int(elem))
            user['subscriptions'] = list_subscriptions

        user['isAnonymous'] = bool(user['isAnonymous'])

    if get_resp:
        if len(user) == 0:
            str_err = "User %s not found" % data['user']
            response = response_error(Codes.not_found, str_err)
        else:
            response = {
                'code': Codes.ok,
                'response': user
            }
        return response

    return user


def follow(**data):
    # Здесь должна быть проверка на корректность данных в **data
    # Здесь всё верно
    query = """INSERT INTO Followers(follower, followee)
               VALUES ('%s', '%s')""" % (data['followee'], data['follower'])

    db = dbService.connect()
    cursor = db.cursor()
    try:
        cursor.execute(query)
        db.commit()

    except MySQLdb.Error as e:
        # Если email не существует
        #if e[0] == errorcode.ER_NO_REFERENCED_ROW_2:
        if e[0] == errorcode.ER_PARSE_ERROR:
            return response_error(Codes.incorrect_query, e)
        else:
            return response_error(Codes.unknown_error, e)

    finally:
        cursor.close()
        db.close()

    user = details(**{'user': data['follower']})
    return {
        'code': Codes.ok,
        'response': user
    }


def unfollow(**data):
    query = "DELETE FROM Followers WHERE follower=%s AND followee=%s"

    # Тут всё верно
    values = (data['followee'], data['follower'])

    db = dbService.connect()
    cursor = db.cursor()
    try:
        cursor.execute(query, values)
        db.commit()

    except MySQLdb.Error as e:
        if e[0] == errorcode.ER_PARSE_ERROR:
            return response_error(Codes.incorrect_query, e)
        else:
            return response_error(Codes.unknown_error, e)

    finally:
        cursor.close()
        db.close()

    user = details(**{"user": data['follower']})
    return {
        'code': Codes.ok,
        'response': user
    }


def update_profile(**data):
    query = "UPDATE User SET name=%s, about=%s WHERE email=%s"
    values = (data['name'], data['about'], data['user'])

    db = dbService.connect()
    cursor = db.cursor()
    try:
        cursor.execute(query, values)
        db.commit()

    except MySQLdb.Error as e:
        return response_error(Codes.unknown_error, e)

    finally:
        cursor.close()
        db.close()

    user = details(**{'user': data['user']})
    return {
        'code': Codes.ok,
        'response': user
    }


def list_followers(**data):
    # Коннекшены либо передавать дальше надо, либо закрывать раньше!
    query = """SELECT DISTINCT Followers.followee AS user
                FROM User LEFT JOIN Followers ON User.email=Followers.follower
                INNER JOIN User AS Usr ON Followers.followee=Usr.email
                WHERE User.email='%s' """ % str(data['user'])

    if 'since_id' in data:
        query += """AND Usr.id >= %s """ % str(data['since_id'])

    if 'order' in data:
        query += """ORDER BY Usr.name %s """ % data['order']
    else:
        query += """ORDER BY Usr.name DESC """

    if 'limit' in data:
        query += """LIMIT %s """ % data['limit']

    db = dbService.connect()
    cursor = db.cursor()
    try:
        cursor.execute(query)

    except MySQLdb.Error as e:
        cursor.close()
        db.close()
        return response_error(Codes.unknown_error, e)

    followers = cursor.fetchall()
    ret = list()

    cursor.close()
    db.close()

    if followers is not None:
        for user in followers:
            ret.append(details(**{"user": user['user']}))

    return {
        'code': Codes.ok,
        'response': ret
    }


def list_following(**data):
    query = """SELECT DISTINCT Followers.follower AS user
                FROM User LEFT JOIN Followers ON User.email=Followers.followee
                INNER JOIN User AS Usr ON Followers.follower=Usr.email
                WHERE User.email='%s' """ % str(data['user'])

    if 'since_id' in data:
        query += """AND Usr.id>=%s """ % str(data['since_id'])

    if 'order' in data:
        query += """ORDER BY Usr.name %s """ % data['order']
    else:
        query += """ORDER BY Usr.name DESC """

    if 'limit' in data:
        query += """LIMIT %s """ % data['limit']

    db = dbService.connect()
    cursor = db.cursor()
    try:
        cursor.execute(query)

    except MySQLdb.Error as e:
        cursor.close()
        db.close()
        return response_error(Codes.unknown_error, e)

    following = cursor.fetchall()

    ret = list()
    if following is not None:
        for user in following:
            user_data = {"user": user['user']}
            ret.append(details(**user_data))

    cursor.close()
    db.close()
    return {
        'code': Codes.ok,
        'response': ret
    }


def list_posts(**data):
    query = """SELECT date, dislikes, forum, id, isApproved,
              isDeleted, isEdited, isHighlighted, isSpam, likes,
              message, parent, likes - dislikes AS points,
              thread, user FROM Post WHERE user='%s' """ % data['user']

    if 'since' in data:
        query += """AND date>='%s' """ % data['since']

    if 'order' in data:
        query += """ORDER BY date %s """ % data['order']
    else:
        query += """ORDER BY date DESC """

    if 'limit' in data:
        query += """LIMIT %s """ % data['limit']

    db = dbService.connect()
    cursor = db.cursor()
    try:
        cursor.execute(query)

    except MySQLdb.Error as e:
        cursor.close()
        db.close()
        return response_error(Codes.unknown_error, e)

    posts = cursor.fetchall()
    ret = list()
    for post in posts:
        #post['date'] = post['date'].strftime("%Y-%m-%d %H:%M:%S")
        post['isApproved'] = bool(post['isApproved'])
        post['isDeleted'] = bool(post['isDeleted'])
        post['isEdited'] = bool(post['isEdited'])
        post['isHighlighted'] = bool(post['isHighlighted'])
        post['isSpam'] = bool(post['isSpam'])
        ret.append(post)

    cursor.close()
    db.close()
    return {
        'code': Codes.ok,
        'response': ret
    }