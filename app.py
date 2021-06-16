import os
import json
import yaml
from flask import Flask, render_template, request, session, redirect, url_for, g
from flask_babel import Babel
from wikidata import query_quantidade, query_by_type, query_metadata_of_work, query_next_qid, api_category_members
from oauth_wiki import get_username, get_token
from requests_oauthlib import OAuth1Session

__dir__ = os.path.dirname(__file__)
app = Flask(__name__)
app.config.update(yaml.safe_load(open(os.path.join(__dir__, 'config.yaml'))))

BABEL = Babel(app)


##############################################################
# LOGIN
##############################################################
@app.before_request
def init_profile():
    g.profiling = []


@app.before_request
def global_user():
    g.user = get_username()


@app.route('/login')
def login():
    next_page = request.args.get('next')
    if next_page:
        session['after_login'] = next_page

    client_key = app.config['CONSUMER_KEY']
    client_secret = app.config['CONSUMER_SECRET']
    base_url = 'https://commons.wikimedia.org/w/index.php'
    request_token_url = base_url + '?title=Special%3aOAuth%2finitiate'

    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          callback_uri='oob')
    fetch_response = oauth.fetch_request_token(request_token_url)

    session['owner_key'] = fetch_response.get('oauth_token')
    session['owner_secret'] = fetch_response.get('oauth_token_secret')

    base_authorization_url = 'https://commons.wikimedia.org/wiki/Special:OAuth/authorize'
    authorization_url = oauth.authorization_url(base_authorization_url,
                                                oauth_consumer_key=client_key)
    return redirect(authorization_url)


@app.route("/oauth-callback", methods=["GET"])
def oauth_callback():
    base_url = 'https://commons.wikimedia.org/w/index.php'
    client_key = app.config['CONSUMER_KEY']
    client_secret = app.config['CONSUMER_SECRET']

    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          resource_owner_key=session['owner_key'],
                          resource_owner_secret=session['owner_secret'])

    oauth_response = oauth.parse_authorization_response(request.url)
    verifier = oauth_response.get('oauth_verifier')
    access_token_url = base_url + '?title=Special%3aOAuth%2ftoken'
    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          resource_owner_key=session['owner_key'],
                          resource_owner_secret=session['owner_secret'],
                          verifier=verifier)

    oauth_tokens = oauth.fetch_access_token(access_token_url)
    session['owner_key'] = oauth_tokens.get('oauth_token')
    session['owner_secret'] = oauth_tokens.get('oauth_token_secret')
    next_page = session.get('after_login')

    return redirect(next_page)


##############################################################
# LOCALIZAÇÃO
##############################################################
# Função para pegar a língua de preferência do usuário
@BABEL.localeselector
def get_locale():
    if request.args.get('lang'):
        session['lang'] = request.args.get('lang')
    return session.get('lang', 'pt')


# Função para mudar a língua de exibição do conteúdo
@app.route('/set_locale')
def set_locale():
    next_page = request.args.get('return_to')
    lang = request.args.get('lang')

    session["lang"] = lang
    redirected = redirect(next_page)
    redirected.delete_cookie('session', '/item')
    return redirected


def pt_to_ptbr(lang):
    if lang == "pt" or lang == "pt-br":
        return "pt-br"
    else:
        return lang


##############################################################
# PÁGINAS
##############################################################
@app.errorhandler(400)
@app.errorhandler(401)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(406)
@app.errorhandler(408)
@app.errorhandler(409)
@app.errorhandler(410)
@app.errorhandler(411)
@app.errorhandler(412)
@app.errorhandler(413)
@app.errorhandler(414)
@app.errorhandler(415)
@app.errorhandler(416)
@app.errorhandler(417)
@app.errorhandler(418)
@app.errorhandler(422)
@app.errorhandler(423)
@app.errorhandler(424)
@app.errorhandler(429)
@app.errorhandler(500)
@app.errorhandler(501)
@app.errorhandler(502)
@app.errorhandler(503)
@app.errorhandler(504)
@app.errorhandler(505)
def page_not_found(e):
    return render_template('error.html')


@app.route('/')
@app.route('/home')
@app.route('/inicio')
def inicio():
    username = get_username()
    lang = pt_to_ptbr(get_locale())
    return render_template('inicio.html',
                           username=username,
                           lang=lang)


@app.route('/about')
@app.route('/sobre')
def sobre():
    username = get_username()
    lang = pt_to_ptbr(get_locale())
    with open(os.path.join(app.static_folder, 'queries.json'), encoding="utf-8") as category_queries:
        all_queries = json.load(category_queries)

    quantidade = query_quantidade(all_queries["Quantidade_de_objetos"]["query"])
    return render_template('sobre.html',
                           username=username,
                           lang=get_locale(),
                           number_works=quantidade)


@app.route('/tutorial')
def tutorial():
    username = get_username()
    lang = pt_to_ptbr(get_locale())
    return render_template('tutorial.html',
                           username=username,
                           lang=lang)


@app.route('/apps')
def apps():
    username = get_username()
    lang = pt_to_ptbr(get_locale())
    return render_template('apps.html',
                           username=username,
                           lang=lang)


@app.route('/colecao/<type>')
def colecao(type):
    username = get_username()
    lang = pt_to_ptbr(get_locale())
    with open(os.path.join(app.static_folder, 'queries.json'), encoding="utf-8") as category_queries:
        all_queries = json.load(category_queries)

    try:
        selected_query = all_queries[type]["query"]
        selection = query_by_type(selected_query)
        if lang == "en":
            descriptor = all_queries[type]["descriptor"]["en"]
        else:
            descriptor = all_queries[type]["descriptor"]["pt-br"]

        return render_template("colecao.html",
                               collection=selection,
                               username=username,
                               lang=lang,
                               descriptor=descriptor)
    except:
        return redirect(url_for('inicio'))


@app.route('/item/<qid>', methods=["GET"])
def item(qid):
    username = get_username()
    lang = pt_to_ptbr(get_locale())

    with open(os.path.join(app.static_folder, 'queries.json')) as category_queries:
        all_queries = json.load(category_queries)

    metadata_query = all_queries["Metadados"]["query"].replace("LANGUAGE", lang).replace("QIDDAOBRA", qid)
    next_qid_query = all_queries["Next_qid"]["query"].replace("QIDDAOBRA", qid)
    work_metadata = query_metadata_of_work(metadata_query, lang=lang)
    next_qid = query_next_qid(next_qid_query)

    brasoes = [{"qid": "Q5198811", "label": "Brasão da cidade de São Paulo"}]

    crowns = [{"qid": "Q15320147", "label": "Astral crown"},
              {"qid": "Q2047836", "label": "camp crown"},
              {"qid": "Q429340", "label": "Coroa mural"},
              {"qid": "Q50324108", "label": "coronet"},
              {"qid": "Q5788764", "label": "Crown of the Infante"},
              {"qid": "Q18433798", "label": "imperial crown"},
              {"qid": "Q70576379", "label": "Imperial crown"},
              {"qid": "Q58995913", "label": "royal crown"},
              {"qid": "Q4287993", "label": "Tudor Crown"},
              {"qid": "Q1399217", "label": "Volkskrone"}]

    colors = [{"qid": "Q430099", "label": "or"},
              {"qid": "Q936472", "label": "argento"},
              {"qid": "Q1785501", "label": "azure"},
              {"qid": "Q858055", "label": "gules"},
              {"qid": "Q4401253", "label": "purpure"},
              {"qid": "Q936496", "label": "sable"},
              {"qid": "Q10858582", "label": "murrey"},
              {"qid": "Q218177", "label": "sanguinho"},
              {"qid": "Q218169", "label": "tenné"},
              {"qid": "Q1055869", "label": "azul-celeste"},
              {"qid": "Q1663655", "label": "carnação"},
              {"qid": "Q218173", "label": "cendrée"},
              {"qid": "Q3040333", "label": "laranja"}]

    partitions = [{"qid": "Q27304931", "label": "chapé"},
                  {"qid": "Q27307662", "label": "chapé ployé"},
                  {"qid": "Q2394938", "label": "chaussé"},
                  {"qid": "Q3689354", "label": "chequy counterchanged"},
                  {"qid": "Q3925792", "label": "chequy of 15"},
                  {"qid": "Q3925799", "label": "chequy of nine"},
                  {"qid": "Q3689252", "label": "counterquartered"},
                  {"qid": "Q3603323", "label": "embrassé"},
                  {"qid": "Q1471238", "label": "Franconian Rake"},
                  {"qid": "Q3799048", "label": "inquartato in grembi ritondati"},
                  {"qid": "Q3800675", "label": "interzato abbracciato"},
                  {"qid": "Q3800678", "label": "interzato in grembi ritondati"},
                  {"qid": "Q3800679", "label": "interzato in grembo appuntato"},
                  {"qid": "Q3800686", "label": "interzato in scudetto"},
                  {"qid": "Q3998872", "label": "party per bend"},
                  {"qid": "Q27305194", "label": "party per chevron"},
                  {"qid": "Q3999669", "label": "party per fess"},
                  {"qid": "Q27429803", "label": "party per fess wavy"},
                  {"qid": "Q2672501", "label": "party per pale"},
                  {"qid": "Q30233953", "label": "party per pale embattled"},
                  {"qid": "Q95981351", "label": "party per pale pily"},
                  {"qid": "Q30232869", "label": "party per pale wavy"},
                  {"qid": "Q3799047", "label": "party per saltire"},
                  {"qid": "Q3797569", "label": "per chevron enhanced"},
                  {"qid": "Q3999671", "label": "per fess, the base per pale"},
                  {"qid": "Q3955076", "label": "per fess, the chief per pale"},
                  {"qid": "Q3955087", "label": "per pale, the dexter per fess"},
                  {"qid": "Q3896860", "label": "per pale, the sinister per fess"},
                  {"qid": "Q3799049", "label": "quarterly en equerre"},
                  {"qid": "Q3937798", "label": "recoupé"},
                  {"qid": "Q3932255", "label": "Reinterzato"},
                  {"qid": "Q3936339", "label": "reparti"},
                  {"qid": "Q3800674", "label": "tierced"},
                  {"qid": "Q3800677", "label": "tierced per bend"},
                  {"qid": "Q3800684", "label": "tierced per bend sinister"},
                  {"qid": "Q3800685", "label": "tierced per chevron"},
                  {"qid": "Q3800676", "label": "tierced per fess"},
                  {"qid": "Q3800682", "label": "tierced per pale"},
                  {"qid": "Q3800683", "label": "tierced per pall"},
                  {"qid": "Q27516259", "label": "tierced per pall reversed"},
                  {"qid": "Q3991737", "label": "tiro"}]

    if "category" in work_metadata:
        category_images = api_category_members(work_metadata["category"])
    else:
        category_images = []

    return render_template('item.html',
                           metadata=work_metadata,
                           category_images=category_images,
                           username=username,
                           lang=lang,
                           qid=qid,
                           next_qid=next_qid,
                           brasoes=brasoes,
                           crowns=crowns,
                           colors=colors,
                           partitions=partitions
                           )


if __name__ == '__main__':
    app.run()
