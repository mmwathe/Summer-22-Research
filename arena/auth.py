"""
arena/auth.py - Authentication methods for accessing the ARENA.
"""

import json
import os
import pickle
import ssl
import sys
import time
import webbrowser
from pathlib import Path
from urllib import parse, request
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

import jwt
import requests
from google.auth.transport.requests import AuthorizedSession, Request
from google_auth_oauthlib.flow import InstalledAppFlow

debug_toggle = False
_scopes = ["openid",
           "https://www.googleapis.com/auth/userinfo.profile",
           "https://www.googleapis.com/auth/userinfo.email"]
_user_gauth_path = f'{str(Path.home())}/.arena_google_auth'
_user_mqtt_path = f'{str(Path.home())}/.arena_mqtt_auth'
_local_mqtt_path = f'.arena_mqtt_auth'
_mqtt_token = {}


def authenticate(realm, scene, broker, debug=False):
    global debug_toggle
    global _mqtt_token
    debug_toggle = debug
    webhost = broker  # broker expected on web-client host
    print("Signing in to the ARENA...")

    # TODO: remove this workaround for dev broker/webhost separation
    if broker == 'oz.andrew.cmu.edu':
        webhost = 'xr.andrew.cmu.edu'

    # TODO: remove local check after ARTS supports mqtt_token passing
    # check for local mqtt_token first
    if os.path.exists(_local_mqtt_path):
        print("Using local MQTT token.")
        f = open(_local_mqtt_path, "r")
        mqtt_json = f.read()
        f.close()
        # TODO: check token expiration
        _mqtt_token = json.loads(mqtt_json)
        return _mqtt_token

    # begin authentication flow
    creds = None
    browser = None
    try:
        browser = webbrowser.get()
    except (webbrowser.Error) as err:
        print("Console-only login. {0}".format(err))

    # store the user's access and refresh tokens
    if os.path.exists(_user_gauth_path):
        print("Using cached Google authentication.")
        with open(_user_gauth_path, 'rb') as token:
            creds = pickle.load(token)
        session = AuthorizedSession(creds)
    # if no credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Requesting refreshed Google authentication.")
            creds.refresh(Request())
            session = AuthorizedSession(creds)
        else:
            print("Requesting new Google authentication.")
            gauth_json = _get_gauthid(webhost)
            flow = InstalledAppFlow.from_client_config(
                json.loads(gauth_json), _scopes)
            if browser:
                # TODO: select best client port to avoid likely conflicts
                creds = flow.run_local_server(port=8989)
            else:
                creds = flow.run_console()
            session = flow.authorized_session()
        with open(_user_gauth_path, 'wb') as token:
            # save the credentials for the next run
            pickle.dump(creds, token)
        os.chmod(_user_gauth_path, 0o600)  # set user-only perms.

    id_token = creds.id_token
    profile_info = session.get(
        'https://www.googleapis.com/userinfo/v2/me').json()

    # use JWT for authentication
    if profile_info != None:
        mqtt_json = None
        user = profile_info['email']
        print(f'Authenticated Google account: {user}')

        # TODO: permissions may change by owner or admin,
        # for now, get a fresh mqtt_token each time
        # if os.path.exists(_user_mqtt_path):
        #     f = open(_user_mqtt_path, "r")
        #     mqtt_json = f.read()
        #     f.close()
        # # TODO: check token expiration

        # if no credentials available, get them.
        if not mqtt_json:
            print("Using remote-authenticated MQTT token.")
            mqtt_json = _get_mqtt_token(broker, realm, scene, user, id_token)
            # save mqtt_token
            with open(_user_mqtt_path, mode="w") as d:
                d.write(mqtt_json)
            os.chmod(_user_mqtt_path, 0o600)  # set user-only perms.

    # end authentication flow
    _mqtt_token = json.loads(mqtt_json)
    username = None
    if 'username' in _mqtt_token:
        username = _mqtt_token['username']
    print(f'ARENA Username: {username}')
    return _mqtt_token


# TODO: will be deprecated after using arena-account
def _get_gauthid(webhost):
    url = f'https://{webhost}/conf/gauth.json'
    return urlopen(url)


def _get_mqtt_token(broker, realm, scene, user, id_token):
    url = f'https://{broker}/user/mqtt_auth'
    if broker == 'oz.andrew.cmu.edu':
        # TODO: remove this workaround for non-auth broker
        url = f'https://{broker}:8888/'
        csrftoken = None
    else:
        # get the csrftoken for django
        csrf_url = f'https://{broker}/user/login'
        client = requests.session()
        if debug_toggle:
            csrftoken = client.get(csrf_url, verify=False).cookies['csrftoken']
        else:
            csrftoken = client.get(csrf_url).cookies['csrftoken']

    params = {
        "id_auth": "google-installed",
        "username": user,
        "id_token": id_token,
        "realm": realm,
        "scene": scene
    }
    query_string = parse.urlencode(params)
    data = query_string.encode("ascii")
    return urlopen(url, data=data, csrf=csrftoken)


def urlopen(url, data=None, creds=False, csrf=None):
    """ urlopen is for ARENA URL connections.
    url: the url to POST/GET.
    data: None for GET, add params for POST.
    creds: True to pass the MQTT token as a cookie.
    """
    global debug_toggle
    global _mqtt_token
    try:
        req = request.Request(url)
        if creds:
            req.add_header("Cookie", f"mqtt_token={_mqtt_token['token']}")
        if csrf:
            req.add_header("Cookie", f"csrftoken={csrf}")
            req.add_header("X-CSRFToken", csrf)
        if debug_toggle:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            res = request.urlopen(req, data=data, context=context)
        else:
            res = request.urlopen(req, data=data)
        return res.read().decode('utf-8')
    except (URLError, HTTPError) as err:
        print("{0}: ".format(err)+url)
        if isinstance(err, HTTPError) and round(err.code, -2) == 400:
            # user not authorized on website yet, they don't have an ARENA username
            base_url = "{0.scheme}://{0.netloc}".format(urlsplit(url))
            print(f'Login with this this account on the website first:')
            print(f'Trying to open login page: {base_url}/user')
            try:
                webbrowser.open_new_tab(f'{base_url}/user')
            except (webbrowser.Error) as err:
                print("Console-only login. {0}".format(err))
        sys.exit("Terminating...")


def signout():
    if os.path.exists(_user_gauth_path):
        os.remove(_user_gauth_path)
    if os.path.exists(_user_mqtt_path):
        os.remove(_user_mqtt_path)
    print("Signed out of the ARENA.")


def _print_mqtt_token(jwt):
    print('ARENA MQTT Permissions')
    print('----------------------')
    print(f'User: {jwt["sub"]}')
    exp_str = time.strftime("%c", time.localtime(jwt["exp"]))
    print(f'Expires: {exp_str}')
    print('Publish topics:')
    for pub in jwt["publ"]:
        print(f'- {pub}')
    print('Subscribe topics:')
    for sub in jwt["subs"]:
        print(f'- {sub}')


def permissions():
    # TODO: remove local check after ARTS supports mqtt_token passing
    # check for local mqtt_token first
    mqtt_path = None
    if os.path.exists(_local_mqtt_path):
        print("Using local MQTT token.")
        mqtt_path = _local_mqtt_path
    elif os.path.exists(_user_mqtt_path):
        print("Using user MQTT token.")
        mqtt_path = _user_mqtt_path
    if mqtt_path:
        f = open(mqtt_path, "r")
        mqtt_json = f.read()
        f.close()
        mqtt_token = json.loads(mqtt_json)
        decoded = jwt.decode(mqtt_token["token"], options={
            "verify_signature": False})
        _print_mqtt_token(decoded)


if __name__ == '__main__':
    globals()[sys.argv[1]]()
