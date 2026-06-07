from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WorkflowRoutingFunction(BaseModel):
    language: Literal["python"] = "python"
    code: str
    entrypoint: str = "route"

    @field_validator("code")
    @classmethod
    def code_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Workflow routingFunction code must not be empty")
        return value

    @field_validator("entrypoint")
    @classmethod
    def entrypoint_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Workflow routingFunction entrypoint must not be empty")
        return value


class WorkflowNode(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    agent_id: str = Field(default="", alias="agentId")
    prompt: str = ""
    input_template: str = Field(default="", alias="inputTemplate")
    type: str = "agent"
    routing_function: WorkflowRoutingFunction | None = Field(default=None, alias="routingFunction")
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class WorkflowEdge(BaseModel):
    source: str
    target: str
    condition: str = ""


class WorkflowRoute(BaseModel):
    condition: str
    target: str


class WorkflowConditionalEdge(BaseModel):
    source: str
    routes: list[WorkflowRoute] = Field(min_length=1)
    default_target: str = Field(default="", alias="defaultTarget")

    model_config = ConfigDict(populate_by_name=True)


class WorkflowDefinition(BaseModel):
    version: int = 1
    entrypoint: str
    output_node: str = Field(default="", alias="outputNode")
    nodes: list[WorkflowNode] = Field(min_length=1)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    conditional_edges: list[WorkflowConditionalEdge] = Field(default_factory=list, alias="conditionalEdges")
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("version")
    @classmethod
    def supported_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("Only workflow definition version 1 is supported")
        return value

    @model_validator(mode="after")
    def validate_graph_shape(self) -> "WorkflowDefinition":
        node_ids = [node.id for node in self.nodes]
        unique_node_ids = set(node_ids)
        if len(unique_node_ids) != len(node_ids):
            raise ValueError("Workflow node ids must be unique")
        if self.entrypoint not in unique_node_ids:
            raise ValueError("Workflow entrypoint must match a node id")
        if self.output_node and self.output_node not in unique_node_ids:
            raise ValueError("Workflow outputNode must match a node id")
        for edge in self.edges:
            if edge.source not in unique_node_ids:
                raise ValueError(f"Workflow edge source '{edge.source}' does not match a node id")
            if edge.target not in unique_node_ids:
                raise ValueError(f"Workflow edge target '{edge.target}' does not match a node id")
        for conditional_edge in self.conditional_edges:
            if conditional_edge.source not in unique_node_ids:
                raise ValueError(f"Workflow conditional edge source '{conditional_edge.source}' does not match a node id")
            if conditional_edge.default_target and conditional_edge.default_target not in unique_node_ids:
                raise ValueError(
                    f"Workflow conditional edge defaultTarget '{conditional_edge.default_target}' does not match a node id"
                )
            seen_conditions: set[str] = set()
            for route in conditional_edge.routes:
                if not route.condition:
                    raise ValueError("Workflow conditional edge route condition must not be empty")
                if route.condition in seen_conditions:
                    raise ValueError(f"Workflow conditional edge condition '{route.condition}' is duplicated")
                seen_conditions.add(route.condition)
                if route.target not in unique_node_ids:
                    raise ValueError(f"Workflow conditional edge route target '{route.target}' does not match a node id")
        for node in self.nodes:
            if node.type == "agent" and not node.agent_id:
                raise ValueError(f"Workflow agent node '{node.id}' must include agentId")
        return self


class TeamWorkflowCreate(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    name: str
    description: str = ""
    definition: WorkflowDefinition
    enabled: bool = True


class TeamWorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    definition: WorkflowDefinition | None = None
    enabled: bool | None = None


class TeamWorkflow(BaseModel):
    id: str
    team_id: str = Field(alias="teamId")
    name: str
    description: str = ""
    definition: WorkflowDefinition
    enabled: bool = True
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)
