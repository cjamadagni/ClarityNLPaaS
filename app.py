from flask import Flask, request, jsonify, Response
from worker import worker
import json
import os

app = Flask(__name__)


def validJob(jobType):
    validJobs = os.listdir("nlpql")
    return jobType in validJobs



@app.route("/")
def hello():
    return "Welcome to ClarityNLPaaS"


"""
API for triggering jobs
"""
@app.route("/job/<jobType>", methods=['POST', 'GET'])
def submitJob(jobType):
    if request.method == 'POST':
        jobType += ".nlpql"
        # Checking if the selected job is valid
        if not validJob(jobType):
            return Response(json.dumps({'message': 'Invalid API route'}), status=400, mimetype='application/json')
        else:
            data = request.get_json()
            jobFilePath = "nlpql/" + jobType
            return worker(jobFilePath, data)
    else:
        return Response(json.dumps({'message': 'API supports only POST requests'}), status=400, mimetype='application/json')




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6000, debug=True)
