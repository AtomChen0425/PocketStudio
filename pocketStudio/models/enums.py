from enum import StrEnum

class TeamMode(StrEnum):
    chain = "chain"
    fanout = "fanout"

class MessageStatus(StrEnum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
    dead = "dead"