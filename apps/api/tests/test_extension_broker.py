import asyncio

from job_orchestrator.extension.broker import ExtensionBroker


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)


def test_broker_correlates_command_result_by_unique_id() -> None:
    async def scenario() -> None:
        broker = ExtensionBroker()
        socket = FakeWebSocket()
        await broker.attach(socket)

        pending = asyncio.create_task(broker.send_command("detectPage", {}))
        while not socket.sent:
            await asyncio.sleep(0)
        command = socket.sent[0]
        assert command["type"] == "detectPage"
        assert isinstance(command["command_id"], str)

        await broker.handle_message(
            {"command_id": command["command_id"], "result": {"page": "job_detail"}}
        )

        assert await pending == {"page": "job_detail"}

    asyncio.run(scenario())


def test_broker_reports_disconnected_instead_of_dropping_commands() -> None:
    async def scenario() -> None:
        broker = ExtensionBroker()
        try:
            await broker.send_command("collectListings", {"limit": 20})
        except ConnectionError as exc:
            assert "not connected" in str(exc)
        else:
            raise AssertionError("disconnected broker accepted a command")

    asyncio.run(scenario())


def test_broker_records_risk_event_for_dashboard() -> None:
    async def scenario() -> None:
        broker = ExtensionBroker()
        await broker.handle_message(
            {
                "event": "risk_stopped",
                "payload": {"url": "https://www.zhipin.com/job_detail/1", "detectedAt": "now"},
            }
        )
        status = broker.status()
        assert status["connected"] is False
        assert status["last_risk"]["url"].startswith("https://www.zhipin.com")

    asyncio.run(scenario())

