from flask import Flask, request, send_file
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
    disable_resource, get_resource_count_from_database, Task,
    Result,
)


def create_app(session=None):
    app = Flask(__name__)
    api = Api(app)

    if session is None:
        # Если сеанс не передается, создайте новый сеанс с использованием sessionmaker
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        init_resource_statuses(session)

    data_base = Queue(DATABASE_URL)

    def get_resource_status(resource_name):
        try:
            result_status = session.query(ResourceStatus).filter_by(
                resource_name=resource_name).first()
            return result_status
        finally:
            session.close()

    class Show(Resource):
        """ Получить id задач в зависимости от их статуса. """

        def get(self):
            result_status = get_resource_status('results')
            if result_status is not None and result_status.status == 0:
                return {'error': 'Forbidden'}, 403

            # Еще не взяты в расчет
            income_tasks = session.query(Task.id_tasks).filter(
                Task.flag == 0
            ).all()

            # Решаются.
            calculation_tasks = session.query(Task.id_tasks).filter(
                Task.flag == 1
            ).all()

            # Уже готовы.
            calculated_tasks = session.query(Result.id_tasks).filter().all()

            income_list = [task[0] for task in income_tasks]
            calculation_list = [task[0] for task in calculation_tasks]
            calculated_list = [task[0] for task in calculated_tasks]

            return {
                'income': income_list,
                'calculation': calculation_list,
                'calculated': calculated_list
            }

    class Results(Resource):
        def get(self):
            result_status = get_resource_status('results')
            if result_status is not None and result_status.status == 0:
                return {'error': 'Forbidden'}, 403

            t_id, r_list = data_base.get_result()
            # Обновляем статистику
            data_base.update_time_statistics(t_id, 'results')
            return {'task_id': t_id, 'results': r_list}

    class Status(Resource):
        def get(self, key):
            result_status = get_resource_status('status')
            if result_status is not None and result_status.status == 0:
                return {'error': 'Forbidden'}, 403

            task_id = int(key)
            res = data_base.get_id_status(task_id)
            return {'status': res}

    class Calculation(Resource):
        def post(self):
            result_status = get_resource_status('calculation')
            if result_status is not None and result_status.status == 0:
                return {'error': 'Forbidden'}, 403

            parser = reqparse.RequestParser()
            parser.add_argument('task_id', type=int, required=True)
            parser.add_argument('task', type=str, required=True)
            args = parser.parse_args()

            res = data_base.put_task(args['task_id'], args['task'])
            if res:
                # Обновляем статистику
                data_base.update_time_statistics(args['task_id'],
                                                 'calculation')
                return {'error': 'OK'}, 201
            else:
                return {'error': 'Not Added'}, 405

    class SecretGet(Resource):
        def get(self):
            result_status = get_resource_status('secret_get')
            if result_status is not None and result_status.status == 0:
                return {'error': 'Forbidden'}, 403

            task_id, task_str = data_base.get_task()
            # Обновляем статистику
            data_base.update_time_statistics(task_id, 'secret-get')
            return {'task_id': task_id, 'task': task_str}

    class SecretPut(Resource):
        def post(self):
            result_status = get_resource_status('secret_put')
            if result_status is not None and result_status.status == 0:
                return {'error': 'Forbidden'}, 403

            parser = reqparse.RequestParser()
            parser.add_argument('task_id', type=int, required=True)
            parser.add_argument('results', type=list, location='json',
                                required=True)
            args = parser.parse_args()

            res = data_base.put_result(args['task_id'], args['results'])
            if res:
                # Обновляем статистику
                data_base.update_time_statistics(args['task_id'], 'secret-put')
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
        """
        Формирует HTML страницу для отслеживания параметров.
        :return:
        https://asuavtomatic.ru/resources
        """

        def get_resource_status(resource_name):
            with data_base.session() as session:
                try:
                    result_status = session.query(ResourceStatus).filter_by(
                        resource_name=resource_name).first()
                    return result_status
                finally:
                    session.close()

        resource_statuses = [
            ('results',
             get_resource_status('results').status if get_resource_status(
                 'results') else 'N/A'),
            ('status',
             get_resource_status('status').status if get_resource_status(
                 'status') else 'N/A'),
            ('calculation',
             get_resource_status('calculation').status if get_resource_status(
                 'calculation') else 'N/A'),
            ('secret_get',
             get_resource_status('secret_get').status if get_resource_status(
                 'secret_get') else 'N/A'),
            ('secret_put',
             get_resource_status('secret_put').status if get_resource_status(
                 'secret_put') else 'N/A')
        ]
        return render_template('resources_control.html',
                               resource_statuses=resource_statuses)

    @app.route('/api/v1/resource-count/<resource_type>', methods=['GET'])
    def resource_count(resource_type):
        """
        Позволяет получить количество задач в базе данных.
        :param resource_type:
        :return:
        """
        with data_base.session() as session:
            count = get_resource_count_from_database(session, resource_type)
            return str(count)

    @app.route('/resources/download', methods=['POST'])
    def download_task_statistic():

        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        file_path = data_base.get_task_statistic_by_date_range(start_date_str,
                                                               end_date_str)
        if file_path:
            return send_file(file_path, as_attachment=True)
        else:
            def get_resource_status(resource_name):
                with data_base.session() as session:
                    try:
                        result_status = session.query(
                            ResourceStatus).filter_by(
                            resource_name=resource_name).first()
                        return result_status
                    finally:
                        session.close()

            resource_statuses = [
                ('results',
                 get_resource_status('results').status if get_resource_status(
                     'results') else 'N/A'),
                ('status',
                 get_resource_status('status').status if get_resource_status(
                     'status') else 'N/A'),
                ('calculation',
                 get_resource_status(
                     'calculation').status if get_resource_status(
                     'calculation') else 'N/A'),
                ('secret_get',
                 get_resource_status(
                     'secret_get').status if get_resource_status(
                     'secret_get') else 'N/A'),
                ('secret_put',
                 get_resource_status(
                     'secret_put').status if get_resource_status(
                     'secret_put') else 'N/A')
            ]

            error_message = 'Нет данных в этом диапазоне дат!'
            return render_template('resources_control.html',
                                   resource_statuses=resource_statuses,
                                   error_message=error_message)

    api.add_resource(EnableResource,
                     '/enable-resource/<string:resource_name>')
    api.add_resource(DisableResource,
                     '/disable-resource/<string:resource_name>')

    api.add_resource(Results, '/api/v1/results')
    api.add_resource(Status, '/api/v1/status/<int:key>')
    api.add_resource(Calculation, '/api/v1/calculation')
    api.add_resource(SecretGet, '/api/v1/secret-get')
    api.add_resource(SecretPut, '/api/v1/secret-put')
    api.add_resource(Show, '/api/v1/show')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
