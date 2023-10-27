from flask import Flask
from flask_restful import Resource, Api, reqparse

from config import DATABASE_URL
from tools.base_connector import Queue


def create_app():
    app = Flask(__name__)
    api = Api(app)

    data_base = Queue(DATABASE_URL)

    class Results(Resource):
        def get(self):
            t_id, r_list = data_base.get_result()
            if t_id is None and r_list is None:
                return {'task_id': t_id, 'results': r_list}
            return r_list

    class Status(Resource):
        def get(self, key):
            task_id = int(key)
            res = data_base.get_id_status(task_id)
            return {'status': res}

    class Calculation(Resource):
        def post(self):
            parser = reqparse.RequestParser()
            parser.add_argument('task_id', type=int, required=True)
            parser.add_argument('task', type=str, required=True)
            args = parser.parse_args()

            res = data_base.put_task(args['task_id'], args['task'])
            if res:
                return {'error': 'OK'}, 201
            else:
                return {'error': 'Not Added'}, 405

    class SecretGet(Resource):
        def get(self):
            task_id, task_str = data_base.get_task()
            return {'task_id': task_id, 'task': task_str}

    class SecretPut(Resource):
        def post(self):
            parser = reqparse.RequestParser()
            parser.add_argument('task_id', type=int, required=True)
            parser.add_argument('results', type=str, required=True)
            args = parser.parse_args()

            res = data_base.put_result(args['task_id'], args['results'])
            if res:
                return {'error': 'OK'}, 200
            else:
                return {'error': 'Not Added'}, 405

    api.add_resource(Results, '/api/v1/results')
    api.add_resource(Status, '/api/v1/status/<int:key>')
    api.add_resource(Calculation, '/api/v1/calculation')
    api.add_resource(SecretGet, '/api/v1/secret-get')
    api.add_resource(SecretPut, '/api/v1/secret-put')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
