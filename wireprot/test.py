import threading
import unittest
from server import *
from client import *

class ClientServersTest(unittest.TestCase):
  """
  Unit tests for chat application. Note that logins here are orchestrated by directly obtaining the secure token
  for a particular user/pswd. This would not be an accessible method in runtime/production.
  """

  def setup_server_and_clients(self, port, client_count):
    server = Server()
    threading.Thread(target=server.start, args=(port,)).start()

    clients = []
    for i in range(client_count):
      client = Client()
      client.run('localhost', port)
      clients.append(client)
    return server, clients

  def test_signup(self):
    # Create a client and sign up.
    server, clients = self.setup_server_and_clients(8000, 1)
    self.assertTrue(clients[0].authenticate('test', 'test'))
    server.test_close()
    for c in clients:
      c.s.close()

  def test_list(self):
    # Create two accounts.
    server, clients = self.setup_server_and_clients(8001, 2)
    clients[0].authenticate('test_a', 'test')
    clients[1].authenticate('test_b', 'test')

    # List both accounts.
    clients[0].send_action_and_body(2, b'\n')
    _, response = clients[0].receive_response_from_server()
    self.assertEqual(response, b'test_a,test_b') # this is better formatted in the client code (server returns as compressed as possible)
    server.test_close()
    for c in clients:
      c.s.close()

  def test_send_deliver(self):
    # Make 2 clients, with 2 accts.
    server, clients = self.setup_server_and_clients(8002, 2)
    clients[0].authenticate('test_a', 'test')
    clients[1].authenticate('test_b', 'test')

    # Send messages back and forth
    clients[0].send_action_and_body(3, b'test_b:hello1')
    self.assertTrue(clients[0].receive_success_from_server())

    clients[0].send_action_and_body(3, b'test_b:hello2')
    self.assertTrue(clients[0].receive_success_from_server())

    # Get messages back and forth.
    clients[1].send_action_and_body(4, b'test_b')
    self.assertTrue(clients[1].receive_success_from_server())
    messages = clients[1].flush_messages()
    self.assertEqual(len(messages), 2)
    self.assertEqual(messages[0], 'hello1')
    self.assertEqual(messages[1], 'hello2')
    server.test_close()
    for c in clients:
      c.s.close()

  def test_account_deletion(self):
    # Make 1 user, create acct, and then delete them.
    server, clients = self.setup_server_and_clients(8003, 1)
    clients[0].authenticate('test_a', 'test')
    clients[0].send_action_and_body(5, b'test_a')
    self.assertTrue(clients[0].receive_success_from_server())

    # Now try to send messages / get messages and expect fail.
    clients[0].send_action_and_body(3, b'hello, world')
    self.assertFalse(clients[0].receive_success_from_server())

    clients[0].send_action_and_body(4, b'test_a')
    self.assertFalse(clients[0].receive_success_from_server())
    server.test_close()
    for c in clients:
      c.s.close()

if __name__ == '__main__':
  unittest.main(buffer=True)
