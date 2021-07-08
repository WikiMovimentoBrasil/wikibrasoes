##############################################################
# IMPORTAÇÃO DE BIBLIOTECAS E FUNÇÕES
##############################################################
import os
import json
import yaml
from flask import Flask, render_template, request, session, redirect, url_for, g, jsonify
from flask_babel import Babel, gettext
from wikidata import query_quantidade, query_by_type, query_metadata_of_work, query_next_qid, api_category_members, \
    post_search_entity, get_labels, post_search_query, query_wikidata, query_items
from oauth_wiki import get_username, get_token, raw_post_request
from requests_oauthlib import OAuth1Session
from datetime import datetime

##############################################################
# INICIALIZAÇÃO
##############################################################
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
    base_url = 'https://www.wikidata.org/w/index.php'
    request_token_url = base_url + '?title=Special%3aOAuth%2finitiate'

    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          callback_uri='oob')
    fetch_response = oauth.fetch_request_token(request_token_url)

    session['owner_key'] = fetch_response.get('oauth_token')
    session['owner_secret'] = fetch_response.get('oauth_token_secret')

    base_authorization_url = 'https://www.wikidata.org/wiki/Special:OAuth/authorize'
    authorization_url = oauth.authorization_url(base_authorization_url,
                                                oauth_consumer_key=client_key)
    return redirect(authorization_url)


@app.route("/oauth-callback", methods=["GET"])
def oauth_callback():
    base_url = 'https://www.wikidata.org/w/index.php'
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
    username = get_username()
    lang = pt_to_ptbr(get_locale())
    return render_template('error.html',
                           username=username,
                           lang=lang)


# Função para exibir a tela inicial do aplicativo
@app.route('/')
@app.route('/home')
@app.route('/inicio')
def inicio():
    username = get_username()
    lang = pt_to_ptbr(get_locale())
    return render_template('inicio.html',
                           username=username,
                           lang=lang)


# Função para exibir a tela de descrição do aplicativo
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


# Função para exibir a tela com o vídeo tutorial do aplicativo
@app.route('/tutorial')
def tutorial():
    username = get_username()
    lang = pt_to_ptbr(get_locale())
    return render_template('tutorial.html',
                           username=username,
                           lang=lang)


# Função para exibir a tela de descrição dos outros aplicativos
@app.route('/apps')
def apps():
    username = get_username()
    lang = pt_to_ptbr(get_locale())
    return render_template('apps.html',
                           username=username,
                           lang=lang)


# Função para exibir a tela das obras de uma coleção
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


# Função para exibir a tela principal do aplicativo
@app.route('/item/<qid>', methods=["GET"])
def item(qid):
    username = get_username()
    lang = pt_to_ptbr(get_locale())
    iconography = ["Q3305213", "Q93184"]

    with open(os.path.join(app.static_folder, 'queries.json')) as category_queries:
        all_queries = json.load(category_queries)

    metadata_query = all_queries["Metadados"]["query"].replace("LANGUAGE", lang).replace("QIDDAOBRA", qid)
    next_qid_query = all_queries["Next_qid"]["query"].replace("QIDDAOBRA", qid)
    work_metadata = query_metadata_of_work(metadata_query, lang=lang)

    if "instancia" in work_metadata and work_metadata["instancia"]:
        for instancia in work_metadata["instancia"]:
            if instancia.split("@")[0] in iconography:
                next_qid_query = next_qid_query.replace(
                    "OPTIONAL{?obra_next wdt:P180 wd:Q14659.}",
                    "?obra_next wdt:P180 wd:Q14659.")

    next_qid = query_next_qid(next_qid_query)

    # brasoes = query_items(all_queries["brasoes"]["query"].replace("LANGUAGE", lang))
    brasoes = [
        {"qid": "Q5198811", "label": {"pt-br": "Brasão da cidade de São Paulo", "en": "Coat of arms of São Paulo"}},
        {"qid": "Q107366396",
         "label": {"pt-br": "Brasão da Família Souza Queiróz", "en": "Coat of arms of Souza Queiróz Family"}},
        {"qid": "Q107366391", "label": {"pt-br": "Brasão de Amparo", "en": "Coat of arms of Amparo"}},
        {"qid": "Q9664727", "label": {"pt-br": "Brasão de Campinas", "en": "Coat of arms of Campinas"}},
        {"qid": "Q107366378", "label": {"pt-br": "Brasão de Cananeia", "en": "Coat of arms of Cananeia"}},
        {"qid": "Q107366377", "label": {"pt-br": "Brasão de Capivarí", "en": "Coat of arms of Capivarí"}},
        {"qid": "Q20055797", "label": {"pt-br": "Brasão de Franca", "en": "Coat of arms of Franca"}},
        {"qid": "Q18462982", "label": {"pt-br": "Brasão de Guaratinguetá", "en": "Coat of arms of Guaratinguetá"}},
        {"qid": "Q9665074", "label": {"pt-br": "Brasão de Guarulhos", "en": "Coat of arms of Guarulhos"}},
        {"qid": "Q107366376", "label": {"pt-br": "Brasão de Ibitinga", "en": "Coat of arms of Ibitinga"}},
        {"qid": "Q107366395", "label": {"pt-br": "Brasão de Itanhaém", "en": "Coat of arms of Itanhaém"}},
        {"qid": "Q107366394", "label": {"pt-br": "Brasão de Itú", "en": "Coat of arms of Itú"}},
        {"qid": "Q107366393", "label": {"pt-br": "Brasão de Jaboticabal", "en": "Coat of arms of Jaboticabal"}},
        {"qid": "Q9665234", "label": {"pt-br": "Brasão de Jacareí", "en": "Coat of arms of Jacareí"}},
        {"qid": "Q107366379", "label": {"pt-br": "Brasão de Jaú", "en": "Coat of arms of Jaú"}},
        {"qid": "Q9665267", "label": {"pt-br": "Brasão de Joinville", "en": "Coat of arms of Joinville"}},
        {"qid": "Q9665281", "label": {"pt-br": "Brasão de Jundiaí", "en": "Coat of arms of Jundiaí"}},
        {"qid": "Q107366372", "label": {"pt-br": "Brasão de Laguna", "en": "Coat of arms of Laguna"}},
        {"qid": "Q107366387", "label": {"pt-br": "Brasão de Lorena", "en": "Coat of arms of Lorena"}},
        {"qid": "Q18463362", "label": {"pt-br": "Brasão de Mogi das Cruzes", "en": "Coat of arms of Mogi das Cruzes"}},
        {"qid": "Q20058877", "label": {"pt-br": "Brasão de Monte Alto", "en": "Coat of arms of Monte Alto"}},
        {"qid": "Q107366375", "label": {"pt-br": "Brasão de Porto Feliz", "en": "Coat of arms of Porto Feliz"}},
        {"qid": "Q107366388", "label": {"pt-br": "Brasão de Porto Seguro", "en": "Coat of arms of Porto Seguro"}},
        {"qid": "Q107366373", "label": {"pt-br": "Brasão de Santana de Parnaíba", "en": "Coat of arms of Parnaíba"}},
        {"qid": "Q25442792", "label": {"pt-br": "Brasão de Santo Amaro", "en": "Coat of arms of Santo Amaro"}},
        {"qid": "Q107366385", "label": {"pt-br": "Brasão de Santo André", "en": "Coat of arms of Santo André"}},
        {"qid": "Q9665758", "label": {"pt-br": "Brasão de Santos", "en": "Coat of arms of Santos"}},
        {"qid": "Q107366383", "label": {"pt-br": "Brasão de São Bernardo", "en": "Coat of arms of São Bernardo"}},
        {"qid": "Q107366386", "label": {"pt-br": "Brasão de São Carlos", "en": "Coat of arms of São Carlos"}},
        {"qid": "Q9665808",
         "label": {"pt-br": "Brasão de São Francisco do Sul", "en": "Coat of arms of São Francisco do Sul"}},
        {"qid": "Q9665832",
         "label": {"pt-br": "Brasão de São José do Rio Preto", "en": "Coat of arms of São José do Rio Preto"}},
        {"qid": "Q18463792",
         "label": {"pt-br": "Brasão de São José dos Campos", "en": "Coat of arms of São José dos Campos"}},
        {"qid": "Q107366389", "label": {"pt-br": "Brasão de São Sebastião", "en": "Coat of arms of São Sebastião"}},
        {"qid": "Q9665890", "label": {"pt-br": "Brasão de São Vicente", "en": "Coat of arms of São Vicente"}},
        {"qid": "Q107366381", "label": {"pt-br": "Brasão de Socorro", "en": "Coat of arms of Socorro"}},
        {"qid": "Q107366384", "label": {"pt-br": "Brasão de Sorocaba", "en": "Coat of arms of Sorocaba"}},
        {"qid": "Q107366380", "label": {"pt-br": "Brasão de Tatuí", "en": "Coat of arms of Tatuí"}},
        {"qid": "Q9665926", "label": {"pt-br": "Brasão de Taubaté", "en": "Coat of arms of Taubaté"}},
        {"qid": "Q18463877", "label": {"pt-br": "Brasão de Tietê", "en": "Coat of arms of Tietê"}},
        {"qid": "Q107366390", "label": {"pt-br": "Brasão de Ubatuba", "en": "Coat of arms of Ubatuba"}},
        {"qid": "Q107366382", "label": {"pt-br": "Brasão de Vassouras", "en": "Coat of arms of Vassouras"}},
        {"qid": "Q8778141", "label": {"pt-br": "Brasão do estado de São Paulo", "en": "Coat of arms of São Paulo"}},
        {"qid": "Q107366397",
         "label": {"pt-br": "Brasão do Marquez de Valença", "en": "Coat of arms of the Marquis of Valença"}}]

    languages = [{"label": gettext("Português brasileiro"), "iso": "pt-br"},
                 {"label": gettext("Português"), "iso": "pt"},
                 {"label": gettext("Latim"), "iso": "la"},
                 {"label": gettext("Inglês"), "iso": "en"},
                 {"label": gettext("Espanhol"), "iso": "es"},
                 {"label": gettext("Francês"), "iso": "fr"},
                 {"label": gettext("Alemão"), "iso": "de"}]

    crowns = query_items(all_queries["crowns"]["query"].replace("LANGUAGE", lang))

    colors = [
        {"label": {"pt-br": "Metais", "en": "Metals"},
         "list": [{"qid": "Q936472", "label": {"pt-br": "argent", "en": "argent"}},
                  {"qid": "Q430099", "label": {"pt-br": "or", "en": "or"}}]},
        {"label": {"pt-br": "Cores", "en": "Colours"},
         "list": [{"qid": "Q1785501", "label": {"pt-br": "azure", "en": "azure"}},
                  {"qid": "Q858055", "label": {"pt-br": "gules", "en": "gules"}},
                  {"qid": "Q4401253", "label": {"pt-br": "purpure", "en": "purpure"}},
                  {"qid": "Q936496", "label": {"pt-br": "sable", "en": "sable"}},
                  {"qid": "Q936535", "label": {"pt-br": "vert", "en": "vert"}}]},
        {"label": {"pt-br": "Manchas", "en": "Stains"},
         "list": [{"qid": "Q10858582", "label": {"pt-br": "murrey", "en": "murrey"}},
                  {"qid": "Q218177", "label": {"pt-br": "sanguinho", "en": "sanguine"}},
                  {"qid": "Q218169", "label": {"pt-br": "tenné", "en": "tenné"}}]},
        {"label": {"pt-br": "Peles", "en": "Furs"},
         "list": [{"qid": "Q384324", "label": {"pt-br": "arminho", "en": "ermine"}},
                  {"qid": "Q356887", "label": {"pt-br": "veiro", "en": "vair"}}]},
        {"label": {"pt-br": "Metais não-tradicionais", "en": "Non-traditional metals"},
         "list": [{"qid": "Q88219768", "label": {"pt-br": "aço", "en": "steel"}},
                  {"qid": "Q107348978", "label": {"pt-br": "bronze", "en": "bronze"}},
                  {"qid": "Q107348994", "label": {"pt-br": "chumbo", "en": "lead"}},
                  {"qid": "Q15830500", "label": {"pt-br": "cobre", "en": "copper"}},
                  {"qid": "Q3743211", "label": {"pt-br": "ferro", "en": "iron"}}]},
        {"label": {"pt-br": "Cores não-tradicionais", "en": "Non-traditional colours"},
         "list": [{"qid": "Q107349007", "label": {"pt-br": "amaranto", "en": "amaranth"}},
                  {"qid": "Q1055869", "label": {"pt-br": "azul-celeste", "en": "bleu celeste"}},
                  {"qid": "Q105721308", "label": {"pt-br": "brunâtre", "en": "brunâtre"}},
                  {"qid": "Q1663655", "label": {"pt-br": "carnação", "en": "carnation"}},
                  {"qid": "Q218173", "label": {"pt-br": "cendrée", "en": "cendrée"}},
                  {"qid": "Q1867823", "label": {"pt-br": "cor natural", "en": "natural color"}},
                  {"qid": "Q3040333", "label": {"pt-br": "laranja", "en": "orange"}},
                  {"qid": "Q16977936", "label": {"pt-br": "rosa", "en": "rose"}}]}
    ]

    partitions = query_items(all_queries["partitions"]["query"].replace("LANGUAGE", lang))

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
                           partitions=partitions,
                           languages=languages
                           )


@app.route('/brasao', methods=["GET"])
def brasao():
    username = get_username()
    lang = pt_to_ptbr(get_locale())
    return render_template("brasao.html",
                           username=username,
                           lang=lang)


def no_brasao(form):
    username = get_username()
    lang = pt_to_ptbr(get_locale())
    date = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    qid = form["qid"]
    next_qid = form["next_qid"]
    done = False

    with open(os.path.join(app.static_folder, 'no-coats-depicted.json'), "r", encoding="utf-8") as no_brasao_file:
        all_items = json.load(no_brasao_file)
        if "list_of_items" in all_items and qid in all_items["list_of_items"]:
            for item in all_items["list_of_items"][qid]:
                if item["username"] == username:
                    item["timestamp"] = date
                    done = True
            if not done:
                all_items["list_of_items"][qid].append({"username": username, "timestamp": date})
        else:
            all_items["list_of_items"][qid] = [{"username": username, "timestamp": date}]

    if all_items:
        with open(os.path.join(app.static_folder, 'no-coats-depicted.json'), "w", encoding="utf-8") as no_brasao_file:
            json.dump(all_items, no_brasao_file)

    template_data = {'redirect_url': url_for('item', qid=next_qid),
                     'username': username,
                     'lang': lang}

    return template_data


def brasao_missing(form):
    username = get_username()
    lang = pt_to_ptbr(get_locale())
    date = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    qid = form["qid"]
    next_qid = form["next_qid"]
    done = False
    brasao_name = ""

    if "brasao_name" in form and form["brasao_name"]:
        brasao_name = form["brasao_name"]

    with open(os.path.join(app.static_folder, 'coats-missing.json'), "r", encoding="utf-8") as brasao_missing_file:
        all_items = json.load(brasao_missing_file)
        if "list_of_items" in all_items and qid in all_items["list_of_items"]:
            for item in all_items["list_of_items"][qid]:
                if item["username"] == username:
                    item["timestamp"] = date
                    item["coats_of_arms"] = brasao_name
                    done = True
            if not done:
                all_items["list_of_items"][qid].append(
                    {"username": username, "timestamp": date, "coats_of_arms": brasao_name})
        else:
            all_items["list_of_items"][qid] = [
                {"username": username, "timestamp": date, "coats_of_arms": brasao_name}]
    if all_items:
        with open(os.path.join(app.static_folder, 'coats-missing.json'), "w", encoding="utf-8") as brasao_missing_file:
            json.dump(all_items, brasao_missing_file)

    template_data = {'redirect_url': url_for('item', qid=next_qid),
                     'username': username,
                     'lang': lang}

    return template_data


@app.route('/send_brasao', methods=["POST"])
def send_brasao():
    username = get_username()
    lang = pt_to_ptbr(get_locale())

    form = request.form

    if "has_brasao" in form and form["has_brasao"] == "no":
        return render_template("success.html", **no_brasao(form))
    if "has_brasao" in form and form["has_brasao"] == "yes":
        if "brasao" in form and form["brasao"] != "no":
            # add_p180(form["qid"], form["brasao"])
            values_already_on_wd = get_item(form["brasao"])
            statements = []

            # COROA
            if "coroa" in form and form["coroa"] != "no":
                coroa = form["coroa"]
                coroa_cor = []

                if "coroa_cor" in form and form["coroa_cor"] != "no":
                    coroa_cor = request.form.getlist("coroa_cor")

                edit_or_create = check_items(values_already_on_wd, coroa, "Q908430")
                statements.append(make_stat(
                    "P180",
                    coroa,
                    [{"pq": "P1114", "type": "number", "val": 1}] +
                    [{"pq": "P462", "type": "qid", "val": y} for y in coroa_cor if y != "no"] +
                    [{"pq": "P1354", "type": "qid", "val": "Q908430"}],
                    edit_or_create))

            # ELMO
            if "elmo" in form and form["elmo"] != "no":
                elmo_cor = []

                if "elmo_cor" in form and form["elmo_cor"] != "no":
                    elmo_cor = request.form.getlist("elmo_cor")

                edit_or_create = check_items(values_already_on_wd, "Q910873", "")
                statements.append(make_stat(
                    "P180",
                    "Q910873",
                    [{"pq": "P1114", "type": "number", "val": 1}] +
                    [{"pq": "P462", "type": "qid", "val": y} for y in elmo_cor if y != "no"],
                    edit_or_create))

            # PAQUIFE
            if "paquife" in form and form["paquife"] != "no":
                paquife_cor = []

                if "paquife_cor" in form and form["paquife_cor"] != "no":
                    paquife_cor = request.form.getlist("paquife_cor")

                edit_or_create = check_items(values_already_on_wd, "Q1289089", "")
                statements.append(make_stat(
                    "P180",
                    "Q1289089",
                    [{"pq": "P462", "type": "qid", "val": y} for y in paquife_cor if y != "no"],
                    edit_or_create))

            # VIROL
            if "virol" in form and form["virol"] != "no":
                virol_cor = []

                if "virol_cor" in form and form["virol_cor"] != "no":
                    virol_cor = request.form.getlist("virol_cor")

                edit_or_create = check_items(values_already_on_wd, "Q910873", "")
                statements.append(make_stat(
                    "P180",
                    "Q910873",
                    [{"pq": "P462", "type": "qid", "val": y} for y in virol_cor if y != "no"],
                    edit_or_create))

            # CAMPO
            if "campo" in form and form["campo"]:
                divisao = []
                campo_cor = []

                if "divisao" in form and form["divisao"] != "no":
                    divisao = request.form.getlist("divisao")

                if "campo_cor" in form and form["campo_cor"] != "no":
                    campo_cor = request.form.getlist("campo_cor")

                edit_or_create = check_items(values_already_on_wd, "Q372254", "")
                statements.append(make_stat(
                    "P180",
                    "Q372254",
                    [{"pq": "P1354", "type": "qid", "val": x} for x in divisao] +
                    [{"pq": "P462", "type": "qid", "val": y} for y in campo_cor if y != "no"],
                    edit_or_create))

            # FIGURA
            if "figura" in form:
                figura_values = [figura_aux.split("@") for figura_aux in request.form.getlist("figura")]
                for figura in figura_values:
                    edit_or_create = check_items(values_already_on_wd, figura[0], "Q1424805")
                    statements.append(make_stat(
                        "P180",
                        figura[0],
                        [{"pq": "P1354", "type": "qid", "val": "Q1424805"}] +
                        [{"pq": "P1114", "type": "number", "val": figura[1]}] +
                        [{"pq": "P462", "type": "qid", "val": y} for y in figura[2].split(",") if y != "no"],
                        edit_or_create))

            # SUPORTE
            if "suporte" in form:
                suporte_values = [suporte_aux.split("@") for suporte_aux in request.form.getlist("suporte")]

                for suporte in suporte_values:
                    edit_or_create = check_items(values_already_on_wd, suporte[0], "Q725975")
                    statements.append(make_stat(
                        "P180",
                        suporte[0],
                        [{"pq": "P1354", "type": "qid", "val": "Q725975"}] +
                        [{"pq": "P1114", "type": "number", "val": suporte[1]}] +
                        [{"pq": "P462", "type": "qid", "val": y} for y in suporte[2].split(",") if y != "no"],
                        edit_or_create))

            # TIMBRE
            if "timbre" in form:
                timbre_values = [timbre_aux.split("@") for timbre_aux in request.form.getlist("timbre")]

                for timbre in timbre_values:
                    edit_or_create = check_items(values_already_on_wd, timbre[0], "Q668732")
                    statements.append(make_stat(
                        "P180",
                        timbre[0],
                        [{"pq": "P1354", "type": "qid", "val": "Q668732"}] +
                        [{"pq": "P1114", "type": "number", "val": timbre[1]}] +
                        [{"pq": "P462", "type": "qid", "val": y} for y in timbre[2].split(",") if y != "no"],
                        edit_or_create))

            # LEMA
            if "lema" in form and form["lema"]:
                lema = form["lema"]
                if "lema_lang" in form and form["lema_lang"] != "no":
                    lema_lang = form["lema_lang"]
                    edit_or_create = check_items(values_already_on_wd, lema, "")
                    statements.append(make_monolingual_stat("P1451", lema, lema_lang, edit_or_create))
                    # TODO: Adicionar possibilidade de inserir listel com cor e texto do lema

            statements = {"claims": statements}
            post_item(json.dumps(statements), form["brasao"])

            if "next_qid" in form and form["next_qid"]:
                next_qid = form["next_qid"]
            else:
                next_qid = form["qid"]

            template_data = {'redirect_url': url_for('item', qid=next_qid),
                             'username': username,
                             'lang': lang}
            return render_template("success.html", **template_data)
        elif "brasao" in form and form["brasao"] == "no":
            return render_template("success.html", **brasao_missing(form))

    return redirect(url_for("item", qid=form["qid"]))


def add_p180(qid, brasao):
    try:
        values_already_on_wd = get_item(qid)
        edit_or_create = check_items(values_already_on_wd, brasao, "")
        statements = {"claims": [make_stat("P180", brasao, [], edit_or_create)]}
        post_item(json.dumps(statements), qid)
    except:
        pass


def get_item(qid):
    items = []
    values = query_wikidata("SELECT DISTINCT ?p ?ps ?pqv WHERE { wd:" +
                            qid +
                            " p:P180|p:P1451 ?p. OPTIONAL {?p ps:P180|ps:P1451 ?ps}. OPTIONAL {?p pq:P1354 ?pqv.} } ORDER BY DESC(?pqv)")
    if "results" in values and "bindings" in values["results"]:
        for result in values["results"]["bindings"]:
            item = {}
            if "p" in result:
                item["id"] = result["p"]["value"].replace("http://www.wikidata.org/entity/statement/", "")
            if "ps" in result:
                item["val"] = result["ps"]["value"].replace("http://www.wikidata.org/entity/", "")
            if "pqv" in result:
                item["qual"] = result["pqv"]["value"].replace("http://www.wikidata.org/entity/", "")
            items.append(item)
    return items


def check_items(elements_already_on_wd, val, p1354):
    for element in elements_already_on_wd:
        if "qual" in element:
            if val == element["val"] and p1354 == element["qual"]:
                return element["id"]
        else:
            if val == element["val"]:
                return element["id"]
    return ""


def post_item(statements, qid):
    token = get_token()
    data = statements

    params = {
        "action": "wbeditentity",
        "format": "json",
        "token": token,
        "id": qid,
        "data": data
    }

    result = raw_post_request(params)
    if 'error' in result.json():
        return jsonify('204')
    else:
        return jsonify('200')


def make_stat(prop, val, qualifiers, edit_or_create):
    result_item = {
        "mainsnak":
            {"snaktype": "value",
             "property": prop,
             "datavalue":
                 {
                     "value":
                         {
                             "entity-type": "item",
                             "numeric-id": int(val.strip("Q"))
                         },
                     "type": "wikibase-entityid"
                 }
             },
        "type": "statement",
        "rank": "normal"
    }
    if qualifiers:
        result_item["qualifiers"] = make_qualifiers(qualifiers)

    if edit_or_create:
        result_item["id"] = edit_or_create.replace("-", "$", 1)

    return result_item


def make_monolingual_stat(prop, val, lang, edit_or_create):
    language = lang if lang else "und"

    result_item = {
        "mainsnak":
            {
                "snaktype": "value",
                "property": prop,
                "datavalue":
                    {
                        "value":
                            {
                                "text": val,
                                "language": language
                            },
                        "type": "monolingualtext"
                    }
            },
        "type": "statement",
        "rank": "normal",
    }

    if edit_or_create:
        result_item["id"] = edit_or_create.replace("-", "$", 1)

    return result_item


def make_qualifiers(qualifiers):
    qualificadores = {"P462": [], "P1354": [], "P518": [], "P1114": []}

    for qual in qualifiers:
        if qual["pq"] in ["P462", "P1354", "P518"]:
            qualificadores[qual["pq"]].append({
                "snaktype": "value",
                "property": qual["pq"],
                "datavalue": {
                    "value": {
                        "entity-type": "item",
                        "numeric-id": int(qual["val"].strip("Q"))
                    },
                    "type": "wikibase-entityid"
                },
                "datatype": "wikibase-item"
            })
        elif qual["pq"] in ["P1114"]:
            qualificadores[qual["pq"]].append({
                "snaktype": "value",
                "property": qual["pq"],
                "datavalue": {
                    "value": {
                        "amount": "+" + str(qual["val"]),
                        "unit": "1"
                    },
                    "type": "quantity"
                },
                "datatype": "quantity"
            })
        else:
            pass

    resultados_qual = {}
    for key in qualificadores.keys():
        if qualificadores[key]:
            resultados_qual[key] = qualificadores[key]
    return resultados_qual


# Requisição para procurar entidades e filtrá-las pelos tesauros
@app.route('/search', methods=['GET', 'POST'])
def search_entity():
    if request.method == "POST":
        jsondata = request.get_json()
        term = jsondata['term']
        instance = jsondata['instance']
        lang = pt_to_ptbr(get_locale())

        data_1 = post_search_query(term, lang)
        data_2 = post_search_entity(term, lang)

        new_data = get_labels(data_1) + get_labels(data_2)
        items = []
        for item_ in new_data:
            item_["labelptbr"] = item_["labelpt"] if not item_["labelptbr"] else item_["labelptbr"]
            item_["descrptbr"] = item_["descrpt"] if not item_["descrptbr"] else item_["descrptbr"]
            items.append({"qid": item_["id"],
                          "label": item_["labelptbr"] if lang != "en" else item_["labelen"],
                          "descr": item_["descrptbr"] if lang != "en" else item_["descren"]})

        return jsonify(items), 200


if __name__ == '__main__':
    app.run()
