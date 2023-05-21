import threading
import unittest
from server import *

class ClientServersTest(unittest.TestCase):
  def test_signup(self):
    server = ServerServicer()
    self.assertTrue(server.Authenticate(service_pb2.AuthenticateRequest(
      username="test",
      password="test"
    ), None).success)

  def test_list(self):
    server = ServerServicer()
    auth_a = server.Authenticate(service_pb2.AuthenticateRequest(
      username="test_a",
      password="test"
    ), None)
    self.assertTrue(auth_a.success)
    self.assertTrue(server.Authenticate(service_pb2.AuthenticateRequest(
      username="test_b",
      password="test"
    ), None).success)

    response = server.List(service_pb2.ListRequest(
      token=auth_a.response,
      request="\n"
    ), None)
    self.assertTrue(response.success)
    self.assertEqual(response.response, 'test_a,test_b')

  def test_send_deliver(self):
    server = ServerServicer()
    auth_a = server.Authenticate(service_pb2.AuthenticateRequest(
      username="test_a",
      password="test"
    ), None)
    auth_b = server.Authenticate(service_pb2.AuthenticateRequest(
      username="test_b",
      password="test"
    ), None)

    self.assertTrue(auth_a.success)
    self.assertTrue(auth_b.success)

    self.assertTrue(server.Send(service_pb2.SendRequest(
      token=auth_a.response,
      username="test_b",
      body="hello1"
    ), None).success)

    self.assertTrue(server.Send(service_pb2.SendRequest(
      token=auth_a.response,
      username="test_b",
      body="hello2"
    ), None).success)

    response = server.Deliver(service_pb2.DeliverRequest(
      token=auth_b.response,
    ), None)
    self.assertTrue(response.success)
    self.assertEqual(response.response, 'hello1\n\nhello2')

  def test_account_deletion(self):
    # Make 1 user, create acct, and then delete them.
    server = ServerServicer()
    auth_a = server.Authenticate(service_pb2.AuthenticateRequest(
      username="test_a",
      password="test"
    ), None)
    self.assertTrue(auth_a.success)

    self.assertTrue(server.Delete(service_pb2.SendRequest(
      token=auth_a.response,
      username="test_a",
    ), None).success)

    # Now try to send messages / get messages and expect fail.
    self.assertFalse(server.Send(service_pb2.SendRequest(
      token=auth_a.response,
      username="test_b",
      body="hello!"
    ), None).success)

    self.assertFalse(server.Deliver(service_pb2.SendRequest(
      token=auth_a.response,
    ), None).success)

if __name__ == '__main__':
  unittest.main(buffer=True)
