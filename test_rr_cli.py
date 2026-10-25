import contextlib
import io
import unittest
from unittest.mock import patch
import runrunit_api as api
import rr_cli as cli


class CliTests(unittest.TestCase):
    def test_page_cut_is_partial(self):
        with patch.object(api, "call", return_value={"body": [1, 2, 3], "headers": {}}):
            result = api.paginate("/tasks", 1, 2)
        self.assertEqual(result["body"], [1, 2])
        self.assertTrue(result["truncated"])

    def test_lowercase_link(self):
        with patch.object(api, "call", side_effect=[
            {"body": [1], "headers": {"link": '<https://runrun.it/api/v1.0/tasks?page=2>; rel="next"'}},
            {"body": [2], "headers": {}}]):
            self.assertEqual(api.paginate("/tasks", 2, 10)["body"], [1, 2])

    def test_only_active_assignments_and_title_search(self):
        tasks = [{"title": "C360", "assignments": [{"assignee_id": "hendrix-freire", "is_closed": closed}]} for closed in (True, False)]
        with patch.object(api, "paginate", return_value={"body": tasks, "truncated": True}), patch.object(cli, "output") as out:
            cli.main(["buscar", "c360"])
        result = out.call_args.args[0]
        self.assertEqual(len(result["body"]), 1)
        self.assertTrue(result["truncated"])

    def test_no_write_without_confirmation(self):
        with patch.object(api, "call", return_value={"body": {"id": 123, "title": "Teste"}}) as call, patch.object(cli.sys.stdin, "isatty", return_value=False):
            with self.assertRaises(SystemExit):
                cli.main(["iniciar", "123"])
        self.assertEqual([c.args[0] for c in call.call_args_list], ["GET"])

    def test_confirmed_comment_is_posted_once_and_read_back(self):
        with patch.object(api, "call", side_effect=[{"body": {"id": 123}}, {"body": {"id": 7}}, {"body": {"id": 7, "task_id": 123, "text": "Olá"}}]) as call, contextlib.redirect_stdout(io.StringIO()):
            cli.main(["comentar", "123", "Olá", "--confirmar", "123", "--json"])
        self.assertEqual([c.args[0] for c in call.call_args_list], ["GET", "POST", "GET"])

    def test_terminal_controls_are_removed(self):
        self.assertNotIn("\x1b", cli.plain("<b>Olá</b>\x1b[31m"))


if __name__ == "__main__":
    unittest.main()
