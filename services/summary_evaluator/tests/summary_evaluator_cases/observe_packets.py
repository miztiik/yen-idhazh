"""Observe actual owned byte-pipe payloads without supplying or changing an outcome."""

from dataclasses import dataclass

from summary_evaluator.shared.exchange_packets import ByteChannel


@dataclass
class ObservedChannel:
    channel: ByteChannel
    commands: list[bytes]
    replies: list[bytes]

    def send_bytes(self, encoded: bytes) -> None:
        self.channel.send_bytes(encoded)
        self.commands.append(encoded)

    def recv_bytes(self, maxlength: int | None = None) -> bytes:
        encoded = self.channel.recv_bytes(maxlength)
        self.replies.append(encoded)
        return encoded

    def close(self) -> None:
        self.channel.close()
