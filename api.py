import json
import os
import util

from flask import Flask, request, Response
from flask_cors import CORS

from worker import get_results, worker, submit_test, add_custom_nlpql, get_nlpql, get_file, async_results

application = Flask(__name__)
CORS(application)


def get_files(files, path):
    for (directory_path, directory_names, file_names) in os.walk(path):
        for d in directory_names:
            get_files(files, directory_path + '/' + d)
        for f in file_names:
            path = (directory_path + '/' + f[0:f.find('.')]).replace('nlpql/', '')
            files.append(path)


def get_nlpql_options(with_sorting=True):
    results = list()
    get_files(results, 'nlpql')

    unique = list(set(results))
    if with_sorting:
        return sorted(unique)
    else:
        return unique


def get_json(files, path):
    for (directory_path, directory_names, file_names) in os.walk(path):
        for d in directory_names:
            get_json(files, directory_path + '/' + d)
        for f in file_names:
            if f.endswith('json'):
                path = (directory_path + '/' + f[0:f.find('.')]).replace('nlpql/', '')
                files.append(path)


def get_nlpql_questions(results=None, with_sorting=True):
    results = list()
    get_json(results, 'nlpql')

    unique = list(set(results))
    if with_sorting:
        return sorted(unique)
    else:
        return unique


def valid_job(job_type):
    return job_type in get_nlpql_options(with_sorting=False)


def get_api_routes():
    return ', '.join(get_nlpql_options())


@application.route("/")
def hello():
    return "Welcome to ClarityNLPaaS."


def get_host(r):
    # print(request.headers)
    if r.is_secure:
        return 'https://{0}/'.format(r.host)
    else:
        return 'http://{0}/'.format(r.host)


@application.route("/job/<job_category>/<job_subcategory>/<job_name>", methods=['POST', 'GET'])
def submit_job_with_subcategory(job_category: str, job_subcategory: str, job_name: str):
    """
    API for triggering jobs
    """
    h = get_host(request)
    # print(h)

    try:
        async_job = request.args.get('async') == 'true'
    except:
        async_job = False

    try:
        return_null_results = request.args.get('return_null_results') == 'true'
    except:
        return_null_results = False
    synchronous = not async_job
    job_type = "{}/{}/{}".format(job_category, job_subcategory, job_name)
    job_file_path = "./nlpql/" + job_type + ".nlpql"
    if not valid_job(job_type):
        return Response(json.dumps({'message': 'Invalid API route. Valid Routes: ' + get_api_routes()}, indent=4,
                                   sort_keys=True), status=400,
                        mimetype='application/json')
    if request.method == 'POST':
        # Checking if the selected job is valid
        data = request.get_json()
        return worker(job_file_path, data, synchronous=synchronous, return_null_results=return_null_results)
    else:

        return Response(get_nlpql(job_file_path),
                        status=200,
                        mimetype='text/plain')


@application.route("/job/<job_category>/<job_name>", methods=['POST', 'GET'])
def submit_job_with_category(job_category: str, job_name: str):
    """
    API for triggering jobs
    """
    h = get_host(request)
    # print(h)

    try:
        async_arg = request.args.get('async').lower()
        async_job = async_arg == 'true' or async_arg == 't' or async_arg == '1'
    except:
        async_job = False
    synchronous = not async_job
    job_type = "{}/{}".format(job_category, job_name)
    job_file_path = "./nlpql/" + job_type + ".nlpql"
    if not valid_job(job_type):
        return Response(json.dumps({'message': 'Invalid API route. Valid Routes: ' + get_api_routes()}, indent=4,
                                   sort_keys=True), status=400,
                        mimetype='application/json')
    if request.method == 'POST':
        # Checking if the selected job is valid
        data = request.get_json()
        return worker(job_file_path, data, synchronous=synchronous)
    else:

        return Response(get_nlpql(job_file_path),
                        status=200,
                        mimetype='text/plain')


@application.route("/job/<job_type>", methods=['POST', 'GET'])
def submit_job(job_type: str):
    """
    API for triggering jobs
    """
    h = get_host(request)
    # print(h)

    job_type = job_type.replace('~', '/')
    job_file_path = "./nlpql/" + job_type + ".nlpql"
    valid = valid_job(job_type)
    try:
        async_job = request.args.get('async') == 'true'
    except:
        async_job = False
    try:
        return_null_results = request.args.get('return_null_results') == 'false'
    except:
        return_null_results = False
    synchronous = not async_job

    if request.method == 'POST':
        # Checking if the selected job is valid
        if (job_type == 'validate_nlpql' or job_type == 'nlpql_tester') and request.data:
            _, res = submit_test(request.data)
            return json.dumps(res, indent=4, sort_keys=True)
        elif job_type == 'register_nlpql' and request.data:
            res = request.data.decode("utf-8")
            return json.dumps(add_custom_nlpql(res), indent=4, sort_keys=True)
        elif job_type == 'results' and request.data:
            res = request.get_json()
            return async_results(res['job_id'], res['source_id'], return_null_results=return_null_results)
        else:
            if not valid:
                return Response(
                    json.dumps({'message': 'Invalid API route. Valid Routes: ' + get_api_routes()}, indent=4,
                               sort_keys=True), status=400,
                    mimetype='application/json')
            data = request.get_json()
            return worker(job_file_path, data, synchronous=synchronous)
    else:
        if not valid:
            return Response(json.dumps({'message': 'Invalid API route. Valid Routes: ' + get_api_routes()}, indent=4,
                                       sort_keys=True), status=400,
                            mimetype='application/json')
        return Response(get_nlpql(job_file_path),
                        status=200,
                        mimetype='text/plain')


@application.route("/job/results/<job_id>", methods=['GET'])
def get_results(job_id):
    """
    API for getting Job results
    """
    if request.method == 'GET':
        return get_results(job_id)
    else:
        return Response(json.dumps({'message': 'API supports only GET requests'}, indent=4, sort_keys=True), status=400,
                        mimetype='application/json')


@application.route("/job/list/all", methods=['GET'])
def get_nlpql_list():
    """
    API for getting NLPQL Options
    """
    if request.method == 'GET':
        return Response(json.dumps(get_nlpql_options()), status=200, mimetype='application/json')
    else:
        return Response(json.dumps({'message': 'API supports only GET requests'}, indent=4, sort_keys=True), status=400,
                        mimetype='application/json')


@application.route("/form/questions/all", methods=['GET'])
def get_question_list():
    """
    API for getting NLPQL questions
    """
    if request.method == 'GET':
        return Response(json.dumps(get_nlpql_questions()), status=200, mimetype='application/json')
    else:
        return Response(json.dumps({'message': 'API supports only GET requests'}, indent=4, sort_keys=True), status=400,
                        mimetype='application/json')


@application.route("/form/<form_category>/<form_subcategory>/<form_name>", methods=['POST', 'GET'])
def get_form_with_subcategory(form_category: str, form_subcategory: str, form_name: str):
    file_type = "{}/{}/{}".format(form_category, form_subcategory, form_name)
    file_path = "./nlpql/" + file_type + ".json"
    return Response(get_file(file_path),
                    status=200,
                    mimetype='application/json')


@application.route("/form/<form_category>/<form_name>", methods=['POST', 'GET'])
def get_form_with_category(form_category: str, form_name: str):
    file_type = "{}/{}".format(form_category, form_name)
    file_path = "./nlpql/" + file_type + ".json"
    return Response(get_file(file_path),
                    status=200,
                    mimetype='application/json')


@application.route("/form/<form_type>", methods=['POST', 'GET'])
def get_form(form_type: str):
    form_type = form_type.replace('~', '/')
    file_path = "./nlpql/" + form_type + ".json"

    return Response(get_file(file_path),
                    status=200,
                    mimetype='application/json')


if __name__ == '__main__':
    util.app_token()
    application.run(host='0.0.0.0', port=5000, debug=True)
    util.set_logger(application.logger)
