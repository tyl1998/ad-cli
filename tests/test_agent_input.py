import unittest
from types import SimpleNamespace
from unittest.mock import patch

from commands.action import cmd_input
from main import build_parser


class DummyADB:
    def get_current_page(self):
        return {"package": "com.demo", "activity": "LoginActivity"}


class AgentInputTest(unittest.TestCase):
    def test_input_parser_accepts_agent_port(self):
        parser = build_parser()

        args = parser.parse_args(
            ["input", "--id", "search_input", "--value", "hello", "--agent-port", "8899"]
        )

        self.assertEqual(args.group, "input")
        self.assertEqual(args.id, "search_input")
        self.assertEqual(args.agent_port, 8899)

    @patch("core.agent_client.AgentClient")
    def test_cmd_input_uses_agent_selector_input_when_agent_port_is_set(self, agent_client_cls):
        adb = DummyADB()
        agent_client = agent_client_cls.return_value
        agent_client.input_by_selector.return_value = {"success": True}
        args = SimpleNamespace(id="search_input", text=None, value="hello", agent_port=8899)

        result = cmd_input(adb, args)

        agent_client_cls.assert_called_once_with(port=8899)
        agent_client.input_by_selector.assert_called_once_with("id", "search_input", "hello")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["command"], "input")
        self.assertEqual(result["source"], "agent")


if __name__ == "__main__":
    unittest.main()
