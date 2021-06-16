from flask import current_app, session
from requests_oauthlib import OAuth1Session
from urllib.parse import urlencode

project = "https://commons.wikimedia.org/w/api.php?"


def raw_request(params):
    app = current_app
    url = project + urlencode(params)
    client_key = app.config['CONSUMER_KEY']
    client_secret = app.config['CONSUMER_SECRET']
    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          resource_owner_key=session['owner_key'],
                          resource_owner_secret=session['owner_secret'])
    return oauth.get(url, timeout=4)


def raw_post_request(files, params):
    app = current_app
    url = project
    client_key = app.config['CONSUMER_KEY']
    client_secret = app.config['CONSUMER_SECRET']
    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          resource_owner_key=session['owner_key'],
                          resource_owner_secret=session['owner_secret'])
    return oauth.post(url, files=files, data=params, timeout=4)


def api_request(params):
    return raw_request(params).json()


def userinfo_call():
    params = {'action': 'query', 'meta': 'userinfo', 'format': 'json'}
    return api_request(params)


def get_username():
    if 'owner_key' not in session:
        return  # not authorized

    if 'username' in session:
        return session['username']

    reply = userinfo_call()
    if 'query' not in reply:
        return
    session['username'] = reply['query']['userinfo']['name']

    return session['username']


def get_token():
    params = {
        'action': 'query',
        'meta': 'tokens',
        'format': 'json',
        'formatversion': 2,
    }
    reply = api_request(params)
    token = reply['query']['tokens']['csrftoken']
    return token


def upload_file(file, filename, form, username):
    text = build_text(form, username)
    token = get_token()

    params = {
        "action": "upload",
        "filename": form["title"]+get_file_ext(filename),
        "format": "json",
        "token": token,
        "text": text,
        "comment": "Uploaded with wikiusos"
    }

    media_file = {'file': (filename, file.read(), 'multipart/form-data')}

    req = raw_post_request(media_file, params)
    data = req.json()

    return data


def build_text(form, username):
    text = ("=={{int:filedesc}}==\n"
            "{{Information\n"
            "|description={{"+form["lang"]+"|1="+form["description"]+"}}\n"
            "|date="+form["date"]+"\n"
            "|source={{own}}\n"
            "|author=[[User:"+username+"|"+username+"]]\n"
            "}}\n\n"
            "=={{int:license-header}}==\n"
            "{{Wikiusos}}\n"
            "{{"+get_license(form["license"])+"}}\n\n"
            "[[Category:Uploaded with wikiusos|"+form["qid"]+"]]")
    return text


def get_license(license_):
    if license_ == "ccbysa3":
        return "Cc-by-sa-3.0"
    elif license_ == "ccby4":
        return "Cc-by-4.0"
    elif license_ == "ccby3":
        return "Cc-by-3.0"
    elif license_ == "cc0":
        return "Cc-zero"
    else:
        return "Cc-by-sa-4.0"


def get_file_ext(filename):
    file_ext = filename.split(".")[-1]
    if file_ext != filename:
        return "." + file_ext
    return ""
