import unittest

from sqlalchemy.exc import OperationalError

from tools.base_connector import Queue
from config import DATABASE_URL


class TestQueue(unittest.TestCase):
    """
    Тест запросов.
    Внимание. Будут ошибки, если задача уже существует с таким ID.
    """

    def setUp(self):
        self.queue = Queue(DATABASE_URL)  # Передайте DATABASE_URL из config.py

    def test_database_connection(self):
        """ Тест подключения к базе данных. """

        try:
            self.queue.engine.connect()
            print("Успешное подключение к базе данных.")
        except OperationalError as e:
            print("Ошибка подключения к базе данных:", str(e))

    def test_put_task(self):
        """ Тест вставки задачи в базу """

        result = self.queue.put_task(1, 'task')
        self.assertTrue(result)

    def test_put_result(self):
        """ Тест вставки результата в базу """

        result = self.queue.put_result(1, {'key': 'value'})
        self.assertTrue(result)

    def test_get_task(self):
        """ Тест получение задачи и базы. """

        task_id, task = self.queue.get_task()
        self.assertIsNone(task_id)
        self.assertIsNone(task)

    def test_get_result(self):
        """ Тест получение результата и базы. """

        task_id, result = self.queue.get_result()
        self.assertIsNone(task_id)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
