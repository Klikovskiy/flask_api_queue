import logging
import time

from sqlalchemy import create_engine, Column, Integer, Text, JSON
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound

from config import Base

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s, %(levelname)s, %(name)s, %(message)s',
    handlers=[
        logging.FileHandler('logs.log', mode='w', encoding='utf-8'),
        logging.StreamHandler()]
)


class Task(Base):
    __tablename__ = 'tasks'

    id_tasks = Column(Integer, primary_key=True)
    flag = Column(Integer)
    time = Column(Integer)
    task = Column(Text)


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
        Base.metadata.create_all(self.engine)

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
            session.add(result)
            try:
                task = session.query(Task).filter(
                    Task.id_tasks == task_id).one()
                session.delete(task)
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
        try:
            result = session.query(Result).first()
            if result:
                task_id = result.id_tasks
                json_txt = result.json
                session.delete(result)
                session.commit()
                return task_id, json_txt
            return None, None
        except Exception as error:
            logging.warning(f'get_result Ошибка -> {error}')
            return None, None
        finally:
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


def init_resource_statuses(session):
    """
    Создаем таблицу resource_status в базе данных и
    добавляем записи для каждого ресурса, если их нет.
    """
    resource_statuses = [
        {'resource_name': 'results', 'status': 1},
        {'resource_name': 'status', 'status': 1},
        {'resource_name': 'calculation', 'status': 1},
        {'resource_name': 'secret_get', 'status': 1},
        {'resource_name': 'secret_put', 'status': 1},
    ]

    # Проверяем, есть ли уже записи для ресурсов
    existing_resources = session.query(ResourceStatus.resource_name).all()
    existing_resource_names = {resource[0] for resource in existing_resources}

    for status_data in resource_statuses:
        if status_data['resource_name'] not in existing_resource_names:
            status = ResourceStatus(**status_data)
            session.add(status)

    session.commit()


def enable_resource(session, resource_name):
    # Выполните SQL-запрос для обновления статуса включения ресурса
    stmt = update(ResourceStatus).where(
        ResourceStatus.resource_name == resource_name).values(status=1)
    session.execute(stmt)
    session.commit()


def disable_resource(session, resource_name):
    # Выполните SQL-запрос для обновления статуса отключения ресурса
    stmt = update(ResourceStatus).where(
        ResourceStatus.resource_name == resource_name).values(status=0)
    session.execute(stmt)
    session.commit()