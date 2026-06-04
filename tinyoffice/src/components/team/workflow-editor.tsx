"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import { Check, FileJson, GitBranch, LayoutDashboard, Plus, Trash2, Upload, Wand2 } from "lucide-react";

import { agentColor } from "@/components/sidebar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { AgentConfig, WorkflowDefinition, WorkflowEdge, WorkflowNode } from "@/lib/api";
import { cn } from "@/lib/utils";

type EditorMode = "graph" | "json";

type WorkflowEditorProps = {
  enabled: boolean;
  workflowId: string;
  workflowName: string;
  definitionJson: string;
  agents: Record<string, AgentConfig>;
  teamAgentIds: string[];
  leaderAgentId: string;
  onEnabledChange: (enabled: boolean) => void;
  onWorkflowIdChange: (workflowId: string) => void;
  onWorkflowNameChange: (workflowName: string) => void;
  onDefinitionJsonChange: (json: string) => void;
};

type WorkflowNodeData = {
  workflowNode: WorkflowNode;
  label: string;
  color: string;
  isEntry: boolean;
  isOutput: boolean;
};

const FLOW_X_GAP = 260;
const FLOW_Y = 80;

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function defaultDefinition(agentId: string): WorkflowDefinition {
  return {
    version: 1,
    entrypoint: "start",
    outputNode: "start",
    nodes: [
      {
        id: "start",
        agentId,
        prompt: "Handle the team request.",
      },
    ],
    edges: [],
    metadata: { name: "Default Workflow" },
  };
}

function parseDefinition(value: unknown): WorkflowDefinition {
  if (!value || typeof value !== "object") {
    throw new Error("Workflow JSON must be an object");
  }
  const record = value as Record<string, unknown>;
  const workflow = record.workflow && typeof record.workflow === "object"
    ? record.workflow as Record<string, unknown>
    : record;
  const definition = workflow.definition && typeof workflow.definition === "object"
    ? workflow.definition
    : workflow;
  const candidate = definition as Partial<WorkflowDefinition>;
  if (!candidate.entrypoint || !Array.isArray(candidate.nodes)) {
    throw new Error("Workflow JSON must include entrypoint and nodes");
  }
  return normalizeDefinition({
    version: candidate.version ?? 1,
    entrypoint: candidate.entrypoint,
    outputNode: candidate.outputNode || "",
    nodes: candidate.nodes as WorkflowNode[],
    edges: Array.isArray(candidate.edges) ? candidate.edges as WorkflowEdge[] : [],
    metadata: candidate.metadata || {},
  });
}

function parseDefinitionJson(json: string, fallbackAgentId: string): WorkflowDefinition {
  if (!json.trim()) return defaultDefinition(fallbackAgentId);
  return parseDefinition(JSON.parse(json));
}

function normalizeDefinition(definition: WorkflowDefinition): WorkflowDefinition {
  const nodes = definition.nodes.map((node) => ({
    ...node,
    type: node.type || "agent",
    prompt: node.prompt || "",
    inputTemplate: node.inputTemplate || "",
  }));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const entrypoint = nodeIds.has(definition.entrypoint) ? definition.entrypoint : nodes[0]?.id || "";
  const outputNode = definition.outputNode && nodeIds.has(definition.outputNode)
    ? definition.outputNode
    : nodes[nodes.length - 1]?.id || entrypoint;
  const edges = (definition.edges || []).filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target));
  return {
    version: definition.version ?? 1,
    entrypoint,
    outputNode,
    nodes,
    edges,
    metadata: definition.metadata || {},
  };
}

function definitionToFlow(
  definition: WorkflowDefinition,
  agents: Record<string, AgentConfig>,
): { nodes: Node<WorkflowNodeData>[]; edges: Edge[] } {
  const nodes = definition.nodes.map((workflowNode, index) => ({
    id: workflowNode.id,
    type: "workflowAgent",
    position: { x: index * FLOW_X_GAP, y: FLOW_Y },
    data: {
      workflowNode,
      label: agents[workflowNode.agentId]?.name || workflowNode.agentId,
      color: agentColor(workflowNode.agentId),
      isEntry: workflowNode.id === definition.entrypoint,
      isOutput: workflowNode.id === definition.outputNode,
    },
  }));
  const edges = definition.edges.map((edge) => ({
    id: `${edge.source}->${edge.target}`,
    source: edge.source,
    target: edge.target,
    type: "smoothstep",
    animated: false,
    style: { stroke: "var(--color-primary)" },
  }));
  return { nodes, edges };
}

function hasCycle(nodes: WorkflowNode[], edges: WorkflowEdge[]): boolean {
  const outgoing = new Map<string, string[]>();
  for (const node of nodes) outgoing.set(node.id, []);
  for (const edge of edges) outgoing.get(edge.source)?.push(edge.target);
  const visiting = new Set<string>();
  const visited = new Set<string>();

  const visit = (nodeId: string): boolean => {
    if (visiting.has(nodeId)) return true;
    if (visited.has(nodeId)) return false;
    visiting.add(nodeId);
    for (const target of outgoing.get(nodeId) || []) {
      if (visit(target)) return true;
    }
    visiting.delete(nodeId);
    visited.add(nodeId);
    return false;
  };

  return nodes.some((node) => visit(node.id));
}

function nextNodeId(nodes: WorkflowNode[]): string {
  let index = nodes.length + 1;
  const existing = new Set(nodes.map((node) => node.id));
  while (existing.has(`node_${index}`)) index += 1;
  return `node_${index}`;
}

function WorkflowAgentNode({ data }: NodeProps<Node<WorkflowNodeData>>) {
  const node = data.workflowNode;
  return (
    <div className="w-[190px] border bg-card shadow-sm">
      <Handle type="target" position={Position.Left} className="!bg-muted-foreground" />
      <Handle type="source" position={Position.Right} className="!bg-primary" />
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <div className={cn("flex h-7 w-7 items-center justify-center text-[10px] font-bold uppercase text-white", data.color)}>
          {data.label.slice(0, 2)}
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{data.label}</div>
          <div className="truncate text-[11px] text-muted-foreground">@{node.agentId}</div>
        </div>
      </div>
      <div className="flex flex-wrap gap-1 px-3 py-2">
        {data.isEntry && <Badge className="h-5 text-[10px]">Entry</Badge>}
        {data.isOutput && <Badge variant="outline" className="h-5 text-[10px]">Output</Badge>}
        {!data.isEntry && !data.isOutput && <span className="text-[11px] text-muted-foreground">Agent node</span>}
      </div>
    </div>
  );
}

const nodeTypes: NodeTypes = {
  workflowAgent: WorkflowAgentNode,
};

export function WorkflowEditor({
  enabled,
  workflowId,
  workflowName,
  definitionJson,
  agents,
  teamAgentIds,
  leaderAgentId,
  onEnabledChange,
  onWorkflowIdChange,
  onWorkflowNameChange,
  onDefinitionJsonChange,
}: WorkflowEditorProps) {
  const fallbackAgentId = leaderAgentId || teamAgentIds[0] || "";
  const [mode, setMode] = useState<EditorMode>("graph");
  const [definition, setDefinition] = useState<WorkflowDefinition>(() => parseDefinitionJson(definitionJson, fallbackAgentId));
  const [nodes, setNodes] = useState<Node<WorkflowNodeData>[]>(() => definitionToFlow(definition, agents).nodes);
  const [edges, setEdges] = useState<Edge[]>(() => definitionToFlow(definition, agents).edges);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(definition.nodes[0]?.id || null);
  const [jsonDraft, setJsonDraft] = useState(definitionJson || prettyJson(definition));
  const [status, setStatus] = useState("");

  useEffect(() => {
    if (!enabled) return;
    try {
      const parsed = parseDefinitionJson(definitionJson, fallbackAgentId);
      /* eslint-disable react-hooks/set-state-in-effect */
      setDefinition(parsed);
      const flow = definitionToFlow(parsed, agents);
      setNodes(flow.nodes);
      setEdges(flow.edges);
      setJsonDraft(prettyJson(parsed));
      setSelectedNodeId((current) => current && parsed.nodes.some((node) => node.id === current) ? current : parsed.nodes[0]?.id || null);
      /* eslint-enable react-hooks/set-state-in-effect */
    } catch {
      setJsonDraft(definitionJson);
    }
  }, [agents, definitionJson, enabled, fallbackAgentId]);

  const commitDefinition = useCallback((nextDefinition: WorkflowDefinition, message = "") => {
    const normalized = normalizeDefinition(nextDefinition);
    setDefinition(normalized);
    const flow = definitionToFlow(normalized, agents);
    setNodes(flow.nodes);
    setEdges(flow.edges);
    const json = prettyJson(normalized);
    setJsonDraft(json);
    onDefinitionJsonChange(json);
    if (message) setStatus(message);
  }, [agents, onDefinitionJsonChange]);

  const handleEnabledChange = (nextEnabled: boolean) => {
    onEnabledChange(nextEnabled);
    if (nextEnabled && !definitionJson.trim()) {
      const initial = defaultDefinition(fallbackAgentId);
      commitDefinition(initial);
    }
  };

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((current) => applyNodeChanges(changes, current) as Node<WorkflowNodeData>[]);
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((current) => applyEdgeChanges(changes, current));
  }, []);

  const onConnect = useCallback((connection: Connection) => {
    if (!connection.source || !connection.target || connection.source === connection.target) {
      setStatus("Invalid connection");
      return;
    }
    if (definition.edges.some((edge) => edge.source === connection.source && edge.target === connection.target)) {
      setStatus("Connection already exists");
      return;
    }
    const nextEdges = [...definition.edges, { source: connection.source, target: connection.target }];
    if (hasCycle(definition.nodes, nextEdges)) {
      setStatus("Workflow cannot contain cycles");
      return;
    }
    commitDefinition({ ...definition, edges: nextEdges }, "Connection added");
    setEdges((current) => addEdge({ ...connection, type: "smoothstep" }, current));
  }, [commitDefinition, definition]);

  const addAgentNode = () => {
    const agentId = teamAgentIds.find(Boolean) || fallbackAgentId;
    if (!agentId) {
      setStatus("Select at least one team member first");
      return;
    }
    const nodeId = nextNodeId(definition.nodes);
    const nextNodes = [
      ...definition.nodes,
      { id: nodeId, agentId, prompt: "", inputTemplate: "" },
    ];
    commitDefinition({
      ...definition,
      entrypoint: definition.entrypoint || nodeId,
      outputNode: definition.outputNode || nodeId,
      nodes: nextNodes,
    }, "Agent node added");
    setSelectedNodeId(nodeId);
  };

  const updateWorkflowNode = (nodeId: string, patch: Partial<WorkflowNode>) => {
    commitDefinition({
      ...definition,
      nodes: definition.nodes.map((node) => node.id === nodeId ? { ...node, ...patch } : node),
    });
  };

  const renameNode = (nodeId: string, nextId: string) => {
    if (!nextId || nextId === nodeId) return;
    if (!/^[a-zA-Z0-9_-]+$/.test(nextId)) {
      setStatus("Node ID can only contain letters, numbers, _ and -");
      return;
    }
    if (definition.nodes.some((node) => node.id === nextId)) {
      setStatus("Node ID already exists");
      return;
    }
    commitDefinition({
      ...definition,
      entrypoint: definition.entrypoint === nodeId ? nextId : definition.entrypoint,
      outputNode: definition.outputNode === nodeId ? nextId : definition.outputNode,
      nodes: definition.nodes.map((node) => node.id === nodeId ? { ...node, id: nextId } : node),
      edges: definition.edges.map((edge) => ({
        ...edge,
        source: edge.source === nodeId ? nextId : edge.source,
        target: edge.target === nodeId ? nextId : edge.target,
      })),
    });
    setSelectedNodeId(nextId);
  };

  const deleteSelectedNode = () => {
    if (!selectedNodeId) return;
    const nextNodes = definition.nodes.filter((node) => node.id !== selectedNodeId);
    const nextEdges = definition.edges.filter((edge) => edge.source !== selectedNodeId && edge.target !== selectedNodeId);
    commitDefinition({
      ...definition,
      nodes: nextNodes,
      edges: nextEdges,
      entrypoint: definition.entrypoint === selectedNodeId ? nextNodes[0]?.id || "" : definition.entrypoint,
      outputNode: definition.outputNode === selectedNodeId ? nextNodes[nextNodes.length - 1]?.id || "" : definition.outputNode,
    }, "Node deleted");
    setSelectedNodeId(nextNodes[0]?.id || null);
  };

  const deleteSelectedEdges = (deletedEdges: Edge[]) => {
    if (!deletedEdges.length) return;
    const deletedIds = new Set(deletedEdges.map((edge) => edge.id));
    commitDefinition({
      ...definition,
      edges: definition.edges.filter((edge) => !deletedIds.has(`${edge.source}->${edge.target}`)),
    }, "Connection removed");
  };

  const autoLayout = () => {
    const flow = definitionToFlow(definition, agents);
    setNodes(flow.nodes);
    setEdges(flow.edges);
    setStatus("Layout reset");
  };

  const applyJson = () => {
    try {
      const parsed = parseDefinition(JSON.parse(jsonDraft));
      commitDefinition(parsed, "JSON applied");
    } catch (err) {
      setStatus((err as Error).message);
    }
  };

  const formatJson = () => {
    try {
      const parsed = parseDefinition(JSON.parse(jsonDraft));
      const formatted = prettyJson(parsed);
      setJsonDraft(formatted);
      onDefinitionJsonChange(formatted);
      setStatus("JSON formatted");
    } catch (err) {
      setStatus((err as Error).message);
    }
  };

  const importJsonFile = async (file: File | undefined) => {
    if (!file) return;
    try {
      const text = await file.text();
      const parsed = parseDefinition(JSON.parse(text));
      commitDefinition(parsed, `Imported ${file.name}`);
    } catch (err) {
      setStatus((err as Error).message);
    }
  };

  const validateLocal = () => {
    const missingAgents = definition.nodes
      .map((node) => node.agentId)
      .filter((agentId) => !teamAgentIds.includes(agentId));
    if (missingAgents.length) {
      setStatus(`Unknown team agents: ${Array.from(new Set(missingAgents)).join(", ")}`);
      return;
    }
    if (hasCycle(definition.nodes, definition.edges)) {
      setStatus("Workflow cannot contain cycles");
      return;
    }
    setStatus(`Workflow is valid: ${definition.nodes.length} nodes, ${definition.edges.length} edges`);
  };

  const selectedNode = useMemo(
    () => definition.nodes.find((node) => node.id === selectedNodeId) || null,
    [definition.nodes, selectedNodeId],
  );

  return (
    <div className="space-y-3 border-t pt-4">
      <div className="flex items-center justify-between gap-4">
        <label className="text-xs font-medium text-muted-foreground">Workflow</label>
        <Switch checked={enabled} onCheckedChange={handleEnabledChange} disabled={teamAgentIds.length === 0} />
      </div>

      {enabled && (
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Workflow ID</label>
              <Input
                value={workflowId}
                onChange={(event) => onWorkflowIdChange(event.target.value)}
                placeholder="e.g. delivery-flow"
                className="font-mono"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Workflow Name</label>
              <Input
                value={workflowName}
                onChange={(event) => onWorkflowNameChange(event.target.value)}
                placeholder="e.g. Delivery Flow"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex border">
              <Button type="button" variant={mode === "graph" ? "secondary" : "ghost"} size="sm" onClick={() => setMode("graph")}>
                <GitBranch className="h-3.5 w-3.5" />
                Graph
              </Button>
              <Button type="button" variant={mode === "json" ? "secondary" : "ghost"} size="sm" onClick={() => setMode("json")}>
                <FileJson className="h-3.5 w-3.5" />
                JSON
              </Button>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={addAgentNode}>
              <Plus className="h-3.5 w-3.5" />
              Add Agent
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={autoLayout}>
              <LayoutDashboard className="h-3.5 w-3.5" />
              Layout
            </Button>
            <label className="inline-flex">
              <input
                type="file"
                accept="application/json,.json"
                className="hidden"
                onChange={(event) => importJsonFile(event.target.files?.[0])}
              />
              <Button type="button" variant="outline" size="sm" asChild>
                <span>
                  <Upload className="h-3.5 w-3.5" />
                  Import
                </span>
              </Button>
            </label>
            <Button type="button" variant="outline" size="sm" onClick={validateLocal}>
              <Check className="h-3.5 w-3.5" />
              Validate
            </Button>
            {status && <span className="text-xs text-muted-foreground">{status}</span>}
          </div>

          {mode === "graph" ? (
            <div className="grid min-h-[520px] grid-cols-1 border lg:grid-cols-[minmax(0,1fr)_320px]">
              <div className="h-[520px] border-b lg:border-b-0 lg:border-r">
                <ReactFlowProvider>
                  <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    nodeTypes={nodeTypes}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onEdgesDelete={deleteSelectedEdges}
                    onConnect={onConnect}
                    onNodeClick={(_event, node) => setSelectedNodeId(node.id)}
                    fitView
                    fitViewOptions={{ padding: 0.25 }}
                    proOptions={{ hideAttribution: true }}
                  >
                    <Background />
                    <Controls />
                  </ReactFlow>
                </ReactFlowProvider>
              </div>

              <div className="space-y-3 p-4">
                {selectedNode ? (
                  <>
                    <div className="flex items-center justify-between gap-2">
                      <div>
                        <div className="text-sm font-medium">Node</div>
                        <div className="text-xs text-muted-foreground">@{selectedNode.agentId}</div>
                      </div>
                      <Button type="button" variant="ghost" size="icon" onClick={deleteSelectedNode}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-muted-foreground">Node ID</label>
                      <Input value={selectedNode.id} onChange={(event) => renameNode(selectedNode.id, event.target.value)} className="font-mono" />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-muted-foreground">Agent</label>
                      <Select value={selectedNode.agentId} onValueChange={(agentId) => updateWorkflowNode(selectedNode.id, { agentId })}>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {teamAgentIds.map((agentId) => (
                            <SelectItem key={agentId} value={agentId}>
                              {agents[agentId]?.name || agentId}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-muted-foreground">Prompt</label>
                      <Textarea
                        value={selectedNode.prompt || ""}
                        onChange={(event) => updateWorkflowNode(selectedNode.id, { prompt: event.target.value })}
                        className="min-h-24 text-sm"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-muted-foreground">Input Template</label>
                      <Textarea
                        value={selectedNode.inputTemplate || ""}
                        onChange={(event) => updateWorkflowNode(selectedNode.id, { inputTemplate: event.target.value })}
                        className="min-h-24 font-mono text-xs"
                      />
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" variant={definition.entrypoint === selectedNode.id ? "default" : "outline"} size="sm" onClick={() => commitDefinition({ ...definition, entrypoint: selectedNode.id })}>
                        Entry
                      </Button>
                      <Button type="button" variant={definition.outputNode === selectedNode.id ? "default" : "outline"} size="sm" onClick={() => commitDefinition({ ...definition, outputNode: selectedNode.id })}>
                        Output
                      </Button>
                    </div>
                  </>
                ) : (
                  <div className="text-sm text-muted-foreground">Select or add a node.</div>
                )}
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <Textarea
                value={jsonDraft}
                onChange={(event) => setJsonDraft(event.target.value)}
                className="min-h-[520px] font-mono text-xs leading-relaxed"
                spellCheck={false}
              />
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="outline" size="sm" onClick={applyJson}>
                  <Check className="h-3.5 w-3.5" />
                  Apply JSON
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={formatJson}>
                  <Wand2 className="h-3.5 w-3.5" />
                  Format
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
