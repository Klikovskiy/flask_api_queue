from flask import Flask
from flask import render_template
from flask_restful import Resource, Api, reqparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from tools.base_connector import (
    Queue,
    init_resource_statuses,
    ResourceStatus,
    enable_resource,
    disable_resource,
)


def create_app():
    app = Flask(__name__)
    api = Api(app)

    data_base = Queue(DATABASE_URL)

    def get_resource_status(resource_name):
        session = data_base.session()
        try:
            result_status = session.query(ResourceStatus).filter_by(
                resource_name=resource_name).first()
            return result_status
        finally:
            session.close()

    class Results(Resource):
        def get(self):
            result_status = get_resource_status('results')
            if result_status.status == 0:  # Ресурс отключен
                return {'error': 'Forbidden'}, 403

            t_id, r_list = data_base.get_result()
            if t_id is None and r_list is None:
                return {'task_id': t_id, 'results': r_list}
            return r_list

    class Status(Resource):
        def get(self, key):
            result_status = get_resource_status('status')
            if result_status.status == 0:  # Ресурс отключен
                return {'error': 'Forbidden'}, 403

            task_id = int(key)
            res = data_base.get_id_status(task_id)
            return {'status': res}

    class Calculation(Resource):
        def post(self):
            result_status = get_resource_status('calculation')
            if result_status.status == 0:  # Ресурс отключен
                return {'error': 'Forbidden'}, 403

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
            result_status = get_resource_status('secret_get')
            if result_status.status == 0:  # Ресурс отключен
                return {'error': 'Forbidden'}, 403

            task_id, task_str = data_base.get_task()
            return {'task_id': task_id, 'task': task_str}

    class SecretPut(Resource):
        def post(self):
            result_status = get_resource_status('secret_put')
            if result_status.status == 0:  # Ресурс отключен
                return {'error': 'Forbidden'}, 403

            parser = reqparse.RequestParser()
            parser.add_argument('task_id', type=int, required=True)
            parser.add_argument('results', type=str, required=True)
            args = parser.parse_args()

            res = data_base.put_result(args['task_id'], args['results'])
            if res:
                return {'error': 'OK'}, 200
            else:
                return {'error': 'Not Added'}, 405

    class EnableResource(Resource):
        def post(self, resource_name):
            enable_resource(session, resource_name)
            return {'message': 'Resource enabled'}, 200

    class DisableResource(Resource):
        def post(self, resource_name):
            disable_resource(session, resource_name)

            return {'message': 'Resource disabled'}, 200

    @app.route('/resources', methods=['GET'])
    def resources():
        def get_resource_status(resource_name):
            session = data_base.session()
            try:
                result_status = session.query(ResourceStatus).filter_by(
                    resource_name=resource_name).first()
                return result_status
            finally:
                session.close()

        # Получите статус каждого ресурса из базы данных
        resource_statuses = [
            ('results', get_resource_status('results').status),
            ('status', get_resource_status('status').status),
            ('calculation', get_resource_status('calculation').status),
            ('secret_get', get_resource_status('secret_get').status),
            ('secret_put', get_resource_status('secret_put').status)
        ]
        return render_template('resources_control.html',
                               resource_statuses=resource_statuses)

    api.add_resource(EnableResource, '/enable-resource/<string:resource_name>')
    api.add_resource(DisableResource,
                     '/disable-resource/<string:resource_name>')

    api.add_resource(Results, '/api/v1/results')
    api.add_resource(Status, '/api/v1/status/<int:key>')
    api.add_resource(Calculation, '/api/v1/calculation')
    api.add_resource(SecretGet, '/api/v1/secret-get')
    api.add_resource(SecretPut, '/api/v1/secret-put')

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        init_resource_statuses(session)
    app.run(debug=True)