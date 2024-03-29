import csv
import logging
import time
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import and_
from sqlalchemy import create_engine, Column, Integer, Text, JSON
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound

from config import Base, TASK_CHECK_INTERVAL_MINUTES

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s, %(levelname)s, %(name)s, %(message)s',
    handlers=[
        logging.FileHandler('tools/logs.log', mode='w', encoding='utf-8'),
        logging.StreamHandler()]
)


class Task(Base):
    __tablename__ = 'tasks'

    id_tasks = Column(Integer, primary_key=True)
    flag = Column(Integer)
    time = Column(Integer)
    task = Column(Text)


class TaskStatistic(Base):
    __tablename__ = 'tasks_statistics'

    id_tasks = Column(
        Integer,
        primary_key=True,
    )  # id задачи из системы.
    time_put_task = Column(
        Integer,
        nullable=True,
        default=None
    )  # Время, прихода задачи.
    time_get_task = Column(
        Integer,
        nullable=True,
        default=None
    )  # Время, взяли на решение.
    time_put_result = Column(
        Integer,
        nullable=True,
        default=None
    )  # Время, когда получили решение.
    time_get_result = Column(
        Integer,
        nullable=True,
        default=None
    )  # Время, когда забрали решение.


class Result(Base):
    __tablename__ = 'results'

    id_tasks = Column(Integer, primary_key=True)
    json = Column(JSON)


class ResourceStatus(Base):
    __tablename__ = 'resource_status'

    id = Column(Integer, primary_key=True)
    resource_name = Column(Text, unique=True)
    status = Column(Integer)


class Queue:
    def __init__(self, database_url):
        self.engine = create_engine(database_url)
        self.session = sessionmaker(bind=self.engine)
        self.scheduler = BackgroundScheduler()

        Base.metadata.create_all(self.engine)
        self.delay_check: int = TASK_CHECK_INTERVAL_MINUTES

    def start_scheduler(self):
        """ Периодический запуск задач. """
        self.scheduler.add_job(self.check_task_time, 'interval', minutes=int(
            self.delay_check))
        self.scheduler.start()

    def check_task_time(self):
        """ Поиск задач, обнуление флага, сравнение со временем. """
        with self.session() as session:
            tasks_to_check = session.query(Task).filter(Task.flag == 1).all()
            logging.info(f'Find a Task - {len(tasks_to_check)}')
            for task in tasks_to_check:
                task_statistic = session.query(TaskStatistic).filter_by(
                    id_tasks=task.id_tasks).first()
                if task_statistic is None:
                    continue
                if datetime.now() > (task_statistic.time_get_task + timedelta(
                        minutes=int(self.delay_check))):
                    task.flag = 0
            session.commit()

    def update_time_statistics(self, task_id, event):
        """Ведет статистику обновления данных."""

        session = self.session()
        try:
            task_statistic = session.query(TaskStatistic).filter_by(
                id_tasks=task_id).first()

            if task_statistic is not None:
                current_time = int(datetime.now().timestamp())

                if event == 'calculation':
                    task_statistic.time_put_task = current_time
                elif event == 'secret-get':
                    task_statistic.time_get_task = current_time
                elif event == 'secret-put':
                    task_statistic.time_put_result = current_time
                elif event == 'results':
                    task_statistic.time_get_result = current_time

                session.commit()
        except Exception as e:
            session.rollback()
            logging.critical('Error updating time for task '
                             f'{task_id} and event {event}: {e}')
        finally:
            session.close()

    def put_task(self, task_id, string):
        session = self.session()
        try:
            task = Task(id_tasks=task_id, flag=0, time=int(time.time()),
                        task=string)
            session.merge(task)
            session.commit()
            return True
        except IntegrityError:
            session.rollback()
            return False
        except Exception as error:
            logging.warning(f'put_task Ошибка -> {error}')
            session.rollback()
            return False
        finally:
            session.close()

    def put_result(self, task_id, json_txt):
        session = self.session()
        try:
            result = Result(id_tasks=task_id, json=json_txt)
            session.add(result)  # Вставка результата
            try:
                task = session.query(Task).filter(
                    Task.id_tasks == task_id).one()
                session.delete(task)  # Удаление задачи
            except NoResultFound:
                pass
            session.commit()
            return True
        except Exception as error:
            logging.warning(f'put_result Ошибка -> {error}')
            session.rollback()
            return False

        finally:
            session.close()

    def get_task(self):
        session = self.session()
        try:
            task = session.query(Task).filter(Task.flag == 0).order_by(
                Task.time).first()
            if task:
                task.flag = 1
                session.commit()
                return task.id_tasks, task.task
            return None, None  # Очередь пуста
        except Exception as error:
            logging.warning(f'get_task Ошибка -> {error}')
            return None, None
        finally:
            session.close()

    def get_result(self):
        session = self.session()
        result = None
        try:
            result = session.query(Result).first()
            if result:
                task_id = result.id_tasks
                json_txt = result.json
                # session.delete(result)
                session.commit()
                return task_id, json_txt
            return None, None
        except Exception as error:
            logging.warning(f'get_result Ошибка -> {error}')
            return None, None
        finally:
            if result:
                session.delete(result)
                session.commit()
            session.close()

    def get_result_by_id(self, task_id):
        session = self.session()
        try:
            results = session.query(Result).filter(
                Result.id_tasks == task_id).all()
            if results:
                result_list = [
                    {'graph_id': result.id_tasks, 'csv': result.json} for
                    result in results]
                for result in results:
                    session.delete(result)
                session.commit()
                return result_list
            return None
        except Exception as error:
            logging.warning(f'get_result_by_id Ошибка -> {error}')
            return None
        finally:
            session.close()

    def get_results_id(self):
        session = self.session()
        try:
            results = session.query(Result.id_tasks).distinct()
            return results.all()
        except Exception as error:
            logging.warning(f'get_results_id Ошибка -> {error}')
            return None
        finally:
            session.close()

    def get_tasks_id(self):
        session = self.session()
        try:
            tasks = session.query(Task.id_tasks).filter(Task.flag == 0)
            return tasks.all()
        except Exception as error:
            logging.warning(f'get_tasks_id Ошибка -> {error}')
            return None
        finally:
            session.close()

    def get_id_status(self, task_id):
        session_results = self.session()
        session_tasks = self.session()
        try:
            result_query = session_results.query(Result.id_tasks).filter(
                Result.id_tasks == task_id)
            task_query = session_tasks.query(Task.id_tasks).filter(
                Task.id_tasks == task_id)

            if result_query.count():
                return 2
            elif task_query.count():
                return 1
            else:
                return 0
        except Exception as error:
            logging.warning(f'get_id_status Ошибка -> {error}')
            return 0
        finally:
            session_results.close()
            session_tasks.close()

    def get_task_statistic_by_date_range(self, start_date, end_date):
        """
        Извлекает статистические данные из таблицы API.
        """
        # Преобразование дат в unixtime
        # Не раньше 00:00
        start_unixtime = datetime.strptime(start_date, '%Y-%m-%d').timestamp()
        # Не позже 23:59:59
        end_unixtime = datetime.strptime(end_date,
                                         '%Y-%m-%d').timestamp() + 86399

        with self.session() as session:

            logging.critical(
                "Количество записей в TaskStatistic: "
                f"{session.query(TaskStatistic).count()}")

            try:
                query = session.query(TaskStatistic).filter(
                    and_(
                        TaskStatistic.time_put_task >= start_unixtime,
                        TaskStatistic.time_put_task < end_unixtime,
                        # TaskStatistic.time_get_result <= end_unixtime
                    )
                )
                data = query.all()

                if data:
                    file_path = "task_statistic.csv"
                    with open(file_path, 'w', newline='') as csv_file:
                        csv_writer = csv.writer(csv_file)
                        csv_writer.writerow(
                            ['id_tasks', 'time_put_task', 'time_get_task',
                             'time_put_result', 'time_get_result'])
                        for row in data:
                            csv_writer.writerow(
                                [row.id_tasks, row.time_put_task,
                                 row.time_get_task, row.time_put_result,
                                 row.time_get_result])

                    return file_path
                else:
                    return None
            finally:
                session.close()


def init_resource_statuses(session):
    """
    Создаем таблицу resource_status в базе данных и
    добавляем записи для каждого ресурса, если их нет.
    """

    try:
        resource_statuses = [
            {'resource_name': 'results', 'status': 1},
            {'resource_name': 'status', 'status': 1},
            {'resource_name': 'calculation', 'status': 1},
            {'resource_name': 'secret_get', 'status': 1},
            {'resource_name': 'secret_put', 'status': 1},
        ]

        # Проверяем, есть ли уже записи для ресурсов
        existing_resources = session.query(ResourceStatus.resource_name).all()
        existing_resource_names = {resource[0] for resource in
                                   existing_resources}

        for status_data in resource_statuses:
            if status_data['resource_name'] not in existing_resource_names:
                status = ResourceStatus(**status_data)
                session.add(status)

        session.commit()
    except Exception as error:
        # Обработка ошибки и логирование
        logging.error(f'init_resource_statuses Ошибка -> {error}')
        session.rollback()


def enable_resource(session, resource_name):
    """
    Запрос, чтобы обновить статус включения ресурса.
    :param session:
    :param resource_name:
    :return:
    """
    stmt = update(ResourceStatus).where(
        ResourceStatus.resource_name == resource_name).values(status=1)
    session.execute(stmt)
    session.commit()


def disable_resource(session, resource_name):
    """
    Запрос, чтобы обновить статус отключения ресурса.
    :param session:
    :param resource_name:
    :return:
    """
    stmt = update(ResourceStatus).where(
        ResourceStatus.resource_name == resource_name).values(status=0)
    session.execute(stmt)
    session.commit()


def get_resource_count_from_database(session, resource_type):
    """
    Получает количество задач, которые есть в базе данных.
    :param session:
    :param resource_type:
    :return:
    """
    try:
        stmt = update(ResourceStatus).where(
            ResourceStatus.resource_name == resource_type).values(status=0)
        session.execute(stmt)

        if resource_type == 'results':
            count = session.query(Result).count()
        elif resource_type == 'status':
            count = session.query(Task).filter(Task.flag == 0).count()
        elif resource_type == 'calculation':
            count = session.query(Task).filter(Task.flag == 1).count()
        else:
            count = 0

        return count
    except Exception as error:
        logging.warning(f'get_resource_count_from_database Ошибка -> {error}')
        return 0
