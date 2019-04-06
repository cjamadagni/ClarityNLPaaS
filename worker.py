import json
import os
import time
import uuid

import requests
from bson.json_util import dumps
from flask import Response
from pymongo import MongoClient

import util

nlpaas_report_list = list()


def get_document_set(source):
    return {
        "alias": "",
        "arguments": [],
        "concept": "",
        "declaration": "documentset",
        "description": "",
        "funct": "createDocumentSet",
        "library": "Clarity",
        "name": "Docs",
        "named_arguments": {
            "query": "source:{}".format(source)
        },
        "values": [],
        "version": ""
    }


def upload_report(data):
    """
    Uploading reports with unique source
    """
    url = util.solr_url + '/update?commit=true'

    headers = {
        'Content-type': 'application/json'
    }

    # Generating a source_id
    rand_uuid = uuid.uuid1()
    source_id = str(rand_uuid)

    payload = list()
    nlpaas_report_list.clear()
    nlpaas_id = 1

    for report in data['reports']:
        id = '{}_{}'.format(source_id, str(nlpaas_id))
        json_body = {
            "report_type": "ClarityNLPaaS Document",
            "id": id,
            "report_id": id,
            "source": source_id,
            "report_date": "1970-01-01T00:00:00Z",
            "subject": "ClarityNLPaaS Document",
            "report_text": report,
            "nlpaas_id": str(nlpaas_id)
        }
        payload.append(json_body)
        nlpaas_report_list.append(id)
        nlpaas_id += 1

    print("\n\nSource ID = " + str(source_id))
    print("\n\nReport List = " + str(nlpaas_report_list))

    response = requests.post(url, headers=headers, data=json.dumps(payload, indent=4))
    if response.status_code == 200:
        return True, source_id
    else:
        return False, response.reason


def delete_report(source_id):
    """
    Deleting reports based on generated source
    """
    url = util.solr_url + '/update?commit=true'

    headers = {
        'Content-type': 'text/xml; charset=utf-8',
    }

    data = '<delete><query>source:%s</query></delete>' % source_id

    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return True, response.reason
    else:
        return False, response.reason


def get_nlpql(file_path):
    """
    Getting required NLPQL based on API route
    """
    with open(file_path, "r") as file:
        content = file.read()

    return content


def submit_job(nlpql_json):
    """
    Submitting ClarityNLP job
    """
    url = util.claritynlp_url + "phenotype"
    phenotype_string = json.dumps(nlpql_json)
    print("")
    print(phenotype_string)
    print("")
    headers = {
        'Content-type': 'application/json'
    }
    response = requests.post(url, headers=headers, data=phenotype_string)
    if response.status_code == 200:
        data = response.json()
        if 'success' in data:
            if not data['success']:
                print(data['error'])
                return False, data['error']
        print("\n\nJob Response:\n")
        print(data)
        return True, data
    else:
        print(response.status_code)
        print(response.reason)
        return False, response.reason


def submit_test(nlpql):
    """
    Testing ClarityNLP job
    """
    url = util.claritynlp_url + "nlpql_tester"
    response = requests.post(url, data=nlpql)
    if response.status_code == 200:
        data = response.json()
        if 'success' in data:
            if not data['success']:
                print(data['error'])
                return False, data['error']
        if 'valid' in data:
            if not data['valid']:
                print(data['valid'])
                return False, data['valid']
        print("\n\nJob Response:\n")
        print(data)
        return True, data
    else:
        print(response.status_code)
        print(response.reason)
        return False, {
            'success': False,
            'status_code': response.status_code,
            'reason': str(response.reason),
            'valid': False
        }


def add_custom_nlpql(nlpql):
    try:
        os.makedirs('./nlpql/custom/')
    except OSError as ex:
        print(ex)

    success, test_json = submit_test(nlpql)
    if not success:
        test_json['message'] = "Failed to upload invalid NLPQL."
        return test_json

    phenotype = test_json['phenotype']
    if not phenotype:
        return {
            'message': 'NLPQL missing phenotype declaration.'
        }
    name = phenotype['name']
    version = phenotype['version']

    if not name or len(name) == 0:
        return {
            'message': 'Phenotype declaration missing name'
        }

    if not version or len(version) == 0:
        return {
            'message': 'Phenotype declaration missing version'
        }
    nlpql_name = 'custom_{}_v{}'.format('_'.join(name.split(' ')), version.replace('.', '-'))
    filename = './nlpql/custom/{}.nlpql'.format(nlpql_name)
    with open(filename, 'w') as the_file:
        the_file.write(nlpql)

    return {
        'message': "Your job is callable via the endpoint '/job/custom/{}'".format(nlpql_name)
    }


def has_active_job(data):
    """
    DoS Protection by allowing user to have only one active job
    """
    # TODO: Query Luigi and see if the user has any current active job
    # If active job is present return
    return False


def get_results(job_id: int, source_data=None, status_endpoint=None):
    """
    Reading Results from Mongo
    TODO use API endpoing
    """
    if not source_data:
        source_data = list()

    # Checking if it is a dev box
    if util.development_mode == "dev" and status_endpoint:
        url = status_endpoint
    else:
        status = "status/%s" % job_id
        url = util.claritynlp_url + status
        print(url)

    # Polling for job completion
    while True:
        r = requests.get(url)

        if r.status_code != 200:
            return Response(json.dumps({'message': 'Could not query job status. Reason: ' + r.reason}, indent=4),
                            status=500,
                            mimetype='application/json')

        if r.json()["status"] == "COMPLETED":
            break

        time.sleep(2.0)

    client = MongoClient(util.mongo_host, util.mongo_port)
    try:
        db = client[util.mongo_db]
        collection = db['phenotype_results']
        results = list(collection.find({'job_id': job_id}))
        if len(source_data) > 0:
            for r in results:
                report_id = r['report_id']
                source = r['source']
                doc_index = int(report_id.replace(source, '').replace('_', '')) - 1
                if doc_index < len(source_data):
                    source_doc = source_data[doc_index]
                    r['report_text'] = source_doc
                else:
                    r['report_text'] = r['sentence']

        result_string = dumps(results)
    except Exception as ex:
        print(ex)
        result_string = """{
            "message": "Unable to query results, {}."
        }""".format(str(ex))
    finally:
        client.close()
    return result_string


def clean_output(data):
    """
    Function to clean output JSON
    """
    data = json.loads(data)

    # iterate through to check for report_ids that are empty and assign report count from original report_list
    for obj in data:
        report_id = obj["report_id"].split('_')
        nlpaas_array_id = report_id[1]
        if obj["report_id"] in nlpaas_report_list:
            obj.update({'nlpaas_report_list_id': nlpaas_array_id})
            nlpaas_report_list.remove(obj["report_id"])
    # return null response for reports with no results
    for item in nlpaas_report_list:
        item_id = item.split('_')
        nlpaas_array_id = int(item_id[1])
        data += [{'nlpaas_report_list_id': nlpaas_array_id, 'nlpql_feature': 'null'}]

    # keys = ['_id', 'experiencer', 'report_id', 'source', 'phenotype_final', 'temporality', 'subject', 'concept_code',
    #         'report_type', 'inserted_date', 'negation', 'solr_id', 'end', 'start', 'report_date', 'batch', 
    #         'nlpaas_id', 'owner', 'pipeline_id']

    # for k in keys:
    #     for obj in data:
    #         obj.pop(k, None)

    return json.dumps(data, indent=4, sort_keys=True)


def worker(job_file_path, data):
    """
    Main worker function
    """
    start = time.time()
    # Checking for active Job
    if has_active_job(data):
        return Response(
            json.dumps({'message': 'You currently have an active job. Only one active job allowed'}, indent=4),
            status=200, mimetype='application/json')

    # Uploading report to Solr
    upload_obj = upload_report(data)
    if not upload_obj[0]:
        return Response(json.dumps({'message': 'Could not upload report. Reason: ' + upload_obj[1]}, indent=4),
                        status=500,
                        mimetype='application/json')
    else:
        source_id = upload_obj[1]

    # Getting the nlpql from disk
    nlpql = get_nlpql(job_file_path)

    # Validating the input object
    success, nlpql_json = submit_test(nlpql)
    if not success:
        return Response(json.dumps(nlpql_json, indent=4, sort_keys=True), status=400, mimetype='application/json')
    doc_set = get_document_set(source_id)
    nlpql_json['document_sets'] = list()
    nlpql_json['document_sets'].append(doc_set)

    docs = ["Docs"]
    data_entities = nlpql_json['data_entities']
    for de in data_entities:
        de['named_arguments']['documentset'] = docs
    nlpql_json['data_entities'] = data_entities

    # Submitting the job
    job_success, job_info = submit_job(nlpql_json)
    if not job_success:
        return Response(json.dumps({'message': 'Could not submit job. Reason: ' + job_info}, indent=4),
                        status=500,
                        mimetype='application/json')

    # Getting the results of the Job
    job_id = int(job_info['job_id'])
    print("\n\njob_id = " + str(job_id))
    results = get_results(job_id, source_data=data['reports'], status_endpoint=job_info['status_endpoint'])

    # Deleting uploaded documents
    delete_obj = delete_report(source_id)
    if not delete_obj[0]:
        return Response(json.dumps({'message': 'Could not delete report. Reason: ' + delete_obj[1]}, indent=4),
                        status=500,
                        mimetype='application/json')

    print("\n\nRun Time = %s \n\n" % (time.time() - start))
    return Response(clean_output(results), status=200, mimetype='application/json')
